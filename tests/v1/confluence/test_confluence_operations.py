"""Error-path unit tests for confluence operations — exercise the `except Exception`
branches (some re-raise, some wrap as HTTPException 502) and _handle_response's
non-JSON fallback."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.v1.confluence import operations as ops


def _raising_client():
    client = MagicMock()
    boom = AsyncMock(side_effect=RuntimeError("boom"))
    client.get = boom
    client.post = boom
    client.put = boom
    client.delete = boom
    return client


def test_handle_response_non_json_falls_back_to_text():
    resp = MagicMock(status_code=500, text="server text")
    resp.json = MagicMock(side_effect=ValueError("not json"))
    with pytest.raises(HTTPException) as exc:
        ops._handle_response(resp)
    assert exc.value.status_code == 500
    assert exc.value.detail == "server text"


# --- re-raise (bare) branches ---


@pytest.mark.asyncio
async def test_create_space_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.create_space(_raising_client(), MagicMock())


@pytest.mark.asyncio
async def test_delete_space_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.delete_space(_raising_client(), "KEY")


@pytest.mark.asyncio
async def test_assign_space_admin_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.assign_space_admin(_raising_client(), MagicMock())


@pytest.mark.asyncio
async def test_assign_space_group_admin_reraises_on_client_error():
    with pytest.raises(RuntimeError):
        await ops.assign_space_group_admin(_raising_client(), MagicMock())


# --- wrap-as-502 branches ---


@pytest.mark.asyncio
async def test_get_upm_token_wraps_as_502():
    with pytest.raises(HTTPException) as exc:
        await ops.get_upm_token(_raising_client())
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_install_plugin_wraps_as_502():
    with pytest.raises(HTTPException) as exc:
        await ops.install_plugin(_raising_client(), b"jar", "plugin.jar", "upm-token")
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_uninstall_plugin_wraps_as_502():
    with pytest.raises(HTTPException) as exc:
        await ops.uninstall_plugin(_raising_client(), "plugin-key")
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_trigger_space_export_wraps_as_502():
    with pytest.raises(HTTPException) as exc:
        await ops.trigger_space_export(_raising_client(), MagicMock())
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_poll_export_job_wraps_as_502():
    with pytest.raises(HTTPException) as exc:
        await ops.poll_export_job(_raising_client(), 123)
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_download_export_wraps_as_502():
    with pytest.raises(HTTPException) as exc:
        await ops.download_export(_raising_client(), 123)
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_upload_archive_and_start_restore_wraps_as_502():
    with pytest.raises(HTTPException) as exc:
        await ops.upload_archive_and_start_restore(
            _raising_client(), b"zip", "export.zip"
        )
    assert exc.value.status_code == 502


@pytest.mark.asyncio
async def test_poll_restore_job_wraps_as_502():
    with pytest.raises(HTTPException) as exc:
        await ops.poll_restore_job(_raising_client(), 123)
    assert exc.value.status_code == 502
