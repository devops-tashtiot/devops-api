import os

import httpx
import pytest

# All overridable via env vars so this file can run against either the local docker-compose
# stack (defaults below) or a real deployed environment.
SONARQUBE_URL = os.environ.get("SONARQUBE_URL", "http://localhost:9000")
API_URL = os.environ.get("API_URL", "http://localhost:5001")
PREFIX = "/api/devops/v1/sonarqube"
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "SonarqubeDevops1!")
GROUP_NAME = "e2e-admin-group"
CONSUMER_NAME = "netanel"

# POST / expects SonarQubeGroupRequest (an OperationRequest subclass) — a flat
# {"consumer_name": ..., "name": ...} body was never valid against this schema, it needs to be
# wrapped as {"metadata": {...}, "spec": {"consumer_name": ..., "name": ...}}, same shape every
# other module's e2e test already sends (see test_sonarqube_consumer_e2e.py's REQUEST_METADATA).
REQUEST_METADATA = {
    "project": "devops-api-e2e",
    "network": "test",
    "region": "test",
    "space": "test",
    "environment": "test",
}

EXPECTED_GLOBAL_PERMISSIONS = {"admin", "gateadmin", "profileadmin", "provisioning", "scan"}
EXPECTED_TEMPLATE_PERMISSIONS = {"user", "codeviewer", "issueadmin", "securityhotspotadmin", "admin", "scan"}


@pytest.fixture(scope="module")
def sonar():
    with httpx.Client(
        base_url=SONARQUBE_URL,
        auth=(ADMIN_USER, ADMIN_PASS),
        timeout=30.0,
    ) as client:
        yield client


@pytest.fixture(scope="module")
def api():
    with httpx.Client(base_url=API_URL, timeout=30.0) as client:
        yield client


def _delete_group_if_exists(sonar: httpx.Client, name: str):
    r = sonar.post("/api/user_groups/delete", params={"name": name})
    # 204 = deleted, 404 = did not exist — both are fine
    assert r.status_code in (204, 404)


def _get_global_permissions_for_group(sonar: httpx.Client, name: str) -> set:
    permissions = set()
    for perm in EXPECTED_GLOBAL_PERMISSIONS:
        r = sonar.get("/api/permissions/groups", params={"permission": perm})
        assert r.status_code == 200
        groups = [g["name"] for g in r.json().get("groups", [])]
        if name in groups:
            permissions.add(perm)
    return permissions


def _get_template_permissions_for_group(sonar: httpx.Client, name: str) -> set:
    r = sonar.get(
        "/api/permissions/template_groups",
        params={"templateName": "Default template"},
    )
    assert r.status_code == 200
    permissions = set()
    for entry in r.json().get("groups", []):
        if entry["name"] == name:
            permissions.update(entry.get("permissions", []))
    return permissions


@pytest.mark.integration
def test_create_and_delete_group_full_flow(sonar, api):
    # --- clean state ---
    _delete_group_if_exists(sonar, GROUP_NAME)

    r = sonar.get("/api/user_groups/search", params={"q": GROUP_NAME})
    assert r.status_code == 200
    assert r.json()["paging"]["total"] == 0

    # --- create group via our API ---
    r = api.post(
        f"{PREFIX}/",
        json={
            "metadata": REQUEST_METADATA,
            "spec": {"consumer_name": CONSUMER_NAME, "name": GROUP_NAME},
        },
    )
    assert r.status_code == 200
    assert r.json()["status"] == "successful"

    # --- verify group exists ---
    r = sonar.get("/api/user_groups/search", params={"q": GROUP_NAME})
    assert r.status_code == 200
    assert r.json()["paging"]["total"] == 1
    assert r.json()["groups"][0]["name"] == GROUP_NAME

    # --- verify global permissions ---
    assigned_global = _get_global_permissions_for_group(sonar, GROUP_NAME)
    assert assigned_global == EXPECTED_GLOBAL_PERMISSIONS, (
        f"Missing global permissions: {EXPECTED_GLOBAL_PERMISSIONS - assigned_global}"
    )

    # --- verify template permissions ---
    assigned_template = _get_template_permissions_for_group(sonar, GROUP_NAME)
    assert assigned_template == EXPECTED_TEMPLATE_PERMISSIONS, (
        f"Missing template permissions: {EXPECTED_TEMPLATE_PERMISSIONS - assigned_template}"
    )

    # --- delete group via our API ---
    r = api.delete(f"{PREFIX}/{CONSUMER_NAME}/{GROUP_NAME}")
    assert r.status_code == 200
    assert r.json()["status"] == "successful"

    # --- verify group is gone ---
    r = sonar.get("/api/user_groups/search", params={"q": GROUP_NAME})
    assert r.status_code == 200
    assert r.json()["paging"]["total"] == 0
