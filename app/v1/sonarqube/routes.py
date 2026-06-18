from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from tashtiot_apis_library.fastapi_template.utils import BaseAPI

from app.global_conf import global_config
from app.v1.response_schemas import ExceptionResponse, SuccessResponse
from .conf import config
from .operations import assign_global_permissions, assign_template_permissions, create_group, delete_group
from .schemas import GroupSpec


def _build_client(consumer_name: str) -> BaseAPI:
    port = f":{config.SONARQUBE_PORT}" if config.SONARQUBE_PORT else ""
    url = f"{config.SONARQUBE_SCHEME}://{consumer_name}.sonarqube.{global_config.DOMAIN_SUFFIX}{port}"
    return BaseAPI(url, auth=(global_config.SONARQUBE_USERNAME, global_config.SONARQUBE_PASSWORD)).client


def get_v1_sonarqube_router():
    router = APIRouter(prefix=config.API_PREFIX, tags=config.API_TAGS)

    @router.post("/", name="create sonarqube group", status_code=200)
    async def create_new_group(payload: GroupSpec) -> JSONResponse:
        client = _build_client(payload.consumer_name)
        try:
            await create_group(client, payload)
            await assign_global_permissions(client, payload)
            await assign_template_permissions(client, payload)
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
            await delete_group(client, payload)

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
