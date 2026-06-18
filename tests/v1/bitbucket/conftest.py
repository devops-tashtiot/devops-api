import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.v1.bitbucket.routes import get_v1_bitbucket_router


@pytest.fixture
def mock_bitbucket_client():
    client = MagicMock()
    ok = MagicMock()
    ok.status_code = 200
    ok.text = ""
    ok_get = MagicMock()
    ok_get.status_code = 200
    ok_get.json = MagicMock(return_value={"values": [
        {"slug": "nati", "name": "nati"},
        {"name": "devops-team"},
    ]})
    client.post = AsyncMock(return_value=ok)
    client.put = AsyncMock(return_value=ok)
    client.delete = AsyncMock(return_value=ok)
    client.get = AsyncMock(return_value=ok_get)
    return client


@pytest.fixture
def client(mock_bitbucket_client):
    app = FastAPI()
    app.include_router(get_v1_bitbucket_router(mock_bitbucket_client))
    return TestClient(app)
