"""
End-to-end integration test for the Confluence space export + import flow.

Requires:
  - Confluence running at http://localhost:8090 (admin / 12345678)
  - MinIO running at http://localhost:9100 (confluence-space-imports bucket public-write)
  - FastAPI server running at http://localhost:5001

Run with: pytest tests/v1/confluence/test_confluence_export_import_e2e.py -v -m integration
"""
import time
import uuid

import httpx
import pytest

CONFLUENCE_URL = "http://localhost:8090"
API_URL = "http://localhost:5001"
API_PREFIX = "/api/devops/v1/confluence"
AUTH = ("admin", "12345678")
SPACE_KEY = "NATTEST"
SPACE_NAME = "Nati Integration Test Space"
ADMIN_USER = "nati"
ATTACHMENT_CONTENT = b"random attachment content for e2e test"
ATTACHMENT_NAME = "test-file.txt"


@pytest.fixture(scope="module")
def confluence():
    return httpx.Client(base_url=CONFLUENCE_URL, auth=AUTH, timeout=30)


@pytest.fixture(scope="module")
def api():
    return httpx.Client(base_url=API_URL, timeout=120)


def _wait_for_confluence(confluence: httpx.Client):
    for _ in range(30):
        try:
            r = confluence.get("/rest/api/latest/space")
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(2)
    pytest.skip("Confluence not reachable")


def _wait_for_api(api: httpx.Client):
    for _ in range(10):
        try:
            r = api.get(f"{API_PREFIX}/user-dirs")
            if r.status_code < 500:
                return
        except Exception:
            pass
        time.sleep(1)
    pytest.skip("FastAPI server not reachable")


def _ensure_user(confluence: httpx.Client, username: str):
    r = confluence.get(f"/rest/api/latest/user?username={username}")
    if r.status_code == 200:
        return
    r = confluence.post(
        "/rest/api/latest/admin/user",
        json={
            "userName": username,
            "password": "Password1!",
            "email": f"{username}@example.com",
            "fullName": username.capitalize(),
        },
    )
    assert r.status_code in (200, 201), f"Failed to create user {username}: {r.text}"


def _delete_space_if_exists(confluence: httpx.Client, space_key: str):
    r = confluence.get(f"/rest/api/latest/space/{space_key}")
    if r.status_code == 404:
        return
    r = confluence.delete(f"/rest/api/latest/space/{space_key}")
    assert r.status_code == 202, f"Failed to delete space {space_key}: {r.text}"
    for _ in range(30):
        if confluence.get(f"/rest/api/latest/space/{space_key}").status_code == 404:
            return
        time.sleep(1)
    pytest.fail(f"Space {space_key} was not deleted within 30s")


@pytest.mark.integration
def test_export_import_full_flow(confluence, api):
    _wait_for_confluence(confluence)
    _wait_for_api(api)

    # --- setup: clean state ---
    _delete_space_if_exists(confluence, SPACE_KEY)
    _ensure_user(confluence, ADMIN_USER)

    # --- step 1: create space via our API with admin_user=nati ---
    r = api.post(f"{API_PREFIX}/", json={
        "key": SPACE_KEY,
        "name": SPACE_NAME,
        "description": "Integration test space",
        "admin_user": ADMIN_USER,
    })
    assert r.status_code == 200, f"Space creation failed: {r.text}"
    assert r.json()["status"] == "successful"

    # --- step 2: create a page in the space ---
    r = confluence.post("/rest/api/latest/content", json={
        "type": "page",
        "title": "E2E Test Page",
        "space": {"key": SPACE_KEY},
        "body": {"storage": {"value": "<p>Integration test content</p>", "representation": "storage"}},
    })
    assert r.status_code == 200, f"Page creation failed: {r.text}"
    page_id = r.json()["id"]

    # --- step 3: attach a random file to the page ---
    r = confluence.post(
        f"/rest/api/latest/content/{page_id}/child/attachment",
        files={"file": (ATTACHMENT_NAME, ATTACHMENT_CONTENT, "text/plain")},
        headers={"X-Atlassian-Token": "no-check"},
    )
    assert r.status_code == 200, f"Attachment upload failed: {r.text}"
    attachment_title = r.json()["results"][0]["title"]
    assert attachment_title == ATTACHMENT_NAME

    # --- step 4: export the space via our API → lands in MinIO ---
    r = api.post(f"{API_PREFIX}/space-export/", json={"space_key": SPACE_KEY})
    assert r.status_code == 200, f"Space export failed: {r.text}"
    assert r.json()["status"] == "successful"
    archive_name = r.json()["archive_name"]
    assert archive_name.endswith(".zip"), f"Unexpected archive_name: {archive_name}"

    # --- step 5: verify the archive is actually in MinIO ---
    r = httpx.get(f"http://localhost:9100/platform-clients/confluence-space-imports/{archive_name}", timeout=10)
    assert r.status_code == 200, f"Archive not found in MinIO: {archive_name}"
    assert len(r.content) > 0

    # --- step 6: delete the space ---
    _delete_space_if_exists(confluence, SPACE_KEY)
    r = confluence.get(f"/rest/api/latest/space/{SPACE_KEY}")
    assert r.status_code == 404, "Space should be gone before import"

    # --- step 7: import the space via our API ---
    r = api.post(f"{API_PREFIX}/space-import/", json={
        "space_key": SPACE_KEY,
        "archive_name": archive_name,
    })
    assert r.status_code == 200, f"Space import failed: {r.text}"
    assert r.json()["status"] == "successful"

    # --- step 8: verify space is back with its page and attachment ---
    r = confluence.get(f"/rest/api/latest/space/{SPACE_KEY}")
    assert r.status_code == 200, "Space not found after import"
    assert r.json()["name"] == SPACE_NAME

    r = confluence.get(f"/rest/api/latest/content?spaceKey={SPACE_KEY}&type=page")
    pages = r.json()["results"]
    assert any(p["title"] == "E2E Test Page" for p in pages), "Test page not restored"

    page_id_restored = next(p["id"] for p in pages if p["title"] == "E2E Test Page")
    r = confluence.get(f"/rest/api/latest/content/{page_id_restored}/child/attachment")
    attachments = r.json()["results"]
    assert any(a["title"] == ATTACHMENT_NAME for a in attachments), "Attachment not restored"
