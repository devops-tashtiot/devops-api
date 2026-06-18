import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.v1.argocd.routes import get_v1_argocd_router


@pytest.fixture
def mock_git():
    git = MagicMock()
    git.add_file = AsyncMock(return_value=None)
    git.delete_file = AsyncMock(return_value=None)
    return git


@pytest.fixture
def client(mock_git):
    app = FastAPI()
    app.include_router(get_v1_argocd_router(mock_git, argocd_timeout=30))
    return TestClient(app)
