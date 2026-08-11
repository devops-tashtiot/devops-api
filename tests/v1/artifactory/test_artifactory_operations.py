"""Error-path unit tests for artifactory operations — exercise the `except Exception`
branches and _handle_response's non-JSON fallback."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.v1.artifactory import operations as ops


def _raising_client():
    client = MagicMock()
    boom = AsyncMock(side_effect=RuntimeError("boom"))
    client.get = boom
    client.post = boom
    client.put = boom
    client.delete = boom
    return client


def test_handle_response_non_json_falls_back_to_text():
    resp = MagicMock(status_code=400, text="bad request text")
    resp.json = MagicMock(side_effect=ValueError("not json"))
    with pytest.raises(HTTPException) as exc:
        ops._handle_response(resp)
    assert exc.value.status_code == 400
    assert exc.value.detail == "bad request text"


@pytest.mark.asyncio
async def test_get_storage_quota_bytes_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.get_storage_quota_bytes(_raising_client(), "PROJ")


@pytest.mark.asyncio
async def test_create_project_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.create_project(_raising_client(), MagicMock())


@pytest.mark.asyncio
async def test_delete_project_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.delete_project(_raising_client(), "PROJ")


@pytest.mark.asyncio
async def test_assign_admin_user_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.assign_admin_user(_raising_client(), MagicMock())


@pytest.mark.asyncio
async def test_assign_admin_group_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.assign_admin_group(_raising_client(), MagicMock())


@pytest.mark.asyncio
async def test_increase_storage_quota_reraises_on_client_error():
    payload = MagicMock()
    payload.name = "PROJ"
    payload.storage_quota_giga_bytes = 5
    with pytest.raises(RuntimeError):
        await ops.increase_storage_quota(_raising_client(), payload)


@pytest.mark.asyncio
async def test_group_exists_in_jpd_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.group_exists_in_jpd(_raising_client(), "grp")


@pytest.mark.asyncio
async def test_sync_ldap_group_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.sync_ldap_group(_raising_client(), "grp")


@pytest.mark.asyncio
async def test_assign_project_member_reraises_on_client_error():
    # member_type is a MagicMock (!= MemberType.GROUP) so it takes the user branch,
    # then the mocked PUT raises.
    with pytest.raises(RuntimeError):
        await ops.assign_project_member(_raising_client(), MagicMock())


@pytest.mark.asyncio
async def test_get_global_role_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.get_global_role(_raising_client(), "role")


@pytest.mark.asyncio
async def test_get_project_permissions_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.get_project_permissions(_raising_client(), "PROJ")


@pytest.mark.asyncio
async def test_upload_xray_vuln_update_wraps_client_error_as_502():
    with pytest.raises(HTTPException) as exc:
        await ops.upload_xray_vulnerability_update(
            _raising_client(), b"data", "update.zip"
        )
    assert exc.value.status_code == 502
