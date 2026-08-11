"""Error-path unit tests for bitbucket operations — exercise the `except Exception`
branches and _handle_response's non-JSON fallback."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.v1.bitbucket import operations as ops


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
