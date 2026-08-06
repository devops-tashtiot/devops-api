from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.v1.response_schemas import SuccessResponse, handle_route
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
        async def _op():
            created = False
            try:
                await assert_user_exists(jira_client, payload.spec.admin_user)
                if payload.spec.admin_group:
                    await assert_group_exists(jira_client, payload.spec.admin_group)
                await create_project(jira_client, payload.spec)
                created = True
                await assign_project_admin_user(jira_client, payload.spec)
                if payload.spec.admin_group:
                    await assign_project_admin_group(jira_client, payload.spec)
                return SuccessResponse(status="successful")
            except Exception:
                if created:
                    try:
                        await delete_project(jira_client, payload.spec)
                    except Exception as rb_err:
                        logger.error(f"Rollback failed for project {payload.spec.key}: {rb_err}")
                raise
        return await handle_route("Jira", _op())

    @router.delete("/{project_key}", name="delete project", status_code=200)
    async def delete_existing_project(project_key: str) -> JSONResponse:
        async def _op():
            await delete_project(jira_client, ProjectSpec.model_construct(key=project_key))
            return SuccessResponse(status="successful")
        return await handle_route("Jira", _op())

    @router.get("/user-dirs", name="list user directories", status_code=200)
    async def get_user_directories() -> JSONResponse:
        async def _op():
            dirs = await list_user_directories(jira_client)
            return JSONResponse(content=dirs)
        return await handle_route("Jira", _op())

    @router.post("/user-dirs/sync", name="sync user directory", status_code=200)
    async def sync_directory() -> JSONResponse:
        async def _op():
            await sync_user_directory(jira_client)
            return SuccessResponse(status="successful")
        return await handle_route("Jira", _op())

    return router
