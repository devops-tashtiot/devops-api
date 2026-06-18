import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.v1.sonarqube.conf import config
from app.v1.sonarqube.operations import SONARQUBE_GLOBAL_PERMISSIONS, SONARQUBE_TEMPLATE_PERMISSIONS
from app.v1.sonarqube.routes import get_v1_sonarqube_router

PREFIX = config.API_PREFIX
# 1 create + N global permissions + N template permissions
EXPECTED_CALL_COUNT = 1 + len(SONARQUBE_GLOBAL_PERMISSIONS) + len(SONARQUBE_TEMPLATE_PERMISSIONS)


VALID_PAYLOAD = {"consumer_name": "test-consumer", "name": "check"}


def test_create_group_check_returns_200(client, mock_sonar_client):
    response = client.post(f"{PREFIX}/", json=VALID_PAYLOAD)
    assert response.status_code == 200
    assert response.json()["status"] == "successful"


def test_create_group_calls_all_operations(client, mock_sonar_client):
    client.post(f"{PREFIX}/", json=VALID_PAYLOAD)
    assert mock_sonar_client.post.call_count == EXPECTED_CALL_COUNT


def test_create_group_calls_create_endpoint(client, mock_sonar_client):
    client.post(f"{PREFIX}/", json=VALID_PAYLOAD)
    endpoints = [c.args[0] for c in mock_sonar_client.post.call_args_list]
    assert any("user_groups/create" in ep for ep in endpoints)


def test_create_group_assigns_all_global_permissions(client, mock_sonar_client):
    client.post(f"{PREFIX}/", json=VALID_PAYLOAD)
    calls = mock_sonar_client.post.call_args_list
    global_calls = [
        c for c in calls
        if "permissions/add_group" in c.args[0] and "template" not in c.args[0]
    ]
    granted = {c.kwargs["params"]["permission"] for c in global_calls}
    assert granted == set(SONARQUBE_GLOBAL_PERMISSIONS)
    for c in global_calls:
        assert c.kwargs["params"]["groupName"] == "check"


def test_create_group_assigns_all_template_permissions(client, mock_sonar_client):
    client.post(f"{PREFIX}/", json=VALID_PAYLOAD)
    calls = mock_sonar_client.post.call_args_list
    template_calls = [
        c for c in calls if "permissions/add_group_to_template" in c.args[0]
    ]
    granted = {c.kwargs["params"]["permission"] for c in template_calls}
    assert granted == set(SONARQUBE_TEMPLATE_PERMISSIONS)
    for c in template_calls:
        assert c.kwargs["params"]["groupName"] == "check"
        assert c.kwargs["params"]["templateName"] == config.SONARQUBE_ADMIN_TEMPLATE_NAME


def test_create_group_already_exists_returns_400(mock_sonar_client):
    conflict = MagicMock()
    conflict.status_code = 400
    conflict.text = "Group 'check' already exists"
    mock_sonar_client.post = AsyncMock(return_value=conflict)

    app = FastAPI()
    app.include_router(get_v1_sonarqube_router())
    client = TestClient(app)

    response = client.post(f"{PREFIX}/", json=VALID_PAYLOAD)

    assert response.status_code == 400
    assert response.json()["status"] == "Failed"
    assert "already exists" in response.json()["stdout"]


def test_create_group_already_exists_does_not_rollback(mock_sonar_client):
    conflict = MagicMock()
    conflict.status_code = 400
    conflict.text = "Group 'check' already exists"
    mock_sonar_client.post = AsyncMock(return_value=conflict)

    app = FastAPI()
    app.include_router(get_v1_sonarqube_router())
    client = TestClient(app)

    client.post(f"{PREFIX}/", json=VALID_PAYLOAD)

    # Only the create call should fire — no rollback delete, no permission calls
    assert mock_sonar_client.post.call_count == 1
    assert "user_groups/create" in mock_sonar_client.post.call_args.args[0]


def test_create_group_invalid_name_returns_422(client):
    response = client.post(f"{PREFIX}/", json={"consumer_name": "test-consumer", "name": "invalid name!"})
    assert response.status_code == 422


def test_create_group_empty_name_returns_422(client):
    response = client.post(f"{PREFIX}/", json={"consumer_name": "test-consumer", "name": ""})
    assert response.status_code == 422


def test_delete_group_returns_200(client, mock_sonar_client):
    response = client.delete(f"{PREFIX}/test-consumer/check")
    assert response.status_code == 200
    assert response.json()["status"] == "successful"


def test_delete_group_calls_delete_endpoint(client, mock_sonar_client):
    client.delete(f"{PREFIX}/test-consumer/check")
    assert mock_sonar_client.post.call_count == 1
    endpoint = mock_sonar_client.post.call_args.args[0]
    assert "user_groups/delete" in endpoint
    assert mock_sonar_client.post.call_args.kwargs["params"]["name"] == "check"


def test_delete_group_error_returns_error_response(mock_sonar_client):
    mock_sonar_client.post = AsyncMock(return_value=MagicMock(status_code=404, text="Group not found"))

    app = FastAPI()
    app.include_router(get_v1_sonarqube_router())
    c = TestClient(app)

    response = c.delete(f"{PREFIX}/test-consumer/check")
    assert response.status_code == 404
    assert response.json()["status"] == "Failed"


def test_create_group_unexpected_error_triggers_rollback(mock_sonar_client):
    ok = MagicMock(status_code=200, text="")
    # First call (create) raises unexpectedly; second call (rollback delete) succeeds
    mock_sonar_client.post = AsyncMock(side_effect=[Exception("network error"), ok])

    app = FastAPI()
    app.include_router(get_v1_sonarqube_router())
    c = TestClient(app)

    c.post(f"{PREFIX}/", json=VALID_PAYLOAD)

    assert mock_sonar_client.post.call_count == 2
    endpoints = [call.args[0] for call in mock_sonar_client.post.call_args_list]
    assert any("user_groups/create" in ep for ep in endpoints)
    assert any("user_groups/delete" in ep for ep in endpoints)
