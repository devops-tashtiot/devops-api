from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.v1.confluence.conf import config
from app.v1.confluence.routes import get_v1_confluence_router

PREFIX = config.API_PREFIX
VALID_PAYLOAD = {"space_key": "MYSP"}
FAKE_ARCHIVE_NAME = "Confluence-space-export-MYSP-2026-01-01-00-00-00-000.xml.zip"
FAKE_ZIP = b"PK\x03\x04fake-zip-content"


@pytest.fixture
def mock_confluence_client():
    client = MagicMock()

    trigger_response = MagicMock()
    trigger_response.status_code = 200
    trigger_response.text = ""
    trigger_response.json.return_value = {"id": 99, "fileName": FAKE_ARCHIVE_NAME, "jobState": "QUEUED"}

    poll_response = MagicMock()
    poll_response.status_code = 200
    poll_response.text = ""
    poll_response.json.return_value = {"id": 99, "jobState": "FINISHED"}

    download_response = MagicMock()
    download_response.status_code = 200
    download_response.content = FAKE_ZIP
    download_response.text = ""

    client.post = AsyncMock(return_value=trigger_response)
    client.get = AsyncMock(side_effect=[poll_response, download_response])
    return client


@pytest.fixture
def mock_s3_upload():
    upload_response = MagicMock()
    upload_response.status_code = 200

    mock_http = AsyncMock()
    mock_http.put = AsyncMock(return_value=upload_response)

    with patch("app.v1.confluence.operations.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        yield mock_http


@pytest.fixture
def client(mock_confluence_client):
    app = FastAPI()
    app.include_router(get_v1_confluence_router(mock_confluence_client))
    return TestClient(app)


def test_export_returns_200_with_archive_name(client, mock_s3_upload):
    response = client.post(f"{PREFIX}/space-export/", json=VALID_PAYLOAD)
    assert response.status_code == 200
    assert response.json()["status"] == "successful"
    assert response.json()["archive_name"] == FAKE_ARCHIVE_NAME


def test_export_triggers_backup_with_space_key(client, mock_s3_upload, mock_confluence_client):
    client.post(f"{PREFIX}/space-export/", json=VALID_PAYLOAD)
    endpoint = mock_confluence_client.post.call_args.args[0]
    assert "backup/space" in endpoint
    body = mock_confluence_client.post.call_args.kwargs["json"]
    assert body == {"spaceKeys": ["MYSP"]}


def test_export_polls_job_status(client, mock_s3_upload, mock_confluence_client):
    client.post(f"{PREFIX}/space-export/", json=VALID_PAYLOAD)
    get_calls = [c.args[0] for c in mock_confluence_client.get.call_args_list]
    assert any("jobs/99" in ep for ep in get_calls)


def test_export_downloads_archive(client, mock_s3_upload, mock_confluence_client):
    client.post(f"{PREFIX}/space-export/", json=VALID_PAYLOAD)
    get_calls = [c.args[0] for c in mock_confluence_client.get.call_args_list]
    assert any("jobs/99/download" in ep for ep in get_calls)


def test_export_uploads_to_s3(client, mock_s3_upload):
    client.post(f"{PREFIX}/space-export/", json=VALID_PAYLOAD)
    mock_s3_upload.put.assert_called_once()
    url = mock_s3_upload.put.call_args.args[0]
    assert FAKE_ARCHIVE_NAME in url


def test_export_confluence_error_returns_error_response(mock_s3_upload):
    bad_client = MagicMock()
    bad_client.post = AsyncMock(return_value=MagicMock(status_code=500, text="Server Error"))
    app = FastAPI()
    app.include_router(get_v1_confluence_router(bad_client))
    c = TestClient(app)
    response = c.post(f"{PREFIX}/space-export/", json=VALID_PAYLOAD)
    assert response.status_code == 500
    assert response.json()["status"] == "Failed"


def test_export_job_failed_returns_422(mock_s3_upload):
    client = MagicMock()

    trigger_response = MagicMock()
    trigger_response.status_code = 200
    trigger_response.text = ""
    trigger_response.json.return_value = {"id": 77, "fileName": "export.zip", "jobState": "QUEUED"}

    failed_response = MagicMock()
    failed_response.status_code = 200
    failed_response.text = ""
    failed_response.json.return_value = {"id": 77, "jobState": "FAILED", "errorMessage": "space not found"}

    client.post = AsyncMock(return_value=trigger_response)
    client.get = AsyncMock(return_value=failed_response)

    app = FastAPI()
    app.include_router(get_v1_confluence_router(client))
    c = TestClient(app)
    response = c.post(f"{PREFIX}/space-export/", json=VALID_PAYLOAD)
    assert response.status_code == 422
    assert "space not found" in response.json()["stdout"]


def test_export_s3_upload_error_returns_502(mock_confluence_client):
    bad_http = AsyncMock()
    bad_http.put = AsyncMock(return_value=MagicMock(status_code=503))

    with patch("app.v1.confluence.operations.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=bad_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        app = FastAPI()
        app.include_router(get_v1_confluence_router(mock_confluence_client))
        c = TestClient(app)
        response = c.post(f"{PREFIX}/space-export/", json=VALID_PAYLOAD)
    assert response.status_code == 502
    assert "S3 upload" in response.json()["stdout"]
