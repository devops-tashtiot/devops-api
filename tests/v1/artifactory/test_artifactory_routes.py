import json as json_module
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.v1.artifactory.conf import config
from app.v1.artifactory.routes import get_v1_artifactory_router


def make_response(status_code=200, data=None):
    r = MagicMock()
    r.status_code = status_code
    r.text = json_module.dumps(data) if data is not None else ""
    r.json = MagicMock(return_value=data if data is not None else {})
    return r

PREFIX = config.API_PREFIX

VALID_PROJECT_PAYLOAD = {
    "name": "my-project",
    "storage_quota_giga_bytes": 2,
    "admin_user": "alice",
}

VALID_PERMISSION_USER_PAYLOAD = {
    "project_key": "my-project",
    "member_name": "alice",
    "member_type": "user",
    "roles": ["Developer"],
}

VALID_PERMISSION_GROUP_PAYLOAD = {
    "project_key": "my-project",
    "member_name": "ad-group-devops",
    "member_type": "group",
    "roles": ["Developer"],
}


# ── POST / ────────────────────────────────────────────────────────────────────

def test_create_project_returns_200(client):
    response = client.post(f"{PREFIX}/", json=VALID_PROJECT_PAYLOAD)
    assert response.status_code == 200
    assert response.json()["status"] == "successful"


def test_create_project_with_admin_user_calls_post_and_put(client, mock_artifactory_client):
    client.post(f"{PREFIX}/", json=VALID_PROJECT_PAYLOAD)
    assert mock_artifactory_client.post.call_count == 1
    assert mock_artifactory_client.put.call_count == 1
    assert "projects" in mock_artifactory_client.post.call_args.args[0]
    assert "users/alice" in mock_artifactory_client.put.call_args.args[0]


def test_create_project_with_admin_group_calls_post_and_put(client, mock_artifactory_client):
    payload = {**VALID_PROJECT_PAYLOAD, "admin_user": None, "admin_group": "devops-team"}
    client.post(f"{PREFIX}/", json=payload)
    assert mock_artifactory_client.post.call_count == 1
    assert mock_artifactory_client.put.call_count == 1
    assert "groups/devops-team" in mock_artifactory_client.put.call_args.args[0]


def test_create_project_with_both_admin_user_and_group_calls_two_puts(client, mock_artifactory_client):
    payload = {**VALID_PROJECT_PAYLOAD, "admin_group": "devops-team"}
    client.post(f"{PREFIX}/", json=payload)
    assert mock_artifactory_client.put.call_count == 2


def test_create_project_external_error_returns_error_response(mock_artifactory_client):
    mock_artifactory_client.post = AsyncMock(return_value=make_response(409, {"message": "already exists"}))
    app = FastAPI()
    app.include_router(get_v1_artifactory_router(mock_artifactory_client))
    c = TestClient(app)

    response = c.post(f"{PREFIX}/", json=VALID_PROJECT_PAYLOAD)
    assert response.status_code == 409
    assert response.json()["status"] == "Failed"


def test_create_project_unexpected_exception_triggers_rollback(mock_artifactory_client):
    # Rollback fires only on bare (non-HTTP) exceptions — e.g. create succeeds but admin assignment crashes
    mock_artifactory_client.post = AsyncMock(return_value=make_response(200))
    mock_artifactory_client.put = AsyncMock(side_effect=Exception("unexpected network failure"))
    app = FastAPI()
    app.include_router(get_v1_artifactory_router(mock_artifactory_client))
    c = TestClient(app)

    c.post(f"{PREFIX}/", json=VALID_PROJECT_PAYLOAD)
    assert mock_artifactory_client.delete.call_count == 1
    assert "projects" in mock_artifactory_client.delete.call_args.args[0]


def test_create_project_http_error_does_not_rollback(mock_artifactory_client):
    # HTTPException (e.g. 500 from upstream) is caught separately — no rollback, just returns ExceptionResponse
    mock_artifactory_client.post = AsyncMock(return_value=make_response(500))
    app = FastAPI()
    app.include_router(get_v1_artifactory_router(mock_artifactory_client))
    c = TestClient(app)

    c.post(f"{PREFIX}/", json=VALID_PROJECT_PAYLOAD)
    assert mock_artifactory_client.delete.call_count == 0


# ── POST /storage-quota ───────────────────────────────────────────────────────

def test_storage_quota_returns_201(client):
    response = client.post(f"{PREFIX}/storage-quota", json={"name": "my-project", "storage_quota_giga_bytes": 1})
    assert response.status_code == 201
    assert response.json()["status"] == "successful"


def test_storage_quota_calls_get_then_put(client, mock_artifactory_client):
    client.post(f"{PREFIX}/storage-quota", json={"name": "my-project", "storage_quota_giga_bytes": 1})
    assert mock_artifactory_client.get.call_count == 1
    assert mock_artifactory_client.put.call_count == 1
    assert "projects/my-project" in mock_artifactory_client.get.call_args.args[0]


def test_storage_quota_adds_to_existing_quota(client, mock_artifactory_client):
    client.post(f"{PREFIX}/storage-quota", json={"name": "my-project", "storage_quota_giga_bytes": 1})
    put_body = mock_artifactory_client.put.call_args.kwargs["json"]
    # 1 GB added to existing 1 GB = 2 GB in bytes
    assert put_body["storage_quota_bytes"] == 2 * 1024 ** 3


# ── GET /permissions/roles/{role_name} ───────────────────────────────────────

def test_get_role_by_name_returns_200(client):
    response = client.get(f"{PREFIX}/permissions/roles/Developer")
    assert response.status_code == 200


def test_get_role_by_name_calls_correct_endpoint(client, mock_artifactory_client):
    client.get(f"{PREFIX}/permissions/roles/Developer")
    assert mock_artifactory_client.get.call_count == 1
    assert "roles/Developer" in mock_artifactory_client.get.call_args.args[0]


# ── POST /permissions — user ──────────────────────────────────────────────────

def test_grant_permission_user_returns_200(client):
    response = client.post(f"{PREFIX}/permissions", json=VALID_PERMISSION_USER_PAYLOAD)
    assert response.status_code == 200
    assert response.json()["status"] == "successful"


def test_grant_permission_user_only_calls_put(client, mock_artifactory_client):
    client.post(f"{PREFIX}/permissions", json=VALID_PERMISSION_USER_PAYLOAD)
    assert mock_artifactory_client.get.call_count == 0
    assert mock_artifactory_client.post.call_count == 0
    assert mock_artifactory_client.put.call_count == 1
    assert "projects/my-project/users/alice" in mock_artifactory_client.put.call_args.args[0]


def test_grant_permission_user_sends_correct_roles(client, mock_artifactory_client):
    client.post(f"{PREFIX}/permissions", json=VALID_PERMISSION_USER_PAYLOAD)
    body = mock_artifactory_client.put.call_args.kwargs["json"]
    assert body["roles"] == ["Developer"]
    assert body["name"] == "alice"


# ── POST /permissions — group already in JFrog ────────────────────────────────

def test_grant_permission_existing_group_returns_200():
    c = MagicMock()
    c.get = AsyncMock(return_value=make_response(200))
    c.put = AsyncMock(return_value=make_response(200))
    c.post = AsyncMock(return_value=make_response(200))
    app = FastAPI()
    app.include_router(get_v1_artifactory_router(c))
    response = TestClient(app).post(f"{PREFIX}/permissions", json=VALID_PERMISSION_GROUP_PAYLOAD)
    assert response.status_code == 200
    assert response.json()["status"] == "successful"


def test_grant_permission_existing_group_skips_ldap_sync():
    c = MagicMock()
    c.get = AsyncMock(return_value=make_response(200))
    c.put = AsyncMock(return_value=make_response(200))
    c.post = AsyncMock(return_value=make_response(200))
    app = FastAPI()
    app.include_router(get_v1_artifactory_router(c))
    TestClient(app).post(f"{PREFIX}/permissions", json=VALID_PERMISSION_GROUP_PAYLOAD)

    assert c.get.call_count == 1
    assert "groups/ad-group-devops" in c.get.call_args.args[0]
    assert c.post.call_count == 0
    assert c.put.call_count == 1
    assert "projects/my-project/groups/ad-group-devops" in c.put.call_args.args[0]


# ── POST /permissions — group not yet imported ────────────────────────────────

def test_grant_permission_new_group_imports_from_ldap_then_assigns():
    c = MagicMock()
    c.get = AsyncMock(return_value=make_response(404))
    c.post = AsyncMock(return_value=make_response(200))
    c.put = AsyncMock(return_value=make_response(200))
    app = FastAPI()
    app.include_router(get_v1_artifactory_router(c))
    response = TestClient(app).post(f"{PREFIX}/permissions", json=VALID_PERMISSION_GROUP_PAYLOAD)

    assert response.status_code == 200
    assert c.get.call_count == 1
    assert c.post.call_count == 1
    assert "ldap/groups/sync" in c.post.call_args.args[0]
    assert c.put.call_count == 1
    assert "projects/my-project/groups/ad-group-devops" in c.put.call_args.args[0]


def test_grant_permission_new_group_sync_payload_contains_group_name():
    c = MagicMock()
    c.get = AsyncMock(return_value=make_response(404))
    c.post = AsyncMock(return_value=make_response(200))
    c.put = AsyncMock(return_value=make_response(200))
    app = FastAPI()
    app.include_router(get_v1_artifactory_router(c))
    TestClient(app).post(f"{PREFIX}/permissions", json=VALID_PERMISSION_GROUP_PAYLOAD)

    sync_body = c.post.call_args.kwargs["json"]
    assert "ad-group-devops" in sync_body["groups"]


# ── GET /permissions/{project_key} ────────────────────────────────────────────

def test_get_permissions_returns_200():
    c = MagicMock()
    users = [{"name": "alice", "roles": ["Developer"]}]
    groups = [{"name": "devops-team", "roles": ["Project Admin"]}]
    c.get = AsyncMock(side_effect=[make_response(200, users), make_response(200, groups)])
    app = FastAPI()
    app.include_router(get_v1_artifactory_router(c))
    response = TestClient(app).get(f"{PREFIX}/permissions/my-project")

    assert response.status_code == 200
    data = response.json()
    assert data["users"] == users
    assert data["groups"] == groups


def test_get_permissions_calls_users_and_groups_endpoints():
    c = MagicMock()
    c.get = AsyncMock(side_effect=[make_response(200, []), make_response(200, [])])
    app = FastAPI()
    app.include_router(get_v1_artifactory_router(c))
    TestClient(app).get(f"{PREFIX}/permissions/my-project")

    assert c.get.call_count == 2
    endpoints = [call.args[0] for call in c.get.call_args_list]
    assert any("users" in ep for ep in endpoints)
    assert any("groups" in ep for ep in endpoints)
    assert all("my-project" in ep for ep in endpoints)
