"""Error-path unit tests for sonarqube operations — exercise the `except Exception`
branches and _handle_response's non-JSON fallback."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.v1.sonarqube import operations as ops
from app.v1.sonarqube.schemas import SonarQubeSizeEnum


def _raising_client():
    client = MagicMock()
    client.post = AsyncMock(side_effect=RuntimeError("boom"))
    return client


def _raising_git():
    git = MagicMock()
    boom = AsyncMock(side_effect=RuntimeError("boom"))
    git.add_file = boom
    git.modify_file = boom
    git.delete_file = boom
    return git


def _consumer_payload():
    payload = MagicMock()
    payload.name = "consumer-a"
    payload.plugins_list = ["plugin-x"]
    payload.size = SonarQubeSizeEnum.default
    return payload


def test_handle_response_non_json_falls_back_to_text():
    resp = MagicMock(status_code=500, text="boom text")
    resp.json = MagicMock(side_effect=ValueError("not json"))
    with pytest.raises(HTTPException) as exc:
        ops._handle_response(resp)
    assert exc.value.status_code == 500
    assert exc.value.detail == "boom text"


@pytest.mark.asyncio
async def test_create_group_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.create_group(_raising_client(), MagicMock())


@pytest.mark.asyncio
async def test_delete_group_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.delete_group(_raising_client(), MagicMock())


@pytest.mark.asyncio
async def test_assign_global_permissions_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.assign_global_permissions(_raising_client(), MagicMock())


@pytest.mark.asyncio
async def test_assign_template_permissions_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.assign_template_permissions(_raising_client(), MagicMock())


@pytest.mark.asyncio
async def test_create_consumer_reraises_on_git_error():
    with pytest.raises(RuntimeError):
        await ops.create_sonarqube_consumer(_raising_git(), _consumer_payload())


@pytest.mark.asyncio
async def test_update_consumer_reraises_on_git_error():
    with pytest.raises(RuntimeError):
        await ops.update_sonarqube_consumer(
            _raising_git(), "consumer-a", _consumer_payload()
        )


@pytest.mark.asyncio
async def test_delete_consumer_reraises_on_git_error():
    with pytest.raises(RuntimeError):
        await ops.delete_sonarqube_consumer(_raising_git(), "consumer-a")
