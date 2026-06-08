import pytest
from unittest.mock import AsyncMock, MagicMock
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


@pytest.fixture
def client(mock_sonar_client):
    app = FastAPI()
    app.include_router(get_v1_sonarqube_router(mock_sonar_client))
    return TestClient(app)
