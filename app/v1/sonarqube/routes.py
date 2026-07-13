from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from tashtiot_apis_library import Git
from tashtiot_apis_library.fastapi_template.utils import BaseAPI

from app.global_conf import global_config
from app.v1.response_schemas import ExceptionResponse, SuccessResponse
from .conf import config
from .operations import (
    assign_global_permissions, assign_template_permissions,
    create_group, delete_group,
    create_sonarqube_consumer, update_sonarqube_consumer, delete_sonarqube_consumer,
)
from .schemas import GroupSpec, SonarQubeConsumerSpec, SonarQubeConsumerUpdateSpec, SonarQubeSizeEnum, SonarQubeGroupRequest, SonarQubeConsumerRequest, SonarQubeConsumerUpdateRequest


def _build_client(consumer_name: str) -> BaseAPI:
    url = f"https://{consumer_name}.sonarqube.{global_config.DOMAIN_SUFFIX}"
    return BaseAPI(url, auth=(global_config.SONARQUBE_USERNAME, global_config.SONARQUBE_PASSWORD)).client


def get_v1_sonarqube_router(git: Git):
    router = APIRouter(prefix=config.API_PREFIX, tags=config.API_TAGS)

    @router.get("/sizes", name="get valid sizes")
    async def get_sizes() -> list[str]:
        return [s.value for s in SonarQubeSizeEnum]

    @router.post("/", name="create sonarqube group", status_code=200)
    async def create_new_group(payload: SonarQubeGroupRequest) -> JSONResponse:
        client = _build_client(payload.spec.consumer_name)
        try:
            await create_group(client, payload.spec)
            await assign_global_permissions(client, payload.spec)
            await assign_template_permissions(client, payload.spec)
            return SuccessResponse(status="successful")
        except HTTPException as external_error:
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in SonarQube. {external_error.detail}",
                    status="Failed",
                    status_code=external_error.status_code,
                ).dict(),
                status_code=external_error.status_code,
            )
        except:
            await delete_group(client, payload.spec)

    @router.post("/consumer/", name="create sonarqube consumer config", status_code=200)
    async def create_consumer(payload: SonarQubeConsumerRequest) -> JSONResponse:
        try:
            await create_sonarqube_consumer(git, payload.spec)
            return SuccessResponse(status="successful")
        except HTTPException as external_error:
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in SonarQube. {external_error.detail}",
                    status="Failed",
                    status_code=external_error.status_code,
                ).dict(),
                status_code=external_error.status_code,
            )

    @router.put("/consumer/{name}", name="update sonarqube consumer config", status_code=200)
    async def edit_consumer(name: str, payload: SonarQubeConsumerUpdateRequest) -> JSONResponse:
        try:
            await update_sonarqube_consumer(git, name, payload.spec)
            return SuccessResponse(status="successful")
        except HTTPException as external_error:
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in SonarQube. {external_error.detail}",
                    status="Failed",
                    status_code=external_error.status_code,
                ).dict(),
                status_code=external_error.status_code,
            )

    @router.delete("/consumer/{name}", name="delete sonarqube consumer config", status_code=200)
    async def delete_consumer(name: str) -> JSONResponse:
        try:
            await delete_sonarqube_consumer(git, name)
            return SuccessResponse(status="successful")
        except HTTPException as external_error:
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in SonarQube. {external_error.detail}",
                    status="Failed",
                    status_code=external_error.status_code,
                ).dict(),
                status_code=external_error.status_code,
            )

    # Registered last: this generic two-segment wildcard would otherwise shadow
    # DELETE /consumer/{name} above, since Starlette matches routes in registration order
    # and both patterns fit the same "/consumer/<x>" shape (confirmed live — see CLAUDE.md).
    @router.delete("/{consumer_name}/{name}", name="delete sonarqube group", status_code=200)
    async def delete_existing_group(consumer_name: str, name: str) -> JSONResponse:
        stub = GroupSpec(consumer_name=consumer_name, name=name)
        client = _build_client(consumer_name)
        try:
            await delete_group(client, stub)
            return SuccessResponse(status="successful")
        except HTTPException as external_error:
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in SonarQube. {external_error.detail}",
                    status="Failed",
                    status_code=external_error.status_code,
                ).dict(),
                status_code=external_error.status_code,
            )

    return router
