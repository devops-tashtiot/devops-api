import httpx
import pytest

BITBUCKET_URL = "http://localhost:7990"
API_URL = "http://localhost:5002"
PREFIX = "/api/devops/v1/bitbucket"
BITBUCKET_USER = "nati"
BITBUCKET_PASS = "12345678"

PROJECT_KEY = "E2ETEST"
PROJECT_NAME = "e2e-test"
ADMIN_USER = "nati"


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
        "key": PROJECT_KEY,
        "name": PROJECT_NAME,
        "description": "End-to-end test project",
        "public": False,
        "admin_user": ADMIN_USER,
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
