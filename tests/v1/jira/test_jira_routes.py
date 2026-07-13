from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.v1.jira.conf import config
from app.v1.jira.routes import get_v1_jira_router

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
    "spec": {"key": "MYPROJ", "name": "My Project", "description": "A test project", "admin_user": "admin"},
}
# Jira unconditionally requires a lead (a user, never a group) to create a project —
# confirmed live, see app/v1/jira/CLAUDE.md. admin_group alone is therefore invalid input.
GROUP_ONLY_PAYLOAD = {
    "metadata": VALID_METADATA,
    "spec": {"key": "GRPPROJ", "name": "Group Project", "description": "A group project", "admin_group": "dev-team"},
}
VALID_BOTH_PAYLOAD = {
    "metadata": VALID_METADATA,
    "spec": {"key": "BTPROJ", "name": "Both Project", "description": "Both admins", "admin_user": "admin", "admin_group": "dev-team"},
}


# --- create project ---

def test_create_project_with_user_returns_200(client):
    response = client.post(f"{PREFIX}/", json=VALID_USER_PAYLOAD)
    assert response.status_code == 200
    assert response.json()["status"] == "successful"


def test_create_project_group_only_returns_422(client):
    response = client.post(f"{PREFIX}/", json=GROUP_ONLY_PAYLOAD)
    assert response.status_code == 422


def test_create_project_with_both_returns_200(client):
    response = client.post(f"{PREFIX}/", json=VALID_BOTH_PAYLOAD)
    assert response.status_code == 200
    assert response.json()["status"] == "successful"


def test_create_project_calls_post_with_correct_endpoint(client, mock_jira_client):
    client.post(f"{PREFIX}/", json=VALID_USER_PAYLOAD)
    endpoint = mock_jira_client.post.call_args_list[0].args[0]
    assert "/project" in endpoint


def test_create_project_with_user_assigns_role(client, mock_jira_client):
    client.post(f"{PREFIX}/", json=VALID_USER_PAYLOAD)
    post_endpoints = [c.args[0] for c in mock_jira_client.post.call_args_list]
    assert any("role" in ep for ep in post_endpoints)


def test_create_project_with_both_assigns_user_and_group(client, mock_jira_client):
    client.post(f"{PREFIX}/", json=VALID_BOTH_PAYLOAD)
    role_calls = [c for c in mock_jira_client.post.call_args_list if "role" in c.args[0]]
    assert len(role_calls) == 2
    bodies = [c.kwargs["json"] for c in role_calls]
    assert any("user" in b for b in bodies)
    assert any("group" in b for b in bodies)


def test_create_project_error_returns_error_response(mock_jira_client):
    mock_jira_client.post = AsyncMock(return_value=MagicMock(status_code=400, text="Bad Request"))
    app = FastAPI()
    app.include_router(get_v1_jira_router(mock_jira_client))
    c = TestClient(app)
    response = c.post(f"{PREFIX}/", json=VALID_USER_PAYLOAD)
    assert response.status_code == 400
    assert response.json()["status"] == "Failed"


# --- delete project ---

def test_delete_project_returns_200(client):
    response = client.delete(f"{PREFIX}/MYPROJ")
    assert response.status_code == 200
    assert response.json()["status"] == "successful"


def test_delete_project_calls_delete_with_key(client, mock_jira_client):
    client.delete(f"{PREFIX}/MYPROJ")
    mock_jira_client.delete.assert_called_once()
    endpoint = mock_jira_client.delete.call_args.args[0]
    assert "MYPROJ" in endpoint


def test_delete_project_not_found_returns_404(mock_jira_client):
    mock_jira_client.delete = AsyncMock(return_value=MagicMock(status_code=404, text="Not found"))
    app = FastAPI()
    app.include_router(get_v1_jira_router(mock_jira_client))
    c = TestClient(app)
    response = c.delete(f"{PREFIX}/NOEXIST")
    assert response.status_code == 404
    assert response.json()["status"] == "Failed"


# --- user-dirs ---

JIRA_DIRECTORIES_RESPONSE = {
    "directories": [
        {"name": "Jira Internal Directory", "links": [{"href": "http://jira/rest/crowd/latest/directory/1", "rel": "self"}]},
        {"name": "LDAP server", "links": [{"href": "http://jira/rest/crowd/latest/directory/10000", "rel": "self"}]},
    ]
}


def test_list_user_dirs_returns_200(mock_jira_client):
    mock_jira_client.get = AsyncMock(return_value=MagicMock(
        status_code=200, text="", json=MagicMock(return_value=JIRA_DIRECTORIES_RESPONSE)
    ))
    app = FastAPI()
    app.include_router(get_v1_jira_router(mock_jira_client))
    c = TestClient(app)
    response = c.get(f"{PREFIX}/user-dirs")
    assert response.status_code == 200
    assert response.json() == JIRA_DIRECTORIES_RESPONSE["directories"]


def test_sync_user_directory_returns_not_supported(mock_jira_client):
    # Jira has no supported API to trigger a directory sync on demand — confirmed live (see
    # app/v1/jira/CLAUDE.md). Must return 501 unconditionally, without calling Jira at all.
    app = FastAPI()
    app.include_router(get_v1_jira_router(mock_jira_client))
    c = TestClient(app)
    response = c.post(f"{PREFIX}/user-dirs/sync")
    assert response.status_code == 501
    assert response.json()["status"] == "Failed"
    mock_jira_client.post.assert_not_called()
