"""Error-path unit tests for bitbucket operations — exercise the `except Exception`
branches and _handle_response's non-JSON fallback."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.v1.bitbucket import operations as ops
from app.v1.bitbucket.schemas import MirrorProjectSpec


def _raising_client():
    client = MagicMock()
    boom = AsyncMock(side_effect=RuntimeError("boom"))
    client.get = boom
    client.post = boom
    client.put = boom
    client.delete = boom
    return client


def test_handle_response_non_json_falls_back_to_text():
    resp = MagicMock(status_code=409, text="conflict text")
    resp.json = MagicMock(side_effect=ValueError("not json"))
    with pytest.raises(HTTPException) as exc:
        ops._handle_response(resp)
    assert exc.value.status_code == 409
    assert exc.value.detail == "conflict text"


@pytest.mark.asyncio
async def test_assert_user_exists_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops._assert_user_exists(_raising_client(), "someone")


@pytest.mark.asyncio
async def test_assert_group_exists_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops._assert_group_exists(_raising_client(), "some-group")


@pytest.mark.asyncio
async def test_create_project_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.create_project(_raising_client(), MagicMock())


@pytest.mark.asyncio
async def test_list_repos_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.list_repos(_raising_client(), "KEY")


@pytest.mark.asyncio
async def test_delete_repo_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.delete_repo(_raising_client(), "KEY", "repo-slug")


@pytest.mark.asyncio
async def test_delete_project_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.delete_project(_raising_client(), "KEY")


@pytest.mark.asyncio
async def test_assign_admin_group_permission_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.assign_admin_group_permission(_raising_client(), MagicMock())


@pytest.mark.asyncio
async def test_assign_admin_permission_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.assign_admin_permission(_raising_client(), MagicMock())


# --- mirror registration ---


def _mirror_project_payload(**overrides):
    data = {
        "key": "MYPROJ",
        "name": "my-project",
        "description": "A mirrored project",
        "admin_user": "nati",
        "mirrored_env_destination": "Nati",
    }
    data.update(overrides)
    return MirrorProjectSpec(**data)


def _paged_client(pages: list[dict]):
    client = MagicMock()
    responses = []
    for page in pages:
        resp = MagicMock(status_code=200)
        resp.json = MagicMock(return_value=page)
        responses.append(resp)
    client.get = AsyncMock(side_effect=responses)
    return client


@pytest.mark.asyncio
async def test_find_mirror_server_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops._find_mirror_server(_raising_client(), "Nati")


@pytest.mark.asyncio
async def test_find_mirror_server_matches_by_name_case_insensitive():
    client = _paged_client(
        [
            {
                "values": [
                    {
                        "id": "m1",
                        "baseUrl": "https://nati-mirror.example.com",
                        "name": "nati",
                    }
                ],
                "isLastPage": True,
            }
        ]
    )
    mirror = await ops._find_mirror_server(client, "Nati")
    assert mirror["baseUrl"] == "https://nati-mirror.example.com"


@pytest.mark.asyncio
async def test_find_mirror_server_paginates_across_pages():
    client = _paged_client(
        [
            {
                "values": [{"id": "m1", "name": "kat"}],
                "isLastPage": False,
                "nextPageStart": 1,
            },
            {
                "values": [
                    {"id": "m2", "baseUrl": "https://nati.example.com", "name": "nati"}
                ],
                "isLastPage": True,
            },
        ]
    )
    mirror = await ops._find_mirror_server(client, "Nati")
    assert mirror["id"] == "m2"


@pytest.mark.asyncio
async def test_find_mirror_server_not_found_raises_404():
    client = _paged_client([{"values": [], "isLastPage": True}])
    with pytest.raises(HTTPException) as exc:
        await ops._find_mirror_server(client, "Nati")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_find_upstream_id_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops._find_upstream_id(_raising_client())


@pytest.mark.asyncio
async def test_find_upstream_id_matches_by_base_url():
    client = _paged_client(
        [
            {
                "values": [
                    {"id": "u1", "baseUrl": ops.global_config.BITBUCKET_API_URL}
                ],
                "isLastPage": True,
            }
        ]
    )
    upstream_id = await ops._find_upstream_id(client)
    assert upstream_id == "u1"


@pytest.mark.asyncio
async def test_find_upstream_id_not_found_raises_502():
    client = _paged_client([{"values": [], "isLastPage": True}])
    with pytest.raises(HTTPException) as exc:
        await ops._find_upstream_id(client)
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_register_project_with_mirror_calls_settings_endpoint():
    main_client = _paged_client(
        [
            {
                "values": [
                    {
                        "id": "m1",
                        "baseUrl": "https://nati-mirror.example.com",
                        "name": "Nati",
                    }
                ],
                "isLastPage": True,
            }
        ]
    )
    mirror_client = MagicMock()
    mirror_client.get = AsyncMock(
        return_value=MagicMock(
            status_code=200,
            json=MagicMock(
                return_value={
                    "values": [
                        {"id": "u1", "baseUrl": ops.global_config.BITBUCKET_API_URL}
                    ],
                    "isLastPage": True,
                }
            ),
        )
    )
    mirror_client.post = AsyncMock(return_value=MagicMock(status_code=200, text=""))

    with patch.object(ops, "BaseAPI") as mock_base_api:
        mock_base_api.return_value.client = mirror_client
        await ops.register_project_with_mirror(
            main_client, _mirror_project_payload(), project_id=42
        )

    endpoint = mirror_client.post.call_args.args[0]
    assert endpoint.endswith("/settings/projects/42")


@pytest.mark.asyncio
async def test_create_mirror_project_creates_then_registers():
    create_response = MagicMock(status_code=200, text="")
    create_response.json = MagicMock(return_value={"id": 7, "key": "MYPROJ"})
    main_client = MagicMock()
    main_client.post = AsyncMock(return_value=create_response)
    main_client.get = AsyncMock(
        return_value=MagicMock(
            status_code=200,
            json=MagicMock(
                return_value={
                    "values": [
                        {
                            "id": "m1",
                            "baseUrl": "https://nati-mirror.example.com",
                            "name": "Nati",
                        }
                    ],
                    "isLastPage": True,
                }
            ),
        )
    )

    mirror_client = MagicMock()
    mirror_client.get = AsyncMock(
        return_value=MagicMock(
            status_code=200,
            json=MagicMock(
                return_value={
                    "values": [
                        {"id": "u1", "baseUrl": ops.global_config.BITBUCKET_API_URL}
                    ],
                    "isLastPage": True,
                }
            ),
        )
    )
    mirror_client.post = AsyncMock(return_value=MagicMock(status_code=200, text=""))

    with patch.object(ops, "BaseAPI") as mock_base_api:
        mock_base_api.return_value.client = mirror_client
        result = await ops.create_mirror_project(main_client, _mirror_project_payload())

    assert result["id"] == 7
    main_client.post.assert_called_once()
    assert main_client.post.call_args.kwargs["json"]["name"] == "my-project - Nati"
    mirror_client.post.assert_called_once()
    endpoint = mirror_client.post.call_args.args[0]
    assert endpoint.endswith("/settings/projects/7")
