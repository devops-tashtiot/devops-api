import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.v1.bitbucket.conf import config
from app.v1.bitbucket.routes import get_v1_bitbucket_router

PREFIX = config.API_PREFIX

VALID_METADATA = {
    "project": "test-project",
    "network": "test-network",
    "region": "test-region",
    "space": "test-space",
    "environment": "test-env",
}

VALID_PAYLOAD = {
    "metadata": VALID_METADATA,
    "spec": {
        "key": "TEST",
        "name": "test-project",
        "description": "A test project",
        "public": False,
        "admin_user": "nati",
    },
}

VALID_PAYLOAD_GROUP = {
    "metadata": VALID_METADATA,
    "spec": {
        "key": "TEST",
        "name": "test-project",
        "description": "A test project",
        "public": False,
        "admin_group": "devops-team",
    },
}


# --- create ---

def test_create_project_returns_200(client, mock_bitbucket_client):
    response = client.post(f"{PREFIX}/", json=VALID_PAYLOAD)
    assert response.status_code == 200
    assert response.json()["status"] == "successful"


def test_create_project_calls_create_endpoint(client, mock_bitbucket_client):
    client.post(f"{PREFIX}/", json=VALID_PAYLOAD)
    endpoints = [c.args[0] for c in mock_bitbucket_client.post.call_args_list]
    assert any("/projects" in ep for ep in endpoints)


def test_create_project_with_admin_user_assigns_user_permission(client, mock_bitbucket_client):
    client.post(f"{PREFIX}/", json=VALID_PAYLOAD)
    put_endpoints = [c.args[0] for c in mock_bitbucket_client.put.call_args_list]
    assert any("permissions/users" in ep for ep in put_endpoints)
    assert any("nati" in ep for ep in put_endpoints)
    assert any("PROJECT_ADMIN" in ep for ep in put_endpoints)


def test_create_project_with_admin_group_assigns_group_permission(client, mock_bitbucket_client):
    client.post(f"{PREFIX}/", json=VALID_PAYLOAD_GROUP)
    put_endpoints = [c.args[0] for c in mock_bitbucket_client.put.call_args_list]
    assert any("permissions/groups" in ep for ep in put_endpoints)
    assert any("devops-team" in ep for ep in put_endpoints)
    assert any("PROJECT_ADMIN" in ep for ep in put_endpoints)


def test_create_project_total_call_count_with_admin_user(client, mock_bitbucket_client):
    client.post(f"{PREFIX}/", json=VALID_PAYLOAD)
    assert mock_bitbucket_client.post.call_count == 1  # create only
    assert mock_bitbucket_client.put.call_count == 1   # user permission


def test_create_project_total_call_count_with_admin_group(client, mock_bitbucket_client):
    client.post(f"{PREFIX}/", json=VALID_PAYLOAD_GROUP)
    assert mock_bitbucket_client.post.call_count == 1  # create only
    assert mock_bitbucket_client.put.call_count == 1   # group permission


def test_create_project_error_returns_error_response(mock_bitbucket_client):
    conflict = MagicMock(status_code=409, text='{"errors":[{"message":"Project already exists"}]}')
    mock_bitbucket_client.post = AsyncMock(return_value=conflict)

    app = FastAPI()
    app.include_router(get_v1_bitbucket_router(mock_bitbucket_client))
    c = TestClient(app)

    response = c.post(f"{PREFIX}/", json=VALID_PAYLOAD)
    assert response.status_code == 409
    assert response.json()["status"] == "Failed"


def test_create_project_unexpected_error_triggers_rollback(mock_bitbucket_client):
    ok = MagicMock(status_code=200, text="")
    mock_bitbucket_client.post = AsyncMock(side_effect=Exception("network error"))
    mock_bitbucket_client.delete = AsyncMock(return_value=ok)

    app = FastAPI()
    app.include_router(get_v1_bitbucket_router(mock_bitbucket_client))
    c = TestClient(app)

    c.post(f"{PREFIX}/", json=VALID_PAYLOAD)

    delete_endpoints = [call.args[0] for call in mock_bitbucket_client.delete.call_args_list]
    assert any("TEST" in ep for ep in delete_endpoints)


# --- delete ---

def test_delete_project_returns_200(client, mock_bitbucket_client):
    response = client.delete(f"{PREFIX}/TEST")
    assert response.status_code == 200
    assert response.json()["status"] == "successful"


def test_delete_project_calls_delete_endpoint(client, mock_bitbucket_client):
    client.delete(f"{PREFIX}/TEST")
    assert mock_bitbucket_client.delete.call_count == 1
    endpoint = mock_bitbucket_client.delete.call_args.args[0]
    assert "/projects/TEST" in endpoint


def test_delete_project_not_found_returns_error(mock_bitbucket_client):
    mock_bitbucket_client.delete = AsyncMock(
        return_value=MagicMock(status_code=404, text='{"errors":[{"message":"Project not found"}]}')
    )

    app = FastAPI()
    app.include_router(get_v1_bitbucket_router(mock_bitbucket_client))
    c = TestClient(app)

    response = c.delete(f"{PREFIX}/NOTEXIST")
    assert response.status_code == 404
    assert response.json()["status"] == "Failed"


def test_delete_project_conflict_returns_error(mock_bitbucket_client):
    mock_bitbucket_client.delete = AsyncMock(
        return_value=MagicMock(status_code=409, text='{"errors":[{"message":"Project has repositories"}]}')
    )

    app = FastAPI()
    app.include_router(get_v1_bitbucket_router(mock_bitbucket_client))
    c = TestClient(app)

    response = c.delete(f"{PREFIX}/HASREPOS")
    assert response.status_code == 409
    assert response.json()["status"] == "Failed"


# --- user-dirs ---

BITBUCKET_DIRECTORIES_RESPONSE = {
    "directory": [
        # Internal directory is listed first and has no "synchronisation" key — not syncable.
        {"name": "Bitbucket Internal Directory", "link": [{"href": "http://bitbucket/rest/crowd/latest/directory/32769", "rel": "self"}]},
        # Connector directory — has "synchronisation", this is the one that should get synced.
        {
            "name": "Active Directory server",
            "link": [{"href": "http://bitbucket/rest/crowd/latest/directory/13139969", "rel": "self"}],
            "synchronisation": {"syncStatus": "Incremental synchronisation completed successfully."},
        },
    ]
}


def test_list_user_dirs_returns_200(mock_bitbucket_client):
    mock_bitbucket_client.get = AsyncMock(return_value=MagicMock(
        status_code=200, text="", json=MagicMock(return_value=BITBUCKET_DIRECTORIES_RESPONSE)
    ))
    app = FastAPI()
    app.include_router(get_v1_bitbucket_router(mock_bitbucket_client))
    c = TestClient(app)
    response = c.get(f"{PREFIX}/user-dirs")
    assert response.status_code == 200
    assert response.json() == BITBUCKET_DIRECTORIES_RESPONSE["directory"]


def test_sync_user_dir_returns_200(mock_bitbucket_client):
    mock_bitbucket_client.get = AsyncMock(return_value=MagicMock(
        status_code=200, text="", json=MagicMock(return_value=BITBUCKET_DIRECTORIES_RESPONSE)
    ))
    mock_bitbucket_client.post = AsyncMock(return_value=MagicMock(status_code=200, text=""))
    app = FastAPI()
    app.include_router(get_v1_bitbucket_router(mock_bitbucket_client))
    c = TestClient(app)
    response = c.post(f"{PREFIX}/user-dirs/sync")
    assert response.status_code == 200
    assert response.json()["status"] == "successful"
    sync_endpoint = mock_bitbucket_client.post.call_args.args[0]
    assert sync_endpoint.endswith("/directory/13139969/synchronise")


def test_sync_user_dir_error_returns_error_response(mock_bitbucket_client):
    mock_bitbucket_client.get = AsyncMock(return_value=MagicMock(
        status_code=200, text="", json=MagicMock(return_value=BITBUCKET_DIRECTORIES_RESPONSE)
    ))
    mock_bitbucket_client.post = AsyncMock(return_value=MagicMock(status_code=404, text="Not found"))
    app = FastAPI()
    app.include_router(get_v1_bitbucket_router(mock_bitbucket_client))
    c = TestClient(app)
    response = c.post(f"{PREFIX}/user-dirs/sync")
    assert response.status_code == 404
    assert response.json()["status"] == "Failed"


def test_sync_user_dir_no_directories_returns_404(mock_bitbucket_client):
    mock_bitbucket_client.get = AsyncMock(return_value=MagicMock(
        status_code=200, text="", json=MagicMock(return_value={"directory": []})
    ))
    app = FastAPI()
    app.include_router(get_v1_bitbucket_router(mock_bitbucket_client))
    c = TestClient(app)
    response = c.post(f"{PREFIX}/user-dirs/sync")
    assert response.status_code == 404
    assert response.json()["status"] == "Failed"


def test_sync_user_dir_only_internal_directory_returns_404(mock_bitbucket_client):
    # Only a non-syncable internal directory exists (no connector/LDAP directory configured) —
    # must not blindly try to sync it (that 404s against Bitbucket itself).
    mock_bitbucket_client.get = AsyncMock(return_value=MagicMock(
        status_code=200, text="", json=MagicMock(return_value={"directory": [
            {"name": "Bitbucket Internal Directory", "link": [{"href": "http://bitbucket/rest/crowd/latest/directory/32769", "rel": "self"}]},
        ]})
    ))
    app = FastAPI()
    app.include_router(get_v1_bitbucket_router(mock_bitbucket_client))
    c = TestClient(app)
    response = c.post(f"{PREFIX}/user-dirs/sync")
    assert response.status_code == 404
    assert response.json()["status"] == "Failed"
    mock_bitbucket_client.post.assert_not_called()
