from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.v1.confluence.conf import config
from app.v1.confluence.routes import get_v1_confluence_router

PREFIX = config.API_PREFIX
FAKE_ZIP = b"PK\x03\x04fake-zip-content"
VALID_PAYLOAD = {"space_key": "MYSP", "archive_name": "my-space-export.zip"}


@pytest.fixture
def mock_s3_http():
    s3_response = MagicMock()
    s3_response.status_code = 200
    s3_response.content = FAKE_ZIP

    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=s3_response)

    with patch("app.v1.confluence.operations.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        yield mock_http


@pytest.fixture
def mock_confluence_client():
    client = MagicMock()
    upload_response = MagicMock()
    upload_response.status_code = 200
    upload_response.text = ""
    upload_response.json.return_value = {"id": 42}

    finished_response = MagicMock()
    finished_response.status_code = 200
    finished_response.text = ""
    finished_response.json.return_value = {"id": 42, "jobState": "FINISHED"}

    client.post = AsyncMock(return_value=upload_response)
    client.get = AsyncMock(return_value=finished_response)
    return client


@pytest.fixture
def client(mock_confluence_client):
    app = FastAPI()
    app.include_router(get_v1_confluence_router(mock_confluence_client))
    return TestClient(app)


def test_space_import_returns_200(client, mock_s3_http):
    response = client.post(f"{PREFIX}/space-import/", json=VALID_PAYLOAD)
    assert response.status_code == 200
    assert response.json()["status"] == "successful"


def test_space_import_fetches_from_s3(client, mock_s3_http):
    client.post(f"{PREFIX}/space-import/", json=VALID_PAYLOAD)
    mock_s3_http.get.assert_called_once()
    url = mock_s3_http.get.call_args.args[0]
    assert url.endswith("my-space-export.zip")


def test_space_import_uploads_to_confluence(client, mock_s3_http, mock_confluence_client):
    client.post(f"{PREFIX}/space-import/", json=VALID_PAYLOAD)
    mock_confluence_client.post.assert_called_once()
    endpoint = mock_confluence_client.post.call_args.args[0]
    assert "backup-restore" in endpoint
    assert "upload" in endpoint


def test_space_import_sends_zip_file(client, mock_s3_http, mock_confluence_client):
    client.post(f"{PREFIX}/space-import/", json=VALID_PAYLOAD)
    files = mock_confluence_client.post.call_args.kwargs["files"]
    filename, _, content_type = files["file"]
    assert filename == "my-space-export.zip"
    assert content_type == "application/zip"


def test_space_import_polls_job(client, mock_s3_http, mock_confluence_client):
    client.post(f"{PREFIX}/space-import/", json=VALID_PAYLOAD)
    mock_confluence_client.get.assert_called_once()
    endpoint = mock_confluence_client.get.call_args.args[0]
    assert "jobs/42" in endpoint


def test_space_import_s3_404_returns_404(mock_confluence_client):
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
        response = c.post(f"{PREFIX}/space-import/", json=VALID_PAYLOAD)
    assert response.status_code == 404
    assert "not found" in response.json()["stdout"].lower()


def test_space_import_job_failed_returns_422(mock_s3_http):
    confluence = MagicMock()
    upload_response = MagicMock()
    upload_response.status_code = 200
    upload_response.text = ""
    upload_response.json.return_value = {"id": 7}

    failed_response = MagicMock()
    failed_response.status_code = 200
    failed_response.text = ""
    failed_response.json.return_value = {"id": 7, "jobState": "FAILED", "errorMessage": "corrupt archive"}

    confluence.post = AsyncMock(return_value=upload_response)
    confluence.get = AsyncMock(return_value=failed_response)

    app = FastAPI()
    app.include_router(get_v1_confluence_router(confluence))
    c = TestClient(app)
    response = c.post(f"{PREFIX}/space-import/", json=VALID_PAYLOAD)
    assert response.status_code == 422
    assert "corrupt archive" in response.json()["stdout"]


def test_space_import_confluence_upload_error_returns_error(mock_s3_http):
    confluence = MagicMock()
    confluence.post = AsyncMock(return_value=MagicMock(status_code=500, text="Server error"))

    app = FastAPI()
    app.include_router(get_v1_confluence_router(confluence))
    c = TestClient(app)
    response = c.post(f"{PREFIX}/space-import/", json=VALID_PAYLOAD)
    assert response.status_code == 500
    assert response.json()["status"] == "Failed"
