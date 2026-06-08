from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.v1.response_schemas import ExceptionResponse, SuccessResponse
from .conf import config
from .operations import assign_global_permissions, assign_template_permissions, create_group, delete_group
from .schemas import GroupSpec


def get_v1_sonarqube_router(sonarqube_client: Any):
    router = APIRouter(prefix=config.API_PREFIX, tags=config.API_TAGS)

    @router.post("/", name="create sonarqube group", status_code=200)
    async def create_new_group(payload: GroupSpec) -> JSONResponse:
        try:
            await create_group(sonarqube_client, payload)
            await assign_global_permissions(sonarqube_client, payload)
            await assign_template_permissions(sonarqube_client, payload)
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
            await delete_group(sonarqube_client, payload)

    @router.delete("/{name}", name="delete sonarqube group", status_code=200)
    async def delete_existing_group(name: str) -> JSONResponse:
        try:
            await delete_group(sonarqube_client, GroupSpec(name=name))
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
