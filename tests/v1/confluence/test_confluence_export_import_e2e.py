"""
End-to-end integration tests for Confluence's live REST surface via devops-api.

These hit a REAL Confluence instance and a REAL devops-api — no mocks. Every request payload
uses the metadata/spec wrapper OperationRequest actually requires (the previous version of
this file omitted it entirely and would have 422'd on its very first call had it ever been run).

Requires a real Confluence + devops-api reachable at CONFLUENCE_URL / API_URL. Defaults target
the local docker-compose stack (see app/v1/confluence/CLAUDE.md's "Local dev" section);
override via env vars to point at a real deployed environment instead — e.g. this platform's
cluster via `kubectl port-forward`:

    kubectl -n confluence port-forward svc/confluence 18090:80
    kubectl -n devops-api port-forward svc/devops-api 15000:5000
    CONFLUENCE_URL=http://localhost:18090 API_URL=http://localhost:15000 \\
    CONFLUENCE_USER=svc-devops-tashtiot CONFLUENCE_PASS=<ldap-bind-password> \\
    E2E_ADMIN_USER=svc-devops-tashtiot \\
    pytest tests/v1/confluence/test_confluence_export_import_e2e.py -v -m integration

Note: plugin install requires Confluence's UPM upload to be enabled
(-Dupm.plugin.upload.enabled=true, see devtools-definition/devtools/confluence/values.yaml)
— it's disabled by default in Confluence Data Center and 403s otherwise.
"""
import base64
import io
import os
import time
import zipfile

import httpx
import pytest

CONFLUENCE_URL = os.environ.get("CONFLUENCE_URL", "http://localhost:8090")
API_URL = os.environ.get("API_URL", "http://localhost:5001")
MINIO_URL = os.environ.get("MINIO_URL", "http://localhost:9100")
API_PREFIX = "/api/devops/v1/confluence"
CONFLUENCE_USER = os.environ.get("CONFLUENCE_USER", "admin")
CONFLUENCE_PASS = os.environ.get("CONFLUENCE_PASS", "12345678")
# admin_user schema pattern is ^[a-z0-9_\-]+$ — pick an account that actually exists on the
# target Confluence and matches that pattern.
ADMIN_USER = os.environ.get("E2E_ADMIN_USER", "admin")

SPACE_KEY = os.environ.get("E2E_SPACE_KEY", "E2ETEST")
SPACE_NAME = "E2E Test Space"
ATTACHMENT_CONTENT = b"random attachment content for e2e test"
ATTACHMENT_NAME = "test-file.txt"

PLUGIN_KEY = "com.example.e2e-verify-plugin"
PLUGIN_NAME = "e2e-verify-plugin.jar"

REQUEST_METADATA = {
    "project": "devops-api-e2e",
    "network": "test",
    "region": "test",
    "space": "test",
    "environment": "test",
}


def _build_minimal_plugin_jar() -> bytes:
    """A minimal but valid Atlassian OSGi plugin: a descriptor with no functional modules —
    installable, but does nothing. No compiled Java/build toolchain needed."""
    manifest = (
        "Manifest-Version: 1.0\n"
        "Bundle-ManifestVersion: 2\n"
        f"Bundle-SymbolicName: {PLUGIN_KEY}\n"
        "Bundle-Version: 1.0.0\n"
        "Bundle-Name: E2E Verify Plugin\n"
    )
    descriptor = (
        f'<atlassian-plugin key="{PLUGIN_KEY}" name="E2E Verify Plugin" plugins-version="2">\n'
        "    <plugin-info>\n"
        "        <description>Minimal no-op plugin for devops-api e2e verification</description>\n"
        "        <version>1.0.0</version>\n"
        '        <vendor name="E2E Test" url="https://example.com"/>\n'
        "    </plugin-info>\n"
        "</atlassian-plugin>\n"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as jar:
        jar.writestr("META-INF/MANIFEST.MF", manifest)
        jar.writestr("atlassian-plugin.xml", descriptor)
    return buf.getvalue()


@pytest.fixture(scope="module")
def confluence():
    return httpx.Client(base_url=CONFLUENCE_URL, auth=(CONFLUENCE_USER, CONFLUENCE_PASS), timeout=30)


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
    pytest.skip("devops-api not reachable")


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
    assert 200 <= r.status_code < 300, f"Failed to delete space {space_key}: {r.text}"
    for _ in range(30):
        if confluence.get(f"/rest/api/latest/space/{space_key}").status_code == 404:
            return
        time.sleep(1)
    pytest.fail(f"Space {space_key} was not deleted within 30s")


def _uninstall_plugin_if_present(confluence: httpx.Client, plugin_key: str):
    r = confluence.get(f"/rest/plugins/1.0/{plugin_key}-key")
    if r.status_code == 404:
        return
    confluence.delete(f"/rest/plugins/1.0/{plugin_key}-key")


@pytest.mark.integration
def test_create_and_delete_space(confluence, api):
    _wait_for_confluence(confluence)
    _wait_for_api(api)
    _ensure_user(confluence, ADMIN_USER)
    _delete_space_if_exists(confluence, SPACE_KEY)

    r = api.post(f"{API_PREFIX}/", json={
        "metadata": REQUEST_METADATA,
        "spec": {
            "key": SPACE_KEY,
            "name": SPACE_NAME,
            "description": "E2E create/delete test space",
            "admin_user": ADMIN_USER,
        },
    })
    assert r.status_code == 200, f"Space creation failed: {r.text}"
    assert r.json()["status"] == "successful"

    r = confluence.get(f"/rest/api/latest/space/{SPACE_KEY}")
    assert r.status_code == 200, "Space not found after create"

    r = confluence.get(f"/rest/api/latest/space/{SPACE_KEY}/permissions")
    admin_ops = {
        p["operation"]["operationKey"]
        for p in r.json()
        if p["subject"].get("type") == "user" and p["operation"]["operationKey"] == "administer"
    }
    assert "administer" in admin_ops, "admin_user was not granted administer permission"

    # DELETE /{key} polls Confluence until the space actually 404s before returning
    # "successful" (Confluence's own DELETE only accepts the request asynchronously) — assert
    # it's really gone immediately after devops-api reports success, not just eventually.
    r = api.delete(f"{API_PREFIX}/{SPACE_KEY}")
    assert r.status_code == 200, f"Space deletion failed: {r.text}"
    assert r.json()["status"] == "successful"

    r = confluence.get(f"/rest/api/latest/space/{SPACE_KEY}")
    assert r.status_code == 404, "Space still exists immediately after a \"successful\" delete"


@pytest.mark.integration
def test_list_user_directories(confluence, api):
    _wait_for_confluence(confluence)
    _wait_for_api(api)

    r = api.get(f"{API_PREFIX}/user-dirs")
    assert r.status_code == 200, r.text
    directories = r.json()
    assert isinstance(directories, list)
    assert len(directories) > 0

    direct = confluence.get("/rest/crowd/latest/directory", headers={"Accept": "application/json"})
    assert direct.status_code == 200
    assert {d["name"] for d in directories} == {d["name"] for d in direct.json()["directory"]}


@pytest.mark.integration
def test_sync_user_directory_returns_not_supported(api):
    # Confluence has no supported REST API to trigger a directory sync on demand — confirmed
    # live: POST /rest/crowd/latest/directory/{id}/synchronise 404s even with a correct
    # connector directory ID (see app/v1/bitbucket/CLAUDE.md for the shared investigation with
    # Bitbucket, same root cause). Must return 501, never a false "successful".
    _wait_for_api(api)
    r = api.post(f"{API_PREFIX}/user-dirs/sync")
    assert r.status_code == 501, r.text
    assert r.json()["status"] == "Failed"


@pytest.mark.integration
def test_plugin_upload_install_uninstall_flow(confluence, api):
    _wait_for_confluence(confluence)
    _wait_for_api(api)
    _uninstall_plugin_if_present(confluence, PLUGIN_KEY)

    jar_bytes = _build_minimal_plugin_jar()
    file_content = base64.b64encode(jar_bytes).decode()

    # --- step 1: upload the jar to MinIO via our API ---
    r = api.post(f"{API_PREFIX}/plugin/upload", json={
        "metadata": REQUEST_METADATA,
        "spec": {"plugin_name": PLUGIN_NAME, "file_content": file_content},
    })
    assert r.status_code == 200, f"Plugin upload failed: {r.text}"
    assert r.json()["status"] == "successful"

    # --- step 2: verify it's actually in MinIO ---
    r = httpx.get(f"{MINIO_URL}/platform-clients/confluence-plugins/{PLUGIN_NAME}", timeout=10)
    assert r.status_code == 200, f"Plugin jar not found in MinIO: {PLUGIN_NAME}"
    assert r.content == jar_bytes

    # --- step 3: install it into Confluence via our API ---
    r = api.post(f"{API_PREFIX}/plugin/", json={
        "metadata": REQUEST_METADATA,
        "spec": {"plugin_name": PLUGIN_NAME},
    })
    assert r.status_code == 200, (
        f"Plugin install failed: {r.text}. If this 403s with "
        "\"Plugins cannot be installed via upload\", Confluence's UPM upload is disabled — "
        "see -Dupm.plugin.upload.enabled=true in devtools-definition/devtools/confluence/values.yaml."
    )
    assert r.json()["status"] == "successful"

    # --- step 4: verify it's actually installed ---
    r = confluence.get(f"/rest/plugins/1.0/{PLUGIN_KEY}-key")
    assert r.status_code == 200, "Plugin not found in Confluence after install"
    assert r.json()["key"] == PLUGIN_KEY
    assert r.json()["enabled"] is True

    # --- step 5: uninstall it via our API ---
    r = api.delete(f"{API_PREFIX}/plugin/{PLUGIN_KEY}")
    assert r.status_code == 200, f"Plugin uninstall failed: {r.text}"
    assert r.json()["status"] == "successful"

    # --- step 6: verify it's actually gone ---
    r = confluence.get(f"/rest/plugins/1.0/{PLUGIN_KEY}-key")
    assert r.status_code == 404, "Plugin still installed after a \"successful\" uninstall"


@pytest.mark.integration
def test_export_import_full_flow(confluence, api):
    _wait_for_confluence(confluence)
    _wait_for_api(api)

    # --- setup: clean state ---
    _delete_space_if_exists(confluence, SPACE_KEY)
    _ensure_user(confluence, ADMIN_USER)

    # --- step 1: create space via our API ---
    r = api.post(f"{API_PREFIX}/", json={
        "metadata": REQUEST_METADATA,
        "spec": {
            "key": SPACE_KEY,
            "name": SPACE_NAME,
            "description": "E2E export/import test space",
            "admin_user": ADMIN_USER,
        },
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

    # --- step 4: export the space via our API — relays Confluence's backup archive into
    # MinIO through devops-api's own memory (Confluence never talks to MinIO directly) ---
    r = api.post(f"{API_PREFIX}/space-export/", json={
        "metadata": REQUEST_METADATA,
        "spec": {"space_key": SPACE_KEY},
    })
    assert r.status_code == 200, f"Space export failed: {r.text}"
    assert r.json()["status"] == "successful"
    archive_name = r.json()["archive_name"]
    assert archive_name.endswith(".zip"), f"Unexpected archive_name: {archive_name}"

    # --- step 5: verify the archive is actually in MinIO ---
    r = httpx.get(f"{MINIO_URL}/platform-clients/confluence-space-imports/{archive_name}", timeout=10)
    assert r.status_code == 200, f"Archive not found in MinIO: {archive_name}"
    assert len(r.content) > 0

    # --- step 6: delete the space ---
    _delete_space_if_exists(confluence, SPACE_KEY)
    r = confluence.get(f"/rest/api/latest/space/{SPACE_KEY}")
    assert r.status_code == 404, "Space should be gone before import"

    # --- step 7: import the space via our API. Note: archive_name is the ONLY field in
    # SpaceImportSpec — Confluence restores the space key from the archive itself, there is
    # no way to override it (see app/v1/confluence/CLAUDE.md). ---
    r = api.post(f"{API_PREFIX}/space-import/", json={
        "metadata": REQUEST_METADATA,
        "spec": {"archive_name": archive_name},
    })
    assert r.status_code == 200, f"Space import failed: {r.text}"
    assert r.json()["status"] == "successful"

    # --- step 8: verify space is back with its page and attachment, including the original
    # creation timestamp (proves this is a genuine restore, not just a fresh space reusing
    # the same key) ---
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

    # --- cleanup ---
    _delete_space_if_exists(confluence, SPACE_KEY)
