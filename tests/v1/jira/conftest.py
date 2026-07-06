import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.v1.jira.routes import get_v1_jira_router


@pytest.fixture
def mock_jira_client():
    client = MagicMock()
    ok = MagicMock()
    ok.status_code = 200
    ok.text = ""
    ok.json.return_value = {"id": "10000", "key": "MYPROJ", "self": "http://jira/project/MYPROJ"}

    client.post = AsyncMock(return_value=ok)
    client.delete = AsyncMock(return_value=ok)
    client.get = AsyncMock(return_value=ok)
    return client


@pytest.fixture
def client(mock_jira_client):
    app = FastAPI()
    app.include_router(get_v1_jira_router(mock_jira_client))
    return TestClient(app)
