import os

import httpx
import pytest

# All overridable via env vars so this file can run against either a local Artifactory
# instance (defaults below) or a real deployed environment — e.g. against this platform's
# cluster via `kubectl port-forward`:
#   kubectl -n artifactory port-forward svc/artifactory 18082:8082
#   kubectl -n devops-api port-forward svc/devops-api 15000:5000
#   ARTIFACTORY_URL=http://localhost:18082 API_URL=http://localhost:15000 \
#   ARTIFACTORY_TOKEN=<reference-or-identity-token> \
#   pytest tests/v1/artifactory/test_artifactory_e2e.py -v -m integration
#
# Auth: Artifactory's Access API (everything this module calls) rejects Basic auth outright
# (401 Unsupported authentication method Basic) — the direct-check client below authenticates
# with Authorization: Bearer, same as devops-api itself. See app/v1/artifactory/CLAUDE.md's
# "Auth: Bearer token, not Basic" section.
ARTIFACTORY_URL = os.environ.get("ARTIFACTORY_URL", "http://localhost:8082")
API_URL = os.environ.get("API_URL", "http://localhost:5002")
ARTIFACTORY_TOKEN = os.environ.get("ARTIFACTORY_TOKEN", "")
PREFIX = "/api/v1/devops/artifactory"

PROJECT_NAME = os.environ.get("E2E_PROJECT_NAME", "e2e-test-project")
# Unlike Bitbucket/Confluence/Jira, "admin" is NOT a safe default here — confirmed live
# (2026-08-16): Artifactory rejects assigning the platform admin account as an explicit
# project member ("User 'admin' is a Platform Administrator and cannot be explicitly added
# as a Project Member"), so admin-assignment tests 400 with the default unless overridden
# to a real non-admin user. This lab instance currently seeds only "admin"/"anonymous" — no
# such user exists yet. Set E2E_ADMIN_USER to a real non-admin username to make these tests
# pass. (admin_group was tried as an alternative and also fails right now — "Invalid role
# assignment; role name `project_admin`" — likely gated behind the Artifactory Pro+ license
# this instance intentionally doesn't have yet; see devtools-labs/docs/
# post-devtools-implementation/artifactory/README.md's License section.)
ADMIN_USER = os.environ.get("E2E_ADMIN_USER", "admin")
# Default project role shipped with every JFrog Platform instance — no setup required.
ROLE_NAME = os.environ.get("E2E_ROLE_NAME", "Developer")

REQUEST_METADATA = {
    "project": "devops-api-e2e",
    "network": "test",
    "region": "test",
    "space": "test",
    "environment": "test",
}


def _project_key(name: str) -> str:
    return name.lower().replace(" ", "-").replace("_", "-")


PROJECT_KEY = _project_key(PROJECT_NAME)


@pytest.fixture(scope="module")
def af():
    with httpx.Client(
        base_url=ARTIFACTORY_URL,
        headers={"Authorization": f"Bearer {ARTIFACTORY_TOKEN}"},
        timeout=30.0,
    ) as client:
        yield client


@pytest.fixture(scope="module")
def api():
    with httpx.Client(base_url=API_URL, timeout=30.0) as client:
        yield client


def _delete_project_if_exists(af: httpx.Client, key: str):
    af.delete(f"/access/api/v1/projects/{key}")


def _project_exists(af: httpx.Client, key: str) -> bool:
    return af.get(f"/access/api/v1/projects/{key}").status_code == 200


@pytest.fixture
def clean_project(af):
    # Cleanup via `yield` (not just at the top of the test) so teardown still runs if the
    # test fails partway through — see tests/v1/bitbucket/test_bitbucket_e2e.py's
    # clean_project fixture for the incident this pattern exists to avoid.
    _delete_project_if_exists(af, PROJECT_KEY)
    yield PROJECT_KEY
    _delete_project_if_exists(af, PROJECT_KEY)


@pytest.mark.integration
def test_create_project_e2e(af, api, clean_project):
    assert not _project_exists(af, PROJECT_KEY)

    r = api.post(
        f"{PREFIX}/",
        json={
            "metadata": REQUEST_METADATA,
            "spec": {
                "name": PROJECT_NAME,
                "storage_quota_giga_bytes": 1,
                "admin_user": ADMIN_USER,
            },
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "successful"

    # cross-check against Artifactory directly — never just trust devops-api's response
    direct = af.get(f"/access/api/v1/projects/{PROJECT_KEY}")
    assert direct.status_code == 200, direct.text
    body = direct.json()
    assert body["display_name"] == PROJECT_NAME
    assert body["storage_quota_bytes"] == 1 * 1024**3

    users = af.get(f"/access/api/v1/projects/{PROJECT_KEY}/users")
    assert users.status_code == 200, users.text
    assert any(
        u["name"] == ADMIN_USER and "PROJECT_ADMIN" in u["roles"]
        for u in users.json()
    ), users.text


@pytest.mark.integration
def test_storage_quota_e2e(af, api, clean_project):
    api.post(
        f"{PREFIX}/",
        json={
            "metadata": REQUEST_METADATA,
            "spec": {
                "name": PROJECT_NAME,
                "storage_quota_giga_bytes": 1,
                "admin_user": ADMIN_USER,
            },
        },
    )

    r = api.post(
        f"{PREFIX}/storage-quota",
        json={
            "metadata": REQUEST_METADATA,
            "spec": {"name": PROJECT_KEY, "storage_quota_giga_bytes": 2},
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "successful"

    direct = af.get(f"/access/api/v1/projects/{PROJECT_KEY}")
    assert direct.status_code == 200, direct.text
    # 1 GB at creation + 2 GB added = 3 GB
    assert direct.json()["storage_quota_bytes"] == 3 * 1024**3


@pytest.mark.integration
def test_get_role_e2e(api):
    r = api.get(f"{PREFIX}/permissions/roles/{ROLE_NAME}")
    assert r.status_code == 200, r.text
    assert r.json()["name"] == ROLE_NAME


@pytest.mark.integration
def test_grant_permission_and_get_permissions_e2e(af, api, clean_project):
    api.post(
        f"{PREFIX}/",
        json={
            "metadata": REQUEST_METADATA,
            "spec": {
                "name": PROJECT_NAME,
                "storage_quota_giga_bytes": 1,
                "admin_user": ADMIN_USER,
            },
        },
    )

    r = api.post(
        f"{PREFIX}/permissions",
        json={
            "metadata": REQUEST_METADATA,
            "spec": {
                "project_key": PROJECT_KEY,
                "member_name": ADMIN_USER,
                "member_type": "user",
                "roles": [ROLE_NAME],
            },
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "successful"

    perms = api.get(f"{PREFIX}/permissions/{PROJECT_KEY}")
    assert perms.status_code == 200, perms.text
    users = perms.json()["users"]
    assert any(
        u["name"] == ADMIN_USER and ROLE_NAME in u["roles"] for u in users
    ), users

    # cross-check against Artifactory directly
    direct = af.get(f"/access/api/v1/projects/{PROJECT_KEY}/users")
    assert direct.status_code == 200, direct.text
    assert any(
        u["name"] == ADMIN_USER and ROLE_NAME in u["roles"] for u in direct.json()
    ), direct.json()


@pytest.mark.integration
@pytest.mark.skip(
    reason="Requires a real Xray offline-update archive pre-uploaded to MinIO's "
    "platform-devops-team/xray-vulnerability-updates/ bucket, and applies a real update to "
    "Xray's vulnerability DB — not safe to run unattended in CI/e2e. Verify manually per "
    "README.md's 'MinIO setup' section when needed."
)
def test_xray_vulnerability_update_e2e(api):
    pass
