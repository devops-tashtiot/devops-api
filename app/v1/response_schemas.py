"""Base operation response schemas and centralized route error handler.

This module defines:
  - ``SuccessResponse`` — returned by all successful mutation endpoints.
  - ``ExceptionResponse`` — returned by all failing endpoints.
  - ``handle_route()`` — a single async helper that every route delegates to,
    converting any exception into the correct structured JSON error response.

Response Taxonomy
-----------------
Every route in this API returns one of the following HTTP status codes:

  200  OK              – Operation succeeded (most endpoints).
  201  Created         – Resource created with a side-effect body
                         (e.g. Artifactory storage-quota).
  401  Unauthorized    – Invalid credentials or unreachable cluster
                         (ArgoCD token validation).
  403  Forbidden       – Token valid but lacks the required permission
                         (ArgoCD namespace admin check).
  404  Not Found       – User, group, project, space, or S3 object does
                         not exist (Bitbucket/Jira user-group pre-checks,
                         S3 fetch, external API proxied 404).
  409  Conflict        – Resource already exists (Bitbucket/Jira/Confluence
                         create operations proxied from the external API).
  410  Gone            – Resource existed but no longer does (Jira group
                         exact-lookup returns 410 instead of 404).
  422  Unprocessable   – Async job completed with a known error payload
                         (Confluence plugin install, space export/import).
  501  Not Implemented – Operation has no supported API on the target
                         service (directory sync on Bitbucket/Jira/Confluence).
  502  Bad Gateway     – Upstream service (S3, Confluence UPM, Xray)
                         returned an unexpected error.
  504  Gateway Timeout – Async job on the external service did not finish
                         within the configured poll window.
  500  Internal Error  – Unexpected exception not covered by the above.

All error responses use ``ExceptionResponse``.
All success responses use ``SuccessResponse`` (or a plain ``JSONResponse``
with extra fields for data-returning endpoints such as space-export or
list-user-dirs).
"""

from __future__ import annotations

from typing import Any, Awaitable, Optional

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from tashtiot_apis_library import OperationRequest

__all__ = [
    "AnyMetadataRequest",
    "ExceptionResponse",
    "SuccessResponse",
    "handle_route",
]


class AnyMetadataRequest(OperationRequest):
    """Drop-in replacement for ``OperationRequest`` that accepts ``metadata`` as an
    optional, unvalidated free-form dict.

    The library's ``OperationRequest`` enforces a strict ``MetadataRequest`` schema
    (``project``, ``network``, ``region``, ``space``, ``environment`` all required).
    In practice our routes never read or act on ``metadata`` — it is purely informational
    context carried by the caller. Requiring callers to always supply every metadata field
    adds friction and breaks when new optional fields are added to the schema.

    This class overrides ``metadata`` with ``Any`` and ``exclude=True`` so the field is
    accepted silently for any shape (or omitted entirely) without any validation, and
    is completely ignored by the API.
    """

    metadata: Any = Field(
        default=None,
        exclude=True,
        description="Free-form request metadata — accepted but not validated or used by the API.",
    )


class ExceptionResponse(BaseModel):
    """Error response shape returned by all failing endpoints.

    Attributes:
        status: Always ``"Failed"`` for error responses.
        status_code: Mirrors the HTTP response status code.
        stdout: Human-readable error detail, prefixed with the originating
            service name (e.g. ``"Exception in Bitbucket. User 'x' does not exist"``).
    """

    status: str = Field(
        ...,
        description='Operation status — always "Failed" for error responses.',
    )
    status_code: Optional[int] = Field(
        default=None,
        description="HTTP status code (mirrors the HTTP response code).",
    )
    stdout: str = Field(
        default="",
        description="Human-readable error detail from the operation.",
    )


class SuccessResponse(BaseModel):
    """Success response shape returned by all successful mutation endpoints.

    Attributes:
        status: Always ``"successful"``.
    """

    status: str = Field(
        default="successful",
        description='Operation status — always "successful" for success responses.',
    )


async def handle_route(service_name: str, coro: Awaitable) -> JSONResponse:
    """Centralized exception handler for all route endpoints.

    Every route delegates its entire business logic to this function so that
    exception handling, status code propagation, and error payload formatting
    are defined in exactly one place.

    The operations layer is responsible for raising ``HTTPException`` with the
    correct status code for each known failure scenario (see the response
    taxonomy in this module's docstring). ``handle_route`` propagates those
    codes verbatim, and maps any unexpected exception to HTTP 500.

    Args:
        service_name: Human-readable service label prepended to the error
            ``stdout`` field (e.g. ``"Bitbucket"``, ``"Confluence"``).
        coro: An awaitable (coroutine) that performs the route's business
            logic and returns a FastAPI response object on success, or raises
            an exception on failure. Rollback logic (if any) should be
            handled inside ``coro`` before re-raising.

    Returns:
        The response produced by ``coro`` on success, or a ``JSONResponse``
        wrapping an ``ExceptionResponse`` on failure.
    """
    try:
        return await coro
    except HTTPException as e:
        return JSONResponse(
            ExceptionResponse(
                stdout=f"Exception in {service_name}. {e.detail}",
                status="Failed",
                status_code=e.status_code,
            ).model_dump(),
            status_code=e.status_code,
        )
    except Exception as e:
        return JSONResponse(
            ExceptionResponse(
                stdout=f"Exception in {service_name}. {str(e)}",
                status="Failed",
                status_code=500,
            ).model_dump(),
            status_code=500,
        )
