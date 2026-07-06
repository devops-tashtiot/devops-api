from unittest.mock import AsyncMock, MagicMock, patch

from app.v1.argocd.conf import config
from app.global_conf import global_config

PREFIX = config.API_PREFIX
VALID_ENV = global_config.ARGOCD_ALLOWED_ENVS[0]
VALID_SIZE = config.ARGOCD_ALLOWED_SIZES[0]
VALID_RESOURCE = config.ARGOCD_ALLOWED_RESOURCES[0]

VALID_METADATA = {
    "project": "test-project",
    "network": "test-network",
    "region": "test-region",
    "space": "test-space",
    "environment": "test-env",
}

VALID_CONSUMER_PAYLOAD = {
    "metadata": VALID_METADATA,
    "spec": {
        "name": "my-consumer",
        "environment": VALID_ENV,
        "size": VALID_SIZE,
        "include_resources": [VALID_RESOURCE],
        "ad_admin_group": "my-group",
    },
}

VALID_CLUSTER = {
    "name": "openshift",
    "namespace": "default",
    "address": "https://127.0.0.1:6443",
    "token": "fake-token",
}

VALID_CLUSTER_SECRET_PAYLOAD = {
    "metadata": VALID_METADATA,
    "spec": {
        "username": "admin",
        "password": "pass",
        "chosen_name": "nati",
        "app_name": "netanel",
        "application_clusters": [VALID_CLUSTER],
    },
}

VALID_CLUSTER_UPDATE_PAYLOAD = {
    "metadata": VALID_METADATA,
    "spec": {
        "username": "admin",
        "password": "pass",
        "application_clusters": [VALID_CLUSTER],
    },
}


# GET /sizes

def test_get_sizes_returns_200(client):
    assert client.get(f"{PREFIX}/sizes").status_code == 200


def test_get_sizes_returns_nonempty_list(client):
    data = client.get(f"{PREFIX}/sizes").json()
    assert isinstance(data, list) and len(data) > 0


# GET /include-resources

def test_get_include_resources_returns_200(client):
    assert client.get(f"{PREFIX}/include-resources").status_code == 200


def test_get_include_resources_returns_nonempty_list(client):
    data = client.get(f"{PREFIX}/include-resources").json()
    assert isinstance(data, list) and len(data) > 0


# GET /environments

def test_get_environments_returns_200(client):
    assert client.get(f"{PREFIX}/environments").status_code == 200


def test_get_environments_returns_nonempty_list(client):
    data = client.get(f"{PREFIX}/environments").json()
    assert isinstance(data, list) and len(data) > 0


# POST /  (create consumer config)

def test_create_consumer_returns_200(client):
    response = client.post(f"{PREFIX}/", json=VALID_CONSUMER_PAYLOAD)
    assert response.status_code == 200
    assert response.json()["status"] == "successful"


def test_create_consumer_calls_git_add_file_once(client, mock_git):
    client.post(f"{PREFIX}/", json=VALID_CONSUMER_PAYLOAD)
    assert mock_git.add_file.call_count == 1


def test_create_consumer_path_contains_env_and_name(client, mock_git):
    client.post(f"{PREFIX}/", json=VALID_CONSUMER_PAYLOAD)
    path = mock_git.add_file.call_args.args[0]
    assert VALID_ENV in path
    assert VALID_CONSUMER_PAYLOAD["spec"]["name"] in path


def test_create_consumer_invalid_name_returns_422(client):
    payload = {**VALID_CONSUMER_PAYLOAD, "spec": {**VALID_CONSUMER_PAYLOAD["spec"], "name": "bad name!"}}
    assert client.post(f"{PREFIX}/", json=payload).status_code == 422


def test_create_consumer_invalid_env_returns_422(client):
    payload = {**VALID_CONSUMER_PAYLOAD, "spec": {**VALID_CONSUMER_PAYLOAD["spec"], "environment": "nonexistent-env"}}
    assert client.post(f"{PREFIX}/", json=payload).status_code == 422


def test_create_consumer_invalid_size_returns_422(client):
    payload = {**VALID_CONSUMER_PAYLOAD, "spec": {**VALID_CONSUMER_PAYLOAD["spec"], "size": "supersize"}}
    assert client.post(f"{PREFIX}/", json=payload).status_code == 422


def test_create_consumer_invalid_resource_returns_422(client):
    payload = {**VALID_CONSUMER_PAYLOAD, "spec": {**VALID_CONSUMER_PAYLOAD["spec"], "include_resources": ["Pod"]}}
    assert client.post(f"{PREFIX}/", json=payload).status_code == 422


# DELETE /{env}/{name}  (delete consumer config)

def test_delete_consumer_returns_200(client):
    response = client.delete(f"{PREFIX}/{VALID_ENV}/my-consumer")
    assert response.status_code == 200
    assert response.json()["status"] == "successful"


def test_delete_consumer_calls_git_delete_file_once(client, mock_git):
    client.delete(f"{PREFIX}/{VALID_ENV}/my-consumer")
    assert mock_git.delete_file.call_count == 1


def test_delete_consumer_path_contains_env_and_name(client, mock_git):
    client.delete(f"{PREFIX}/{VALID_ENV}/my-consumer")
    path = mock_git.delete_file.call_args.args[0]
    assert VALID_ENV in path
    assert "my-consumer" in path


# POST /cluster-secret

def _mock_argocd_for_create():
    argocd = MagicMock()
    argocd.create_app = AsyncMock(return_value=None)
    argocd.sync = AsyncMock(return_value=None)
    return argocd


def test_create_cluster_secret_returns_200(client):
    mock_argocd = _mock_argocd_for_create()
    with patch("app.v1.argocd.operations._check_cluster_permissions", new=AsyncMock(return_value=None)), \
         patch("app.v1.argocd.operations._build_argocd", new=AsyncMock(return_value=mock_argocd)):
        response = client.post(f"{PREFIX}/cluster-secret", json=VALID_CLUSTER_SECRET_PAYLOAD)
    assert response.status_code == 200
    assert response.json()["status"] == "successful"


def test_create_cluster_secret_calls_create_app_and_sync(client):
    mock_argocd = _mock_argocd_for_create()
    with patch("app.v1.argocd.operations._check_cluster_permissions", new=AsyncMock(return_value=None)), \
         patch("app.v1.argocd.operations._build_argocd", new=AsyncMock(return_value=mock_argocd)):
        client.post(f"{PREFIX}/cluster-secret", json=VALID_CLUSTER_SECRET_PAYLOAD)
    assert mock_argocd.create_app.call_count == 1
    assert mock_argocd.sync.call_count == 1


def test_create_cluster_secret_missing_clusters_returns_422(client):
    payload = {**VALID_CLUSTER_SECRET_PAYLOAD, "spec": {**VALID_CLUSTER_SECRET_PAYLOAD["spec"], "application_clusters": []}}
    assert client.post(f"{PREFIX}/cluster-secret", json=payload).status_code == 422


# DELETE /cluster-secret

def test_delete_cluster_secret_returns_200(client):
    mock_argocd = MagicMock()
    mock_argocd.delete_app = AsyncMock(return_value=None)
    with patch("app.v1.argocd.operations._build_argocd", new=AsyncMock(return_value=mock_argocd)):
        response = client.delete(
            f"{PREFIX}/cluster-secret",
            params={"username": "admin", "password": "pass", "app_name": "netanel", "chosen_name": "nati"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "successful"


def test_delete_cluster_secret_calls_delete_app_once(client):
    mock_argocd = MagicMock()
    mock_argocd.delete_app = AsyncMock(return_value=None)
    with patch("app.v1.argocd.operations._build_argocd", new=AsyncMock(return_value=mock_argocd)):
        client.delete(
            f"{PREFIX}/cluster-secret",
            params={"username": "admin", "password": "pass", "app_name": "netanel", "chosen_name": "nati"},
        )
    assert mock_argocd.delete_app.call_count == 1


# PUT /cluster-secret/{app_name}/{chosen_name}

def test_edit_cluster_secret_returns_200(client):
    mock_argocd = MagicMock()
    mock_argocd.modify_parameters = AsyncMock(return_value=None)
    mock_argocd.sync = AsyncMock(return_value=None)
    with patch("app.v1.argocd.operations._build_argocd", new=AsyncMock(return_value=mock_argocd)):
        response = client.put(
            f"{PREFIX}/cluster-secret/netanel/nati",
            json=VALID_CLUSTER_UPDATE_PAYLOAD,
        )
    assert response.status_code == 200
    assert response.json()["status"] == "successful"


def test_edit_cluster_secret_calls_modify_and_sync(client):
    mock_argocd = MagicMock()
    mock_argocd.modify_parameters = AsyncMock(return_value=None)
    mock_argocd.sync = AsyncMock(return_value=None)
    with patch("app.v1.argocd.operations._build_argocd", new=AsyncMock(return_value=mock_argocd)):
        client.put(
            f"{PREFIX}/cluster-secret/netanel/nati",
            json=VALID_CLUSTER_UPDATE_PAYLOAD,
        )
    assert mock_argocd.modify_parameters.call_count == 1
    assert mock_argocd.sync.call_count == 1
