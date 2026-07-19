from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.v1.confluence.conf import config
from app.v1.confluence.routes import get_v1_confluence_router

PREFIX = config.API_PREFIX

VALID_METADATA = {
    "project": "test-project",
    "network": "test-network",
    "region": "test-region",
    "space": "test-space",
    "environment": "test-env",
}

VALID_USER_PAYLOAD = {
    "metadata": VALID_METADATA,
    "spec": {"key": "TESTSP", "name": "Test Space", "description": "A test space", "admin_user": "admin"},
}
VALID_GROUP_PAYLOAD = {
    "metadata": VALID_METADATA,
    "spec": {"key": "GRPSP", "name": "Group Space", "description": "A group space", "admin_group": "dev-team"},
}
VALID_BOTH_PAYLOAD = {
    "metadata": VALID_METADATA,
    "spec": {"key": "BOTHSP", "name": "Both Space", "description": "Both admins", "admin_user": "admin", "admin_group": "dev-team"},
}


@pytest.fixture
def mock_confluence_client():
    client = MagicMock()
    ok = MagicMock()
    ok.status_code = 200
    ok.text = ""
    ok.json.return_value = {"userKey": "abc123"}

    user_key_response = MagicMock()
    user_key_response.status_code = 200
    user_key_response.text = ""
    user_key_response.json.return_value = {"userKey": "abc123"}

    client.post = AsyncMock(return_value=ok)
    client.put = AsyncMock(return_value=ok)
    client.delete = AsyncMock(return_value=ok)
    client.get = AsyncMock(return_value=user_key_response)
    return client


@pytest.fixture
def client(mock_confluence_client):
    app = FastAPI()
    app.include_router(get_v1_confluence_router(mock_confluence_client))
    return TestClient(app)


# --- create space ---

def test_create_space_with_user_returns_200(client):
    response = client.post(f"{PREFIX}/", json=VALID_USER_PAYLOAD)
    assert response.status_code == 200
    assert response.json()["status"] == "successful"


def test_create_space_with_group_returns_200(client):
    response = client.post(f"{PREFIX}/", json=VALID_GROUP_PAYLOAD)
    assert response.status_code == 200
    assert response.json()["status"] == "successful"


def test_create_space_with_both_user_and_group_returns_200(client):
    response = client.post(f"{PREFIX}/", json=VALID_BOTH_PAYLOAD)
    assert response.status_code == 200
    assert response.json()["status"] == "successful"


def test_create_space_calls_post_once(client, mock_confluence_client):
    client.post(f"{PREFIX}/", json=VALID_USER_PAYLOAD)
    mock_confluence_client.post.assert_called_once()
    endpoint = mock_confluence_client.post.call_args.args[0]
    assert "/space" in endpoint


def test_create_space_with_user_assigns_user_admin(client, mock_confluence_client):
    client.post(f"{PREFIX}/", json=VALID_USER_PAYLOAD)
    put_calls = [c.args[0] for c in mock_confluence_client.put.call_args_list]
    assert any("permissions/user" in ep for ep in put_calls)


def test_create_space_with_group_assigns_group_admin(client, mock_confluence_client):
    client.post(f"{PREFIX}/", json=VALID_GROUP_PAYLOAD)
    put_calls = [c.args[0] for c in mock_confluence_client.put.call_args_list]
    assert any("permissions/group" in ep for ep in put_calls)


def test_create_space_with_both_assigns_user_and_group(client, mock_confluence_client):
    client.post(f"{PREFIX}/", json=VALID_BOTH_PAYLOAD)
    put_calls = [c.args[0] for c in mock_confluence_client.put.call_args_list]
    assert any("permissions/user" in ep for ep in put_calls)
    assert any("permissions/group" in ep for ep in put_calls)


def test_create_space_confluence_error_returns_error_response(mock_confluence_client):
    mock_confluence_client.post = AsyncMock(return_value=MagicMock(status_code=400, text="Bad request"))
    app = FastAPI()
    app.include_router(get_v1_confluence_router(mock_confluence_client))
    c = TestClient(app)
    response = c.post(f"{PREFIX}/", json=VALID_USER_PAYLOAD)
    assert response.status_code == 400
    assert response.json()["status"] == "Failed"


# --- delete space ---
# Confluence's DELETE /space/{key} only accepts the deletion — the space is removed
# asynchronously. delete_space polls GET /space/{key} until it 404s before reporting success.

def test_delete_space_returns_200_once_confirmed_gone(client, mock_confluence_client):
    mock_confluence_client.delete = AsyncMock(return_value=MagicMock(status_code=200, text=""))
    # First poll still finds the space (200), second poll confirms it's gone (404).
    mock_confluence_client.get = AsyncMock(side_effect=[
        MagicMock(status_code=200, text=""),
        MagicMock(status_code=404, text=""),
    ])

    response = client.delete(f"{PREFIX}/ZAITEST")
    assert response.status_code == 200
    assert response.json()["status"] == "successful"
    assert mock_confluence_client.get.call_count == 2


def test_delete_space_times_out_if_never_confirmed(mock_confluence_client, monkeypatch):
    from app.v1.confluence import operations as confluence_ops

    monkeypatch.setattr(confluence_ops.config, "CONFLUENCE_JOB_MAX_POLLS", 2)
    monkeypatch.setattr(confluence_ops.config, "CONFLUENCE_JOB_POLL_INTERVAL", 0)

    mock_confluence_client.delete = AsyncMock(return_value=MagicMock(status_code=200, text=""))
    mock_confluence_client.get = AsyncMock(return_value=MagicMock(status_code=200, text=""))  # never 404s

    app = FastAPI()
    app.include_router(get_v1_confluence_router(mock_confluence_client))
    c = TestClient(app)
    response = c.delete(f"{PREFIX}/ZAITEST")
    assert response.status_code == 504
    assert response.json()["status"] == "Failed"
    assert mock_confluence_client.get.call_count == 2


def test_delete_space_error_returns_error_response(mock_confluence_client):
    mock_confluence_client.delete = AsyncMock(return_value=MagicMock(status_code=404, text="Not found"))
    app = FastAPI()
    app.include_router(get_v1_confluence_router(mock_confluence_client))
    c = TestClient(app)
    response = c.delete(f"{PREFIX}/NOEXIST")
    assert response.status_code == 404
    assert response.json()["status"] == "Failed"
    mock_confluence_client.get.assert_not_called()


# --- user-dirs ---

def test_list_user_dirs_returns_200(mock_confluence_client):
    dirs_response = MagicMock()
    dirs_response.status_code = 200
    dirs_response.text = ""
    dirs_response.json.return_value = {"directory": [{"name": "Internal Dir"}]}
    mock_confluence_client.get = AsyncMock(return_value=dirs_response)

    app = FastAPI()
    app.include_router(get_v1_confluence_router(mock_confluence_client))
    c = TestClient(app)
    response = c.get(f"{PREFIX}/user-dirs")
    assert response.status_code == 200
    assert response.json() == [{"name": "Internal Dir"}]


def test_list_user_dirs_calls_crowd_endpoint(mock_confluence_client):
    dirs_response = MagicMock()
    dirs_response.status_code = 200
    dirs_response.text = ""
    dirs_response.json.return_value = {"directory": []}
    mock_confluence_client.get = AsyncMock(return_value=dirs_response)

    app = FastAPI()
    app.include_router(get_v1_confluence_router(mock_confluence_client))
    c = TestClient(app)
    c.get(f"{PREFIX}/user-dirs")
    endpoint = mock_confluence_client.get.call_args.args[0]
    assert "crowd" in endpoint
    assert "directory" in endpoint


def test_sync_user_dir_returns_501_not_supported(client, mock_confluence_client):
    # Confluence has no supported way to trigger a directory sync on demand — confirmed live
    # (see app/v1/bitbucket/CLAUDE.md for the shared investigation): the Crowd-embedded
    # synchronise path 404s even with a correct connector directory ID. Must always return
    # 501 without attempting any call to Confluence.
    response = client.post(f"{PREFIX}/user-dirs/sync")
    assert response.status_code == 501
    assert response.json()["status"] == "Failed"
    mock_confluence_client.get.assert_not_called()
    mock_confluence_client.post.assert_not_called()
