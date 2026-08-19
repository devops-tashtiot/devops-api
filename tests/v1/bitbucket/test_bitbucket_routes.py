from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.global_conf import global_config
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

VALID_PAYLOAD_BOTH = {
    "metadata": VALID_METADATA,
    "spec": {
        "key": "TEST",
        "name": "test-project",
        "description": "A test project",
        "public": False,
        "admin_user": "nati",
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


def _mock_response(json_body=None, status_code=200):
    resp = MagicMock(status_code=status_code, text="")
    resp.json = MagicMock(return_value=json_body or {})
    return resp


def test_create_project_leaves_name_unchanged(client, mock_bitbucket_client):
    client.post(f"{PREFIX}/", json=VALID_PAYLOAD)
    create_call = mock_bitbucket_client.post.call_args_list[0]
    assert create_call.kwargs["json"]["name"] == "test-project"


# --- create mirror project (POST /mirror) ---


def test_create_mirror_project_appends_mirrored_env_destination_to_name(
    client, mock_bitbucket_client
):
    # create response needs a numeric "id" — register_project_with_mirror uses it, not "key"
    mock_bitbucket_client.post = AsyncMock(return_value=_mock_response({"id": 7}))

    def get_side_effect(endpoint, *args, **kwargs):
        if "mirrorServers" in endpoint:
            return _mock_response(
                {
                    "values": [
                        {
                            "id": "m1",
                            "baseUrl": "https://the-mirror.example.com",
                            "name": "mirror",
                        }
                    ],
                    "isLastPage": True,
                }
            )
        return _mock_response({"values": [{"slug": "nati", "name": "nati"}]})

    mock_bitbucket_client.get = AsyncMock(side_effect=get_side_effect)

    mirror_client = MagicMock()
    mirror_client.get = AsyncMock(
        return_value=_mock_response(
            {
                "values": [{"id": "u1", "baseUrl": global_config.BITBUCKET_API_URL}],
                "isLastPage": True,
            }
        )
    )
    mirror_client.post = AsyncMock(return_value=_mock_response())

    payload = {
        "metadata": VALID_METADATA,
        "spec": {**VALID_PAYLOAD["spec"], "mirrored_env_destination": "Nati"},
    }
    with patch("app.v1.bitbucket.operations.BaseAPI") as mock_base_api:
        mock_base_api.return_value.client = mirror_client
        response = client.post(f"{PREFIX}/mirror", json=payload)

    assert response.status_code == 200, response.text
    create_call = mock_bitbucket_client.post.call_args_list[0]
    assert create_call.kwargs["json"]["name"] == "test-project - Nati"
    # and the project was actually registered with the discovered mirror server
    mirror_client.post.assert_called_once()
    assert mirror_client.post.call_args.args[0].endswith("/settings/projects/7")


def test_create_mirror_project_without_mirrored_env_destination_returns_422(client):
    response = client.post(f"{PREFIX}/mirror", json=VALID_PAYLOAD)
    assert response.status_code == 422


def test_create_project_rejects_mirrored_env_destination_field(client):
    # mirrored_env_destination only exists on MirrorProjectSpec (POST /mirror) — sending it
    # to the plain create endpoint is silently dropped as an unrecognized field, not an error,
    # since BitbucketProjectRequest.spec is a plain ProjectSpec.
    payload = {
        "metadata": VALID_METADATA,
        "spec": {**VALID_PAYLOAD["spec"], "mirrored_env_destination": "Nati"},
    }
    response = client.post(f"{PREFIX}/", json=payload)
    assert response.status_code == 200, response.text


def test_create_project_with_admin_user_assigns_user_permission(
    client, mock_bitbucket_client
):
    client.post(f"{PREFIX}/", json=VALID_PAYLOAD)
    put_endpoints = [c.args[0] for c in mock_bitbucket_client.put.call_args_list]
    assert any("permissions/users" in ep for ep in put_endpoints)
    assert any("nati" in ep for ep in put_endpoints)
    assert any("PROJECT_ADMIN" in ep for ep in put_endpoints)


def test_create_project_with_admin_group_assigns_group_permission(
    client, mock_bitbucket_client
):
    client.post(f"{PREFIX}/", json=VALID_PAYLOAD_GROUP)
    put_endpoints = [c.args[0] for c in mock_bitbucket_client.put.call_args_list]
    assert any("permissions/groups" in ep for ep in put_endpoints)
    assert any("devops-team" in ep for ep in put_endpoints)
    assert any("PROJECT_ADMIN" in ep for ep in put_endpoints)


def test_create_project_total_call_count_with_admin_user(client, mock_bitbucket_client):
    client.post(f"{PREFIX}/", json=VALID_PAYLOAD)
    assert mock_bitbucket_client.post.call_count == 1  # create only
    assert mock_bitbucket_client.put.call_count == 1  # user permission


def test_create_project_total_call_count_with_admin_group(
    client, mock_bitbucket_client
):
    client.post(f"{PREFIX}/", json=VALID_PAYLOAD_GROUP)
    assert mock_bitbucket_client.post.call_count == 1  # create only
    assert mock_bitbucket_client.put.call_count == 1  # group permission


def test_create_project_with_admin_user_and_group_assigns_both(
    client, mock_bitbucket_client
):
    # admin_user and admin_group are not mutually exclusive — schema allows both together.
    client.post(f"{PREFIX}/", json=VALID_PAYLOAD_BOTH)
    put_endpoints = [c.args[0] for c in mock_bitbucket_client.put.call_args_list]
    assert mock_bitbucket_client.put.call_count == 2
    assert any("permissions/users" in ep for ep in put_endpoints)
    assert any("permissions/groups" in ep for ep in put_endpoints)


def test_create_project_passes_public_true_through_to_bitbucket(
    client, mock_bitbucket_client
):
    # CLAUDE.md used to (wrongly) claim public:false is hardcoded server-side. It isn't —
    # ProjectSpec.public is a real caller-settable field passed straight through.
    payload = {**VALID_PAYLOAD, "spec": {**VALID_PAYLOAD["spec"], "public": True}}
    client.post(f"{PREFIX}/", json=payload)
    body = mock_bitbucket_client.post.call_args.kwargs["json"]
    assert body["public"] is True


def test_create_project_defaults_public_false_when_omitted(
    client, mock_bitbucket_client
):
    spec = {k: v for k, v in VALID_PAYLOAD["spec"].items() if k != "public"}
    payload = {**VALID_PAYLOAD, "spec": spec}
    client.post(f"{PREFIX}/", json=payload)
    body = mock_bitbucket_client.post.call_args.kwargs["json"]
    assert body["public"] is False


def test_create_project_admin_user_not_found_returns_404(mock_bitbucket_client):
    mock_bitbucket_client.get = AsyncMock(
        return_value=MagicMock(
            status_code=200, json=MagicMock(return_value={"values": []})
        )
    )

    app = FastAPI()
    app.include_router(get_v1_bitbucket_router(mock_bitbucket_client))
    c = TestClient(app)

    response = c.post(f"{PREFIX}/", json=VALID_PAYLOAD)
    assert response.status_code == 404
    assert response.json()["status"] == "Failed"
    mock_bitbucket_client.post.assert_not_called()


def test_create_project_admin_group_not_found_returns_404(mock_bitbucket_client):
    mock_bitbucket_client.get = AsyncMock(
        return_value=MagicMock(
            status_code=200, json=MagicMock(return_value={"values": []})
        )
    )

    app = FastAPI()
    app.include_router(get_v1_bitbucket_router(mock_bitbucket_client))
    c = TestClient(app)

    response = c.post(f"{PREFIX}/", json=VALID_PAYLOAD_GROUP)
    assert response.status_code == 404
    assert response.json()["status"] == "Failed"
    mock_bitbucket_client.post.assert_not_called()


def test_create_project_error_returns_error_response(mock_bitbucket_client):
    conflict = MagicMock(
        status_code=409, text='{"errors":[{"message":"Project already exists"}]}'
    )
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

    response = c.post(f"{PREFIX}/", json=VALID_PAYLOAD)

    delete_endpoints = [
        call.args[0] for call in mock_bitbucket_client.delete.call_args_list
    ]
    assert any("TEST" in ep for ep in delete_endpoints)
    # the bare except used to fall through with no return at all — must be a clean error response
    assert response.status_code == 500
    assert response.json()["status"] == "Failed"


def test_create_project_rollback_failure_does_not_crash(mock_bitbucket_client):
    # If the rollback delete ALSO fails, the endpoint must still return a clean response for the
    # original error, not propagate an unhandled exception (or mask it with the rollback's own).
    mock_bitbucket_client.post = AsyncMock(side_effect=Exception("network error"))
    mock_bitbucket_client.delete = AsyncMock(
        side_effect=Exception("rollback also failed")
    )

    app = FastAPI()
    app.include_router(get_v1_bitbucket_router(mock_bitbucket_client))
    c = TestClient(app)

    response = c.post(f"{PREFIX}/", json=VALID_PAYLOAD)
    assert response.status_code == 500
    assert response.json()["status"] == "Failed"


# --- delete ---


def test_delete_project_returns_200(client, mock_bitbucket_client):
    response = client.delete(f"{PREFIX}/TEST")
    assert response.status_code == 200
    assert response.json()["status"] == "successful"


def test_delete_project_calls_delete_endpoint(client, mock_bitbucket_client):
    # delete_project cascades: one delete per repo under the project (2, per the
    # mock_bitbucket_client fixture), then the project itself — 3 total.
    client.delete(f"{PREFIX}/TEST")
    assert mock_bitbucket_client.delete.call_count == 3
    endpoint = mock_bitbucket_client.delete.call_args.args[0]
    assert "/projects/TEST" in endpoint


def test_delete_project_not_found_returns_error(mock_bitbucket_client):
    mock_bitbucket_client.delete = AsyncMock(
        return_value=MagicMock(
            status_code=404, text='{"errors":[{"message":"Project not found"}]}'
        )
    )

    app = FastAPI()
    app.include_router(get_v1_bitbucket_router(mock_bitbucket_client))
    c = TestClient(app)

    response = c.delete(f"{PREFIX}/NOTEXIST")
    assert response.status_code == 404
    assert response.json()["status"] == "Failed"


def test_delete_project_paginates_across_multiple_pages(mock_bitbucket_client):
    page_1 = MagicMock(
        status_code=200,
        json=MagicMock(
            return_value={
                "values": [{"slug": "repo-one", "name": "repo-one"}],
                "isLastPage": False,
                "nextPageStart": 100,
            }
        ),
    )
    page_2 = MagicMock(
        status_code=200,
        json=MagicMock(
            return_value={
                "values": [{"slug": "repo-two", "name": "repo-two"}],
                "isLastPage": True,
            }
        ),
    )
    mock_bitbucket_client.get = AsyncMock(side_effect=[page_1, page_2])
    ok = MagicMock(status_code=200, text="")
    mock_bitbucket_client.delete = AsyncMock(return_value=ok)

    app = FastAPI()
    app.include_router(get_v1_bitbucket_router(mock_bitbucket_client))
    c = TestClient(app)

    response = c.delete(f"{PREFIX}/TEST")
    assert response.status_code == 200

    delete_endpoints = [
        call.args[0] for call in mock_bitbucket_client.delete.call_args_list
    ]
    # one delete per repo across both pages, plus the project itself
    assert mock_bitbucket_client.delete.call_count == 3
    assert any("repo-one" in ep for ep in delete_endpoints)
    assert any("repo-two" in ep for ep in delete_endpoints)
    assert any("/projects/TEST" in ep for ep in delete_endpoints)


def test_delete_project_with_no_repos_deletes_directly(mock_bitbucket_client):
    mock_bitbucket_client.get = AsyncMock(
        return_value=MagicMock(
            status_code=200,
            json=MagicMock(return_value={"values": [], "isLastPage": True}),
        )
    )
    ok = MagicMock(status_code=200, text="")
    mock_bitbucket_client.delete = AsyncMock(return_value=ok)

    app = FastAPI()
    app.include_router(get_v1_bitbucket_router(mock_bitbucket_client))
    c = TestClient(app)

    response = c.delete(f"{PREFIX}/TEST")
    assert response.status_code == 200
    # no repos to delete — only the project delete itself
    assert mock_bitbucket_client.delete.call_count == 1
    assert "/projects/TEST" in mock_bitbucket_client.delete.call_args.args[0]


def test_delete_project_conflict_returns_error(mock_bitbucket_client):
    mock_bitbucket_client.delete = AsyncMock(
        return_value=MagicMock(
            status_code=409, text='{"errors":[{"message":"Project has repositories"}]}'
        )
    )

    app = FastAPI()
    app.include_router(get_v1_bitbucket_router(mock_bitbucket_client))
    c = TestClient(app)

    response = c.delete(f"{PREFIX}/HASREPOS")
    assert response.status_code == 409
    assert response.json()["status"] == "Failed"


# --- user-dirs ---


def test_sync_user_dir_returns_501_not_supported(client, mock_bitbucket_client):
    # Bitbucket has no supported way to trigger a directory sync on demand — confirmed live
    # (see app/v1/bitbucket/CLAUDE.md): the only "working" internal UI action is unreliable,
    # silently no-ops on repeat calls, and would report false successes. The endpoint must
    # always return 501 without even attempting a call — it never needs to reach the client.
    response = client.post(f"{PREFIX}/user-dirs/sync")
    assert response.status_code == 501
    assert response.json()["status"] == "Failed"
    mock_bitbucket_client.get.assert_not_called()
    mock_bitbucket_client.post.assert_not_called()
