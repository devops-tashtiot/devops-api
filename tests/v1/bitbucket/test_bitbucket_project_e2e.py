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


@pytest.fixture(scope="module")
def api():
    with httpx.Client(base_url=API_URL, timeout=30.0) as client:
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
