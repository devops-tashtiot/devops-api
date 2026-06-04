from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.v1.response_schemas import ExceptionResponse, SuccessResponse
from .schemas import ProjectSpec
from typing import Any
from .conf import config
from .operations import (
    create_project,
    delete_project,
    assign_admin_permission,
)

def get_v1_bitbucket_router(bitbucket_client: Any):
    router = APIRouter(prefix=config.API_PREFIX, tags=config.API_TAGS)
    
    @router.post("/", name="create project", status_code=200)
    async def create_new_project(payload: ProjectSpec) -> JSONResponse:
        try:
            await create_project(bitbucket_client, payload)
            await assign_admin_permission(bitbucket_client, payload)
            return SuccessResponse(status="successful")
        except HTTPException as external_error:
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in Bitbucket. {external_error.detail}",
                    status="Failed",
                    status_code=external_error.status_code
                ).dict(),
                status_code=external_error.status_code
            )
        except:
            await delete_project(bitbucket_client, payload)
    return router