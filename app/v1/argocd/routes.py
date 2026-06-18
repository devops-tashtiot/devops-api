from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from tashtiot_apis_library import Git

from app.global_conf import global_config
from app.v1.response_schemas import ExceptionResponse, SuccessResponse
from .conf import config
from .operations import create_consumer_config, delete_consumer_config, create_cluster_secret, delete_cluster_secret, edit_cluster_secret
from .schemas import ConsumerConfigSpec, ClusterSecretSpec, ClusterSecretUpdateSpec, ClusterSecretIdentifier, SizeEnum, IncludeResourceEnum


def get_v1_argocd_router(git: Git, argocd_timeout: int):
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

    @router.post("/cluster-secret", name="create cluster secret argocd application", status_code=200)
    async def create_cluster_secret_app(payload: ClusterSecretSpec) -> JSONResponse:
        try:
            await create_cluster_secret(argocd_timeout, payload)
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

    @router.delete("/cluster-secret", name="delete cluster secret argocd application", status_code=200)
    async def delete_cluster_secret_app(params: ClusterSecretIdentifier = Depends()) -> JSONResponse:
        try:
            await delete_cluster_secret(argocd_timeout, params)
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

    @router.put("/cluster-secret/{app_name}/{chosen_name}", name="edit cluster secret argocd application", status_code=200)
    async def edit_cluster_secret_app(app_name: str, chosen_name: str, payload: ClusterSecretUpdateSpec) -> JSONResponse:
        try:
            await edit_cluster_secret(argocd_timeout, app_name, chosen_name, payload)
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
