import base64

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.v1.response_schemas import SuccessResponse, handle_route
from .schemas import (
    ConfluenceSpaceRequest,
    ConfluencePluginInstallRequest,
    ConfluencePluginUploadRequest,
    ConfluenceSpaceExportRequest,
    ConfluenceSpaceImportRequest,
)
from typing import Any
from loguru import logger
from .conf import config
from .operations import (
    create_space,
    delete_space,
    assign_space_admin,
    assign_space_group_admin,
    fetch_plugin_from_public_s3,
    get_upm_token,
    install_plugin,
    uninstall_plugin,
    # list_user_directories,
    # sync_user_directory,
    fetch_archive_from_s3,
    upload_archive_and_start_restore,
    poll_restore_job,
    trigger_space_export,
    poll_export_job,
    download_export,
    upload_archive_to_s3,
    upload_plugin_to_s3,
)


def get_v1_confluence_router(confluence_client: Any):
    router = APIRouter(prefix=config.API_PREFIX, tags=config.API_TAGS)

    @router.post("/", name="create space", status_code=200)
    async def create_new_space(payload: ConfluenceSpaceRequest) -> JSONResponse:
        async def _op():
            created = False
            try:
                await create_space(confluence_client, payload.spec)
                created = True
                if payload.spec.admin_user:
                    await assign_space_admin(confluence_client, payload.spec)
                if payload.spec.admin_group:
                    await assign_space_group_admin(confluence_client, payload.spec)
                return SuccessResponse(status="successful")
            except Exception:
                if created:
                    try:
                        await delete_space(confluence_client, payload.spec.key)
                    except Exception as rb_err:
                        logger.error(f"Rollback failed for space {payload.spec.key}: {rb_err}")
                raise
        return await handle_route("Confluence", _op())

    @router.delete("/{key}", name="delete space", status_code=200)
    async def delete_existing_space(key: str) -> JSONResponse:
        async def _op():
            await delete_space(confluence_client, key)
            return SuccessResponse(status="successful")
        return await handle_route("Confluence", _op())

    @router.post("/plugin/", name="install confluence plugin", status_code=200)
    async def install_confluence_plugin(payload: ConfluencePluginInstallRequest) -> JSONResponse:
        async def _op():
            plugin_bytes = await fetch_plugin_from_public_s3(payload.spec)
            upm_token = await get_upm_token(confluence_client)
            await install_plugin(confluence_client, plugin_bytes, payload.spec.plugin_name, upm_token)
            return SuccessResponse(status="successful")
        return await handle_route("Confluence", _op())

    @router.post("/plugin/upload", name="upload confluence plugin to MinIO", status_code=200)
    async def upload_confluence_plugin(payload: ConfluencePluginUploadRequest) -> JSONResponse:
        async def _op():
            data_url = payload.spec.file_content
            raw = data_url.split(",", 1)[1] if "," in data_url else data_url
            await upload_plugin_to_s3(base64.b64decode(raw), payload.spec.plugin_name)
            return JSONResponse({"status": "successful", "plugin_name": payload.spec.plugin_name})
        return await handle_route("Confluence", _op())

    @router.delete("/plugin/{plugin_key:path}", name="uninstall confluence plugin", status_code=200)
    async def uninstall_confluence_plugin(plugin_key: str) -> JSONResponse:
        async def _op():
            await uninstall_plugin(confluence_client, plugin_key)
            return SuccessResponse(status="successful")
        return await handle_route("Confluence", _op())

    # @router.get("/user-dirs", name="list user directories", status_code=200)
    # async def get_user_directories() -> JSONResponse:
    #     async def _op():
    #         dirs = await list_user_directories(confluence_client)
    #         return JSONResponse(content=dirs)
    #     return await handle_route("Confluence", _op())

    @router.post("/space-export/", name="export space to S3", status_code=200)
    async def export_confluence_space(payload: ConfluenceSpaceExportRequest) -> JSONResponse:
        async def _op():
            job_id, file_name = await trigger_space_export(confluence_client, payload.spec)
            await poll_export_job(confluence_client, job_id)
            archive_bytes = await download_export(confluence_client, job_id)
            await upload_archive_to_s3(archive_bytes, file_name)
            return JSONResponse({"status": "successful", "archive_name": file_name})
        return await handle_route("Confluence", _op())

    @router.post("/space-import/", name="import confluence space", status_code=200)
    async def import_confluence_space(payload: ConfluenceSpaceImportRequest) -> JSONResponse:
        async def _op():
            archive_bytes = await fetch_archive_from_s3(payload.spec)
            job_id = await upload_archive_and_start_restore(confluence_client, archive_bytes, payload.spec.archive_name)
            await poll_restore_job(confluence_client, job_id)
            return SuccessResponse(status="successful")
        return await handle_route("Confluence", _op())

    # @router.post("/user-dirs/sync", name="sync user directory", status_code=200)
    # async def sync_directory() -> JSONResponse:
    #     async def _op():
    #         await sync_user_directory(confluence_client)
    #         return SuccessResponse(status="successful")
    #     return await handle_route("Confluence", _op())

    return router
