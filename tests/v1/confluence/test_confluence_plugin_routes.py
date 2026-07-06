import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.v1.confluence.conf import config
from app.v1.confluence.routes import get_v1_confluence_router

PREFIX = config.API_PREFIX
FAKE_UPM_TOKEN = "test-upm-token-123"
VALID_METADATA = {
    "project": "test-project",
    "network": "test-network",
    "region": "test-region",
    "space": "test-space",
    "environment": "test-env",
}
VALID_PAYLOAD = {"metadata": VALID_METADATA, "spec": {"plugin_name": "my-plugin-1.0.jar"}}


def test_install_plugin_returns_200(client, mock_s3_http):
    response = client.post(f"{PREFIX}/plugin/", json=VALID_PAYLOAD)
    assert response.status_code == 200
    assert response.json()["status"] == "successful"


def test_install_plugin_fetches_from_s3_url(client, mock_s3_http):
    client.post(f"{PREFIX}/plugin/", json=VALID_PAYLOAD)
    mock_s3_http.get.assert_called_once()
    url = mock_s3_http.get.call_args.args[0]
    assert url.endswith("my-plugin-1.0.jar")


def test_install_plugin_fetches_upm_token(client, mock_s3_http, mock_confluence_client):
    client.post(f"{PREFIX}/plugin/", json=VALID_PAYLOAD)
    mock_confluence_client.get.assert_called_once()
    endpoint = mock_confluence_client.get.call_args.args[0]
    assert "rest/plugins/1.0" in endpoint
    assert "os_authType=basic" in endpoint


def test_install_plugin_uploads_to_upm_with_token(client, mock_s3_http, mock_confluence_client):
    client.post(f"{PREFIX}/plugin/", json=VALID_PAYLOAD)
    mock_confluence_client.post.assert_called_once()
    endpoint = mock_confluence_client.post.call_args.args[0]
    assert "rest/plugins/1.0" in endpoint
    assert FAKE_UPM_TOKEN in endpoint


def test_install_plugin_sends_correct_filename(client, mock_s3_http, mock_confluence_client):
    client.post(f"{PREFIX}/plugin/", json=VALID_PAYLOAD)
    files = mock_confluence_client.post.call_args.kwargs["files"]
    filename, _, content_type = files["plugin"]
    assert filename == "my-plugin-1.0.jar"
    assert content_type == "application/octet-stream"


def test_install_plugin_s3_404_returns_404(mock_confluence_client):
    s3_response = MagicMock()
    s3_response.status_code = 404
    s3_response.content = b""
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=s3_response)

    with patch("app.v1.confluence.operations.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        app = FastAPI()
        app.include_router(get_v1_confluence_router(mock_confluence_client))
        c = TestClient(app)

        response = c.post(f"{PREFIX}/plugin/", json=VALID_PAYLOAD)
        assert response.status_code == 404
        assert "not found" in response.json()["stdout"].lower()


def test_install_plugin_s3_error_returns_502(mock_confluence_client):
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(side_effect=Exception("connection refused"))

    with patch("app.v1.confluence.operations.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        app = FastAPI()
        app.include_router(get_v1_confluence_router(mock_confluence_client))
        c = TestClient(app)

        response = c.post(f"{PREFIX}/plugin/", json=VALID_PAYLOAD)
        assert response.status_code == 502
        assert "S3 fetch failed" in response.json()["stdout"]


def test_install_plugin_confluence_auth_error_returns_401(mock_s3_http):
    bad_confluence = MagicMock()
    token_response = MagicMock()
    token_response.status_code = 401
    token_response.text = "Unauthorized"
    bad_confluence.get = AsyncMock(return_value=token_response)

    app = FastAPI()
    app.include_router(get_v1_confluence_router(bad_confluence))
    c = TestClient(app)

    response = c.post(f"{PREFIX}/plugin/", json=VALID_PAYLOAD)
    assert response.status_code == 401
    assert response.json()["status"] == "Failed"


def test_install_plugin_missing_upm_token_returns_502(mock_s3_http):
    bad_confluence = MagicMock()
    token_response = MagicMock()
    token_response.status_code = 200
    token_response.headers = {}
    bad_confluence.get = AsyncMock(return_value=token_response)

    app = FastAPI()
    app.include_router(get_v1_confluence_router(bad_confluence))
    c = TestClient(app)

    response = c.post(f"{PREFIX}/plugin/", json=VALID_PAYLOAD)
    assert response.status_code == 502
    assert "upm-token" in response.json()["stdout"]


def test_uninstall_plugin_returns_200(client):
    response = client.delete(f"{PREFIX}/plugin/com.example.my-plugin")
    assert response.status_code == 200
    assert response.json()["status"] == "successful"


def test_uninstall_plugin_calls_delete_with_key_suffix(client, mock_confluence_client):
    client.delete(f"{PREFIX}/plugin/com.example.my-plugin")
    mock_confluence_client.delete.assert_called_once()
    endpoint = mock_confluence_client.delete.call_args.args[0]
    assert endpoint.endswith("com.example.my-plugin-key")


def test_uninstall_plugin_not_found_returns_404(mock_s3_http):
    bad_confluence = MagicMock()
    not_found = MagicMock()
    not_found.status_code = 404
    not_found.text = "Plugin not found"
    bad_confluence.delete = AsyncMock(return_value=not_found)

    app = FastAPI()
    app.include_router(get_v1_confluence_router(bad_confluence))
    c = TestClient(app)

    response = c.delete(f"{PREFIX}/plugin/com.example.nonexistent")
    assert response.status_code == 404
    assert response.json()["status"] == "Failed"


def test_uninstall_dotted_key_preserved(client, mock_confluence_client):
    client.delete(f"{PREFIX}/plugin/com.atlassian.confluence.extra.team-calendars")
    endpoint = mock_confluence_client.delete.call_args.args[0]
    assert "com.atlassian.confluence.extra.team-calendars-key" in endpoint
