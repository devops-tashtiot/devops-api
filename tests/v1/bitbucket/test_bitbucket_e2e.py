import os

import httpx
import pytest

# All overridable via env vars so this file can run against either the local
# docker-compose stack (defaults below) or a real deployed environment — e.g. against
# this platform's cluster via `kubectl port-forward`:
#   kubectl -n bitbucket port-forward svc/bitbucket 17990:80
#   kubectl -n devops-api port-forward svc/devops-api 15000:5000
#   BITBUCKET_URL=http://localhost:17990 API_URL=http://localhost:15000 \
#   BITBUCKET_USER=svc-devops-tashtiot BITBUCKET_PASS=<ldap-bind-password> \
#   ADMIN_USER=admin \
#   pytest tests/v1/bitbucket/test_bitbucket_project_e2e.py -v -m integration
BITBUCKET_URL = os.environ.get("BITBUCKET_URL", "http://localhost:7990")
API_URL = os.environ.get("API_URL", "http://localhost:5002")
PREFIX = "/api/devops/v1/bitbucket"
BITBUCKET_USER = os.environ.get("BITBUCKET_USER", "nati")
BITBUCKET_PASS = os.environ.get("BITBUCKET_PASS", "12345678")

PROJECT_KEY = os.environ.get("E2E_PROJECT_KEY", "E2ETEST")
PROJECT_NAME = "e2etest"
# admin_user schema pattern is ^[a-z0-9]+$ (lowercase alphanumeric only, no hyphens) —
# BITBUCKET_USER itself often won't match (e.g. "svc-devops-tashtiot"), so this needs its
# own override rather than reusing BITBUCKET_USER.
ADMIN_USER = os.environ.get("E2E_ADMIN_USER", "nati")
# Must be a group that already exists in Bitbucket (this suite never creates one) and match
# admin_group's schema pattern ^[a-zA-Z0-9_\-]+$ (no spaces) — most built-in AD groups
# (e.g. "Domain Users") fail that pattern, so this needs an explicit, repo-safe default.
ADMIN_GROUP = os.environ.get("E2E_ADMIN_GROUP", "devops-tashtiot")

REPO_PROJECT_KEY = os.environ.get("E2E_REPO_PROJECT_KEY", "E2EREPOTEST")
REPO_SLUG = "e2e-test-repo"

REQUEST_METADATA = {
    "project": "devops-api-e2e",
    "network": "test",
    "region": "test",
    "space": "test",
    "environment": "test",
}


@pytest.fixture(scope="module")
def bb():
    with httpx.Client(base_url=BITBUCKET_URL, auth=(BITBUCKET_USER, BITBUCKET_PASS), timeout=30.0) as client:
        yield client


# devops-api itself now requires a Bearer token (tashtiot-apis-library's inbound auth,
# AUTH_ENABLED=true in the live deployment) — mint one via client_credentials against the
# durable devops-api-e2e-tests Keycloak client (clusters-provision/clusters/rhbk). Falls back
# to no Authorization header if the secret isn't set (e.g. a local AUTH_ENABLED=false stack).
E2E_TOKEN_URL = os.environ.get("E2E_KEYCLOAK_TOKEN_URL", "https://rhbk.devopstashtiot.page/realms/devtools/protocol/openid-connect/token")
E2E_CLIENT_ID = os.environ.get("E2E_KEYCLOAK_CLIENT_ID", "devops-api-e2e-tests")
E2E_CLIENT_SECRET = os.environ.get("E2E_KEYCLOAK_CLIENT_SECRET", "")


def _api_auth_headers() -> dict:
    if not E2E_CLIENT_SECRET:
        return {}
    resp = httpx.post(
        E2E_TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": E2E_CLIENT_ID,
            "client_secret": E2E_CLIENT_SECRET,
            "scope": "devops-api-audience",
        },
        timeout=10.0,
    )
    resp.raise_for_status()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture(scope="module")
def api():
    with httpx.Client(base_url=API_URL, timeout=30.0, headers=_api_auth_headers()) as client:
        yield client


def _delete_project_if_exists(bb: httpx.Client, key: str):
    repos = bb.get(f"/rest/api/latest/projects/{key}/repos")
    if repos.status_code == 200:
        for repo in repos.json().get("values", []):
            bb.delete(f"/rest/api/latest/projects/{key}/repos/{repo['slug']}")
    bb.delete(f"/rest/api/latest/projects/{key}")


def _project_exists(bb: httpx.Client, key: str) -> bool:
    return bb.get(f"/rest/api/latest/projects/{key}").status_code == 200


def _get_project_user_permission(bb: httpx.Client, key: str, username: str) -> str | None:
    r = bb.get(f"/rest/api/latest/projects/{key}/permissions/users")
    assert r.status_code == 200
    for entry in r.json().get("values", []):
        if entry["user"]["name"] == username:
            return entry["permission"]
    return None


def _get_project_group_permission(bb: httpx.Client, key: str, group_name: str) -> str | None:
    r = bb.get(f"/rest/api/latest/projects/{key}/permissions/groups")
    assert r.status_code == 200
    for entry in r.json().get("values", []):
        if entry["group"]["name"] == group_name:
            return entry["permission"]
    return None


def _repo_exists(bb: httpx.Client, key: str, repo_slug: str) -> bool:
    return bb.get(f"/rest/api/latest/projects/{key}/repos/{repo_slug}").status_code == 200


@pytest.mark.integration
def test_create_assign_and_delete_project(bb, api):
    # --- clean state ---
    _delete_project_if_exists(bb, PROJECT_KEY)
    assert not _project_exists(bb, PROJECT_KEY)

    # --- create project via our API ---
    r = api.post(f"{PREFIX}/", json={
        "metadata": REQUEST_METADATA,
        "spec": {
            "key": PROJECT_KEY,
            "name": PROJECT_NAME,
            "description": "End-to-end test project",
            "public": False,
            "admin_user": ADMIN_USER,
        },
    })
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "successful"

    # --- verify project exists in Bitbucket ---
    assert _project_exists(bb, PROJECT_KEY)

    # --- verify admin permission assigned ---
    permission = _get_project_user_permission(bb, PROJECT_KEY, ADMIN_USER)
    assert permission == "PROJECT_ADMIN", f"Expected PROJECT_ADMIN, got {permission}"

    # --- delete project via our API ---
    r = api.delete(f"{PREFIX}/{PROJECT_KEY}")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "successful"

    # --- verify project is gone ---
    assert not _project_exists(bb, PROJECT_KEY)


@pytest.mark.integration
def test_create_assign_group_and_delete_project(bb, api):
    # --- clean state ---
    _delete_project_if_exists(bb, PROJECT_KEY)
    assert not _project_exists(bb, PROJECT_KEY)

    # --- create project via our API with admin_group instead of admin_user ---
    r = api.post(f"{PREFIX}/", json={
        "metadata": REQUEST_METADATA,
        "spec": {
            "key": PROJECT_KEY,
            "name": PROJECT_NAME,
            "description": "End-to-end test project (group admin)",
            "public": False,
            "admin_group": ADMIN_GROUP,
        },
    })
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "successful"

    assert _project_exists(bb, PROJECT_KEY)

    permission = _get_project_group_permission(bb, PROJECT_KEY, ADMIN_GROUP)
    assert permission == "PROJECT_ADMIN", f"Expected PROJECT_ADMIN, got {permission}"

    # --- delete project via our API ---
    r = api.delete(f"{PREFIX}/{PROJECT_KEY}")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "successful"

    assert not _project_exists(bb, PROJECT_KEY)


@pytest.mark.integration
def test_delete_project_cascades_repo_deletion(bb, api):
    # Bitbucket refuses DELETE /projects/{key} with 409 IntegrityException whenever the
    # project still has a repo inside it (confirmed live — see app/v1/bitbucket/CLAUDE.md).
    # delete_project must delete every repo under the project first so this endpoint can
    # actually delete a real, populated project rather than only ever an empty one.
    _delete_project_if_exists(bb, REPO_PROJECT_KEY)
    assert not _project_exists(bb, REPO_PROJECT_KEY)

    # --- create project via our API ---
    r = api.post(f"{PREFIX}/", json={
        "metadata": REQUEST_METADATA,
        "spec": {
            "key": REPO_PROJECT_KEY,
            "name": REPO_PROJECT_KEY.lower(),
            "description": "End-to-end test project with a repo",
            "public": False,
            "admin_user": ADMIN_USER,
        },
    })
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "successful"

    # --- create a repo inside it directly against Bitbucket (devops-api has no repo-create
    #     route — repos here stand in for ones created by other means, e.g. Bitbucket's own UI) ---
    r = bb.post(f"/rest/api/latest/projects/{REPO_PROJECT_KEY}/repos", json={"name": REPO_SLUG, "scmId": "git"})
    assert r.status_code == 201, r.text
    assert _repo_exists(bb, REPO_PROJECT_KEY, REPO_SLUG)

    # --- delete the project via our API — must cascade-delete the repo instead of 409ing ---
    r = api.delete(f"{PREFIX}/{REPO_PROJECT_KEY}")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "successful"

    # --- verify both the repo and the project are actually gone ---
    assert not _repo_exists(bb, REPO_PROJECT_KEY, REPO_SLUG)
    assert not _project_exists(bb, REPO_PROJECT_KEY)


@pytest.mark.integration
def test_list_user_directories(bb, api):
    # --- list via our API ---
    r = api.get(f"{PREFIX}/user-dirs")
    assert r.status_code == 200, r.text
    directories = r.json()
    assert isinstance(directories, list)
    assert len(directories) > 0, "Bitbucket has no configured user directories"

    # --- cross-check against Bitbucket directly (same Crowd-embedded resource) ---
    direct = bb.get("/rest/crowd/latest/directory", headers={"Accept": "application/json"})
    assert direct.status_code == 200, direct.text
    direct_names = {d["name"] for d in direct.json()["directory"]}
    api_names = {d["name"] for d in directories}
    assert api_names == direct_names


@pytest.mark.integration
def test_sync_user_directory_returns_not_supported(api):
    # Bitbucket Data Center has no supported REST API to trigger a directory sync on demand —
    # confirmed by live investigation (see app/v1/bitbucket/CLAUDE.md). This must return 501,
    # not attempt any call to Bitbucket that could report a false success.
    r = api.post(f"{PREFIX}/user-dirs/sync")
    assert r.status_code == 501, r.text
    assert r.json()["status"] == "Failed"
