from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.v1.response_schemas import ExceptionResponse, SuccessResponse
from .schemas import ProjectSpec, JiraProjectRequest
from typing import Any
from loguru import logger
from .conf import config
from .operations import (
    create_project,
    delete_project,
    assign_project_admin_user,
    assign_project_admin_group,
    list_user_directories,
    sync_user_directory,
    assert_user_exists,
    assert_group_exists,
)


def get_v1_jira_router(jira_client: Any):
    router = APIRouter(prefix=config.API_PREFIX, tags=config.API_TAGS)

    @router.post("/", name="create project", status_code=200)
    async def create_new_project(payload: JiraProjectRequest) -> JSONResponse:
        try:
            await assert_user_exists(jira_client, payload.spec.admin_user)
            if payload.spec.admin_group:
                await assert_group_exists(jira_client, payload.spec.admin_group)
            await create_project(jira_client, payload.spec)
            await assign_project_admin_user(jira_client, payload.spec)
            if payload.spec.admin_group:
                await assign_project_admin_group(jira_client, payload.spec)
            return SuccessResponse(status="successful")
        except HTTPException as external_error:
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in Jira. {external_error.detail}",
                    status="Failed",
                    status_code=external_error.status_code,
                ).dict(),
                status_code=external_error.status_code,
            )
        except Exception as e:
            try:
                await delete_project(jira_client, payload.spec)
            except Exception as rollback_error:
                logger.error(f"Rollback failed for project {payload.spec.key}: {rollback_error}")
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in Jira. {str(e)}",
                    status="Failed",
                    status_code=500,
                ).dict(),
                status_code=500,
            )

    @router.delete("/{project_key}", name="delete project", status_code=200)
    async def delete_existing_project(project_key: str) -> JSONResponse:
        try:
            await delete_project(jira_client, ProjectSpec.model_construct(key=project_key))
            return SuccessResponse(status="successful")
        except HTTPException as external_error:
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in Jira. {external_error.detail}",
                    status="Failed",
                    status_code=external_error.status_code,
                ).dict(),
                status_code=external_error.status_code,
            )

    @router.get("/user-dirs", name="list user directories", status_code=200)
    async def get_user_directories() -> JSONResponse:
        try:
            dirs = await list_user_directories(jira_client)
            return JSONResponse(content=dirs)
        except HTTPException as external_error:
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in Jira. {external_error.detail}",
                    status="Failed",
                    status_code=external_error.status_code,
                ).dict(),
                status_code=external_error.status_code,
            )

    @router.post("/user-dirs/sync", name="sync user directory", status_code=200)
    async def sync_directory() -> JSONResponse:
        try:
            await sync_user_directory(jira_client)
            return SuccessResponse(status="successful")
        except HTTPException as external_error:
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in Jira. {external_error.detail}",
                    status="Failed",
                    status_code=external_error.status_code,
                ).dict(),
                status_code=external_error.status_code,
            )

    return router
