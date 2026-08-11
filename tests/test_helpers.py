"""Unit tests for app.helpers S3 fetch/upload — the 404 and upload-failure branches
the service route tests don't reach."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app import helpers


def _patch_client(*, get_response=None, put_side_effect=None, put_response=None):
    inner = AsyncMock()
    if get_response is not None:
        inner.get = AsyncMock(return_value=get_response)
    if put_side_effect is not None:
        inner.put = AsyncMock(side_effect=put_side_effect)
    elif put_response is not None:
        inner.put = AsyncMock(return_value=put_response)
    cm = MagicMock()
    cm.return_value.__aenter__ = AsyncMock(return_value=inner)
    cm.return_value.__aexit__ = AsyncMock(return_value=False)
    return patch("app.helpers.httpx.AsyncClient", cm)


@pytest.mark.asyncio
async def test_fetch_from_s3_404_raises_404():
    resp = MagicMock(status_code=404)
    with _patch_client(get_response=resp):
        with pytest.raises(HTTPException) as exc:
            await helpers.fetch_from_s3("http://s3/missing", label="thing")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_upload_to_s3_client_error_wraps_as_502():
    with _patch_client(put_side_effect=RuntimeError("boom")):
        with pytest.raises(HTTPException) as exc:
            await helpers.upload_to_s3(
                "http://s3/target", b"data", "application/zip", label="thing"
            )
    assert exc.value.status_code == 502
