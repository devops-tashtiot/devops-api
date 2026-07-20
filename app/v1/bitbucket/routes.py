from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.v1.response_schemas import ExceptionResponse, SuccessResponse
from .schemas import ProjectSpec, BitbucketProjectRequest
from typing import Any
from loguru import logger
from .conf import config
from .operations import (
    create_project,
    delete_project,
    assign_admin_permission,
    assign_admin_group_permission,
    list_user_directories,
    sync_user_directory,
    validate_admin_principals,
)

def get_v1_bitbucket_router(bitbucket_client: Any):
    router = APIRouter(prefix=config.API_PREFIX, tags=config.API_TAGS)

    @router.post("/", name="create project", status_code=200)
    async def create_new_project(payload: BitbucketProjectRequest) -> JSONResponse:
        try:
            await validate_admin_principals(bitbucket_client, payload.spec)
            await create_project(bitbucket_client, payload.spec)
            if payload.spec.admin_user:
                await assign_admin_permission(bitbucket_client, payload.spec)
            if payload.spec.admin_group:
                await assign_admin_group_permission(bitbucket_client, payload.spec)
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
        except Exception as e:
            try:
                await delete_project(bitbucket_client, payload.spec.key)
            except Exception as rollback_error:
                logger.error(f"Rollback failed for project {payload.spec.key}: {rollback_error}")
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in Bitbucket. {str(e)}",
                    status="Failed",
                    status_code=500,
                ).dict(),
                status_code=500,
            )

    @router.delete("/{key}", name="delete project", status_code=200)
    async def delete_existing_project(key: str) -> JSONResponse:
        try:
            await delete_project(bitbucket_client, key)
            return SuccessResponse(status="successful")
        except HTTPException as external_error:
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in Bitbucket. {external_error.detail}",
                    status="Failed",
                    status_code=external_error.status_code,
                ).dict(),
                status_code=external_error.status_code,
            )

    @router.get("/user-dirs", name="list user directories", status_code=200)
    async def get_user_directories() -> JSONResponse:
        try:
            dirs = await list_user_directories(bitbucket_client)
            return JSONResponse(content=dirs)
        except HTTPException as external_error:
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in Bitbucket. {external_error.detail}",
                    status="Failed",
                    status_code=external_error.status_code,
                ).dict(),
                status_code=external_error.status_code,
            )

    @router.post("/user-dirs/sync", name="sync user directory", status_code=200)
    async def sync_directory() -> JSONResponse:
        try:
            await sync_user_directory(bitbucket_client)
            return SuccessResponse(status="successful")
        except HTTPException as external_error:
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in Bitbucket. {external_error.detail}",
                    status="Failed",
                    status_code=external_error.status_code,
                ).dict(),
                status_code=external_error.status_code,
            )

    return router