from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from tashtiot_apis_library import Git

from app.global_conf import global_config
from app.v1.response_schemas import ExceptionResponse, SuccessResponse
from .conf import config
from .operations import create_consumer_config, delete_consumer_config
from .schemas import ConsumerConfigSpec, SizeEnum, IncludeResourceEnum


def get_v1_argocd_router(git: Git):
    router = APIRouter(prefix=config.API_PREFIX, tags=config.API_TAGS)

    @router.get("/sizes", name="get valid sizes")
    async def get_sizes() -> list[str]:
        return [s.value for s in SizeEnum]

    @router.get("/include-resources", name="get valid include resources")
    async def get_include_resources() -> list[str]:
        return [r.value for r in IncludeResourceEnum]

    @router.get("/environments", name="get valid environments")
    async def get_environments() -> list[str]:
        return global_config.ARGOCD_ALLOWED_ENVS

    @router.delete("/{env}/{name}", name="delete consumer argocd config", status_code=200)
    async def delete_consumer(env: str, name: str) -> JSONResponse:
        try:
            await delete_consumer_config(git, env, name)
            return SuccessResponse(status="successful")
        except HTTPException as external_error:
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in ArgoCD. {external_error.detail}",
                    status="Failed",
                    status_code=external_error.status_code,
                ).dict(),
                status_code=external_error.status_code,
            )

    @router.post("/", name="create consumer argocd config", status_code=200)
    async def create_consumer(payload: ConsumerConfigSpec) -> JSONResponse:
        try:
            await create_consumer_config(git, payload)
            return SuccessResponse(status="successful")
        except HTTPException as external_error:
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in ArgoCD. {external_error.detail}",
                    status="Failed",
                    status_code=external_error.status_code,
                ).dict(),
                status_code=external_error.status_code,
            )

    return router
