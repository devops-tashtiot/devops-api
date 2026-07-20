import os

import httpx
import pytest

# All overridable via env vars so this file can run against either a local Jira instance or
# a real deployed environment — e.g. against this platform's cluster via `kubectl port-forward`:
#   kubectl -n jira port-forward svc/jira 18080:80
#   kubectl -n devops-api port-forward svc/devops-api 15000:5000
#   JIRA_URL=http://localhost:18080 API_URL=http://localhost:15000 \
#   JIRA_USER=admin JIRA_PASS=<password> \
#   pytest tests/v1/jira/test_jira_e2e.py -v -m integration
JIRA_URL = os.environ.get("JIRA_URL", "http://localhost:8080")
API_URL = os.environ.get("API_URL", "http://localhost:5002")
PREFIX = "/api/devops/v1/jira"
JIRA_USER = os.environ.get("JIRA_USER", "admin")
JIRA_PASS = os.environ.get("JIRA_PASS", "12345678")

PROJECT_KEY = os.environ.get("E2E_PROJECT_KEY", "E2ETEST")
PROJECT_NAME = "e2etest"
# admin_user schema pattern is ^[a-z0-9_\-]+$ — Jira unconditionally requires this as the
# project lead (see app/v1/jira/CLAUDE.md); there is no admin_group-only path to test here.
ADMIN_USER = os.environ.get("E2E_ADMIN_USER", "admin")
# Must be a group that already exists in Jira (this suite never creates one).
ADMIN_GROUP = os.environ.get("E2E_ADMIN_GROUP", "devops-tashtiot")

REQUEST_METADATA = {
    "project": "devops-api-e2e",
    "network": "test",
    "region": "test",
    "space": "test",
    "environment": "test",
}


@pytest.fixture(scope="module")
def jira():
    with httpx.Client(base_url=JIRA_URL, auth=(JIRA_USER, JIRA_PASS), timeout=30.0) as client:
        yield client


@pytest.fixture(scope="module")
def api():
    with httpx.Client(base_url=API_URL, timeout=30.0) as client:
        yield client


def _delete_project_if_exists(jira: httpx.Client, key: str):
    jira.delete(f"/rest/api/latest/project/{key}")


def _project_exists(jira: httpx.Client, key: str) -> bool:
    return jira.get(f"/rest/api/latest/project/{key}").status_code == 200


def _get_role_actors(jira: httpx.Client, key: str) -> list[tuple[str, str]]:
    r = jira.get(f"/rest/api/latest/project/{key}/role/10002")
    assert r.status_code == 200
    return [(a["name"], a["type"]) for a in r.json().get("actors", [])]


@pytest.fixture
def clean_project(jira):
    # Setup + teardown via yield, not a plain function call at the top of each test body — if
    # an earlier assertion in the test fails (e.g. the CAPTCHA lockout incident), the test
    # aborts right there and a plain call never reaches the cleanup at the bottom, leaving the
    # project behind in real Jira. yield-based teardown still runs even on failure.
    _delete_project_if_exists(jira, PROJECT_KEY)
    yield PROJECT_KEY
    _delete_project_if_exists(jira, PROJECT_KEY)


@pytest.fixture
def clean_nonexistent_user_project(jira):
    # Same reasoning as clean_project — this test expects Jira to reject the create outright,
    # but if that expectation is ever wrong, the fixture's teardown still cleans up the project
    # rather than relying on an assertion that already failed to also run the cleanup after it.
    key = os.environ.get("E2E_NONEXISTENT_USER_PROJECT_KEY", "E2ENOUSR")
    _delete_project_if_exists(jira, key)
    yield key
    _delete_project_if_exists(jira, key)


@pytest.mark.integration
def test_create_assign_and_delete_project(jira, api, clean_project):
    # --- clean state ---
    assert not _project_exists(jira, PROJECT_KEY)

    # --- create project via our API ---
    r = api.post(f"{PREFIX}/", json={
        "metadata": REQUEST_METADATA,
        "spec": {
            "key": PROJECT_KEY,
            "name": PROJECT_NAME,
            "description": "End-to-end test project",
            "admin_user": ADMIN_USER,
        },
    })
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "successful"

    # --- verify project exists and lead was set ---
    assert _project_exists(jira, PROJECT_KEY)
    project = jira.get(f"/rest/api/latest/project/{PROJECT_KEY}").json()
    assert project["lead"]["name"] == ADMIN_USER

    # --- verify admin role (10002) assignment ---
    actors = _get_role_actors(jira, PROJECT_KEY)
    assert (ADMIN_USER, "atlassian-user-role-actor") in actors

    # --- delete project via our API ---
    r = api.delete(f"{PREFIX}/{PROJECT_KEY}")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "successful"

    # --- verify project is gone — Jira's delete is immediately synchronous, confirmed live
    #     (unlike Confluence's space delete, there is no accepted-but-not-yet-gone race here) ---
    assert not _project_exists(jira, PROJECT_KEY)


@pytest.mark.integration
def test_create_with_admin_group_also_assigns_group_role(jira, api, clean_project):
    # admin_group is optional and additive — admin_user (the required lead) still gets the
    # role, and admin_group gets it too.
    assert not _project_exists(jira, PROJECT_KEY)

    r = api.post(f"{PREFIX}/", json={
        "metadata": REQUEST_METADATA,
        "spec": {
            "key": PROJECT_KEY,
            "name": PROJECT_NAME,
            "description": "End-to-end test project (group admin)",
            "admin_user": ADMIN_USER,
            "admin_group": ADMIN_GROUP,
        },
    })
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "successful"

    actors = _get_role_actors(jira, PROJECT_KEY)
    assert (ADMIN_USER, "atlassian-user-role-actor") in actors
    assert (ADMIN_GROUP, "atlassian-group-role-actor") in actors

    r = api.delete(f"{PREFIX}/{PROJECT_KEY}")
    assert r.status_code == 200, r.text
    assert not _project_exists(jira, PROJECT_KEY)


@pytest.mark.integration
def test_create_project_group_only_rejected(api):
    # Jira has no concept of a group-led project — confirmed live (see app/v1/jira/CLAUDE.md):
    # admin_user is a required field, so a group-only request never reaches Jira at all.
    r = api.post(f"{PREFIX}/", json={
        "metadata": REQUEST_METADATA,
        "spec": {
            "key": PROJECT_KEY,
            "name": PROJECT_NAME,
            "description": "should be rejected before hitting Jira",
            "admin_group": ADMIN_GROUP,
        },
    })
    assert r.status_code == 422, r.text


@pytest.mark.integration
def test_create_project_nonexistent_admin_user_rejected(jira, api, clean_nonexistent_user_project):
    key = clean_nonexistent_user_project
    assert not _project_exists(jira, key)

    r = api.post(f"{PREFIX}/", json={
        "metadata": REQUEST_METADATA,
        "spec": {
            "key": key,
            "name": "e2e-nonexistent-admin",
            "description": "Should be rejected by Jira — lead does not exist",
            "admin_user": "definitely-not-a-real-jira-user",
        },
    })

    assert r.status_code >= 400, r.text
    assert r.json()["status"] == "Failed"
    assert not _project_exists(jira, key)


@pytest.mark.integration
def test_delete_project_twice_second_returns_404(jira, api, clean_project):
    # Idempotency check: deleting an already-deleted project should cleanly 404, not crash or
    # silently report success — currently only tested against a project that never existed at
    # all (test_delete_nonexistent_project_returns_404); this covers the "just deleted it"
    # variant instead.
    assert not _project_exists(jira, PROJECT_KEY)

    r = api.post(f"{PREFIX}/", json={
        "metadata": REQUEST_METADATA,
        "spec": {
            "key": PROJECT_KEY,
            "name": PROJECT_NAME,
            "description": "Idempotent delete test",
            "admin_user": ADMIN_USER,
        },
    })
    assert r.status_code == 200, r.text
    assert _project_exists(jira, PROJECT_KEY)

    # --- first delete: project exists, succeeds ---
    r = api.delete(f"{PREFIX}/{PROJECT_KEY}")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "successful"
    assert not _project_exists(jira, PROJECT_KEY)

    # --- second delete: already gone, must 404 cleanly ---
    r = api.delete(f"{PREFIX}/{PROJECT_KEY}")
    assert r.status_code == 404, r.text
    assert r.json()["status"] == "Failed"


@pytest.mark.integration
def test_delete_nonexistent_project_returns_404(jira, api):
    key = os.environ.get("E2E_NEVER_CREATED_PROJECT_KEY", "E2ENEVER")
    assert not _project_exists(jira, key)

    r = api.delete(f"{PREFIX}/{key}")
    assert r.status_code == 404, r.text
    assert r.json()["status"] == "Failed"


@pytest.mark.integration
def test_list_user_directories(jira, api):
    # --- list via our API ---
    r = api.get(f"{PREFIX}/user-dirs")
    assert r.status_code == 200, r.text
    directories = r.json()
    assert isinstance(directories, list)
    assert len(directories) > 0, "Jira has no configured user directories"

    # --- cross-check against Jira directly (same Crowd-embedded resource) ---
    direct = jira.get("/rest/crowd/latest/directory", headers={"Accept": "application/json"})
    assert direct.status_code == 200, direct.text
    direct_names = {d["name"] for d in direct.json()["directories"]}
    api_names = {d["name"] for d in directories}
    assert api_names == direct_names


@pytest.mark.integration
def test_sync_user_directory_returns_not_supported(api):
    # Jira has no supported REST API to trigger a directory sync on demand — confirmed live:
    # POST /rest/crowd/latest/directory/{id}/synchronise 404s even with the correct LDAP
    # directory id (see app/v1/jira/CLAUDE.md). Must return 501, never a false "successful".
    r = api.post(f"{PREFIX}/user-dirs/sync")
    assert r.status_code == 501, r.text
    assert r.json()["status"] == "Failed"
