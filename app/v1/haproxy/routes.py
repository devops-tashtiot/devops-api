from typing import Any, Iterable, List, Sequence, Tuple, Dict
import asyncio

from .operations import create_haproxy_operation, delete_haproxy_operation, update_haproxy_operation, get_haproxy_operation, haproxy_get_status
from ...helpers import build_app_name
import yaml
from fastapi import APIRouter, HTTPException, Depends
from starlette.responses import JSONResponse
from loguru import logger
from tashtiot_apis_library.connectors import ArgoOperationResponse, ExternalServiceError
from .conf import config
from .schemas import HaProxyPayload, HaProxyMeta, HaProxyIdentifier

def get_router(git: Any, argocd: Any, vault: Any) -> APIRouter:
    """Create the APIRouter for HaProxy create operations."""
    router = APIRouter(prefix=config.API_PREFIX, tags = config.API_TAGS)


    @router.post("/", name="Create haproxy", status_code=201)
    async def create_haproxy(payload: HaProxyPayload) -> JSONResponse:
        try:
            app_name = await create_haproxy_operation(git=git, vault=vault, argocd=argocd, payload=payload.spec)

        except ExternalServiceError as external_error:
            app_name = build_app_name(payload.spec.metadata.cluster, payload.spec.metadata.namespace, payload.spec.metadata.name, "haproxy")
            return JSONResponse(ArgoOperationResponse(stdout=f"Exception in {external_error.service_name}. erros: {external_error.detail}", app_name=app_name, status="Failed", status_code=external_error.status_code).dict(), status_code=http_status.HTTP_502_BAD_GATEWAY)

        # Return a temporary response to client that indicate the creation is in process
        return ArgoOperationResponse(app_name=app_name, status="InProgress")


    @router.delete("/", name="Delete HaProxy", status_code=204)
    async def delete_haproxy(params: HaProxyIdentifier = Depends()) -> JSONResponse:
        try:
            app_name = await delete_haproxy_operation(git=git, vault=vault, argocd=argocd, params=params)
        except ExternalServiceError as external_error:
            app_name = build_app_name(params.cluster, params.namespace, params.name, "haproxy")
            return JSONResponse(ArgoOperationResponse(stdout=f"Exception in {external_error.service_name}. erros: {external_error.detail}", app_name=app_name, status="Failed", status_code=external_error.status_code).dict(), status_code=http_status.HTTP_502_BAD_GATEWAY)

        return ArgoOperationResponse(app_name=app_name, status="InProgress")


    @router.put("/", name="Update haproxy", status_code=201)
    async def update_haproxy(payload: HaProxyPayload) -> JSONResponse:
        try:
            app_name = await update_haproxy_operation(git=git, vault=vault, argocd=argocd, payload=payload.spec)
        except ExternalServiceError as external_error:
            app_name = build_app_name(payload.spec.metadata.cluster, payload.spec.metadata.namespace, payload.spec.metadata.name, "haproxy")
            return JSONResponse(ArgoOperationResponse(stdout=f"Exception in {external_error.service_name}. erros: {external_error.detail}", app_name=app_name, status="Failed", status_code=external_error.status_code).dict(), status_code=http_status.HTTP_502_BAD_GATEWAY)

        return ArgoOperationResponse(app_name=app_name, status="InProgress")


    @router.get("/", name="Read haproxy configuration", status_code=200)
    async def get_haproxy(params: HaProxyIdentifier = Depends()) -> dict:
        try:
            return await get_haproxy_operation(git=git, params=params)
        except ExternalServiceError as external_error:
            app_name = build_app_name(params.cluster, params.namespace, params.name, "haproxy")
            return JSONResponse(ArgoOperationResponse(stdout=f"Exception in {external_error.service_name}. erros: {external_error.detail}", app_name=app_name, status="Failed", status_code=external_error.status_code).dict(), status_code=http_status.HTTP_502_BAD_GATEWAY)
        raise

    @router.get("/status", name="Get haproxy app status")
    async def status(params: HaProxyIdentifier = Depends()) -> ArgoOperationResponse:
        try:
            return await haproxy_get_status(git=git, argocd=argocd, params=params)
        except ExternalServiceError as external_error:
            app_name = build_app_name(params.cluster, params.namespace, params.name, "haproxy")
            return JSONResponse(ArgoOperationResponse(stdout=f"Exception in {external_error.service_name}. erros: {external_error.detail}", app_name=app_name, status="Failed", status_code=external_error.status_code).dict(), status_code=http_status.HTTP_502_BAD_GATEWAY)
        raise

    return router