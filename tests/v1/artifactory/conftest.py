import json as json_module
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.v1.artifactory.routes import get_v1_artifactory_router


def make_response(status_code=200, data=None):
    r = MagicMock()
    r.status_code = status_code
    r.text = json_module.dumps(data) if data is not None else ""
    r.json = MagicMock(return_value=data if data is not None else {})
    return r


@pytest.fixture
def mock_artifactory_client():
    c = MagicMock()
    ok = make_response(200)
    quota_ok = make_response(200, {"storage_quota_bytes": 1073741824})
    c.post = AsyncMock(return_value=ok)
    c.put = AsyncMock(return_value=ok)
    c.delete = AsyncMock(return_value=ok)
    c.get = AsyncMock(return_value=quota_ok)
    return c


@pytest.fixture
def client(mock_artifactory_client):
    app = FastAPI()
    app.include_router(get_v1_artifactory_router(mock_artifactory_client))
    return TestClient(app)
