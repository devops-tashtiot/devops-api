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
    assign_admin_group_permission,
    list_user_directories,
    sync_user_directory,
)

def get_v1_bitbucket_router(bitbucket_client: Any):
    router = APIRouter(prefix=config.API_PREFIX, tags=config.API_TAGS)

    @router.post("/", name="create project", status_code=200)
    async def create_new_project(payload: ProjectSpec) -> JSONResponse:
        try:
            await create_project(bitbucket_client, payload)
            if payload.admin_user:
                await assign_admin_permission(bitbucket_client, payload)
            if payload.admin_group:
                await assign_admin_group_permission(bitbucket_client, payload)
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
            await delete_project(bitbucket_client, payload.key)

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

    @router.post("/user-dirs/{directory_id}/sync", name="sync user directory", status_code=200)
    async def sync_directory(directory_id: int) -> JSONResponse:
        try:
            await sync_user_directory(bitbucket_client, directory_id)
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