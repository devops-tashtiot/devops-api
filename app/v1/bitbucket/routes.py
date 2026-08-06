from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.v1.response_schemas import SuccessResponse, handle_route
from .schemas import BitbucketProjectRequest
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
        async def _op():
            created = False
            try:
                await validate_admin_principals(bitbucket_client, payload.spec)
                await create_project(bitbucket_client, payload.spec)
                created = True
                if payload.spec.admin_user:
                    await assign_admin_permission(bitbucket_client, payload.spec)
                if payload.spec.admin_group:
                    await assign_admin_group_permission(bitbucket_client, payload.spec)
                return SuccessResponse(status="successful")
            except Exception:
                if created:
                    try:
                        await delete_project(bitbucket_client, payload.spec.key)
                    except Exception as rb_err:
                        logger.error(f"Rollback failed for project {payload.spec.key}: {rb_err}")
                raise
        return await handle_route("Bitbucket", _op())

    @router.delete("/{key}", name="delete project", status_code=200)
    async def delete_existing_project(key: str) -> JSONResponse:
        async def _op():
            await delete_project(bitbucket_client, key)
            return SuccessResponse(status="successful")
        return await handle_route("Bitbucket", _op())

    @router.get("/user-dirs", name="list user directories", status_code=200)
    async def get_user_directories() -> JSONResponse:
        async def _op():
            dirs = await list_user_directories(bitbucket_client)
            return JSONResponse(content=dirs)
        return await handle_route("Bitbucket", _op())

    @router.post("/user-dirs/sync", name="sync user directory", status_code=200)
    async def sync_directory() -> JSONResponse:
        async def _op():
            await sync_user_directory(bitbucket_client)
            return SuccessResponse(status="successful")
        return await handle_route("Bitbucket", _op())

    return router