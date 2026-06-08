import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.v1.confluence.routes import get_v1_confluence_router

FAKE_JAR = b"PK\x03\x04fake-jar-content"
FAKE_UPM_TOKEN = "test-upm-token-123"


@pytest.fixture
def mock_s3_http():
    """Patches httpx.AsyncClient inside operations for the public S3 fetch."""
    s3_response = MagicMock()
    s3_response.status_code = 200
    s3_response.content = FAKE_JAR

    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=s3_response)

    with patch("app.v1.confluence.operations.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        yield mock_http


@pytest.fixture
def mock_confluence_client():
    client = MagicMock()

    token_response = MagicMock()
    token_response.status_code = 200
    token_response.headers = {"upm-token": FAKE_UPM_TOKEN}

    install_response = MagicMock()
    install_response.status_code = 200
    install_response.text = ""
    install_response.json.return_value = {}

    delete_response = MagicMock()
    delete_response.status_code = 200
    delete_response.text = ""

    client.get = AsyncMock(return_value=token_response)
    client.post = AsyncMock(return_value=install_response)
    client.delete = AsyncMock(return_value=delete_response)
    return client


@pytest.fixture
def client(mock_confluence_client):
    app = FastAPI()
    app.include_router(get_v1_confluence_router(mock_confluence_client))
    return TestClient(app)
