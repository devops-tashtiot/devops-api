import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.v1.sonarqube.routes import get_v1_sonarqube_router


@pytest.fixture
def mock_sonar_client():
    client = MagicMock()
    ok_response = MagicMock()
    ok_response.status_code = 200
    ok_response.text = ""
    client.post = AsyncMock(return_value=ok_response)
    return client


@pytest.fixture(autouse=True)
def patch_base_api(mock_sonar_client):
    """Routes build their own httpx client via BaseAPI; patch it to return the shared mock."""
    with patch("app.v1.sonarqube.routes.BaseAPI") as mock_cls:
        mock_cls.return_value.client = mock_sonar_client
        yield mock_cls


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(get_v1_sonarqube_router())
    return TestClient(app)
