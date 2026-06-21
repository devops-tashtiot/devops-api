from fastapi.responses import JSONResponse
from app.v1.response_schemas import ExceptionResponse, SuccessResponse
from .schemas import ProjectSpec, StorageQuotaBytes, ProjectPermissionSpec, ArtifactoryProjectRequest, ArtifactoryStorageQuotaRequest, ArtifactoryPermissionRequest, ArtifactoryXrayUpdateRequest
from typing import Any
from .operations import assign_admin_group, assign_admin_user, create_project, delete_project, increase_storage_quota, assign_project_member, get_project_permissions, get_global_role, fetch_vuln_update_from_s3, upload_xray_vulnerability_update
from fastapi import APIRouter, HTTPException
from .conf import config

def get_v1_artifactory_router(artifactory_client: Any):
    router = APIRouter(prefix=config.API_PREFIX, tags=config.API_TAGS)

    @router.post("/", name="create project", status_code=200)
    async def create_new_project(payload: ArtifactoryProjectRequest) -> JSONResponse:
        try:
            await create_project(artifactory_client, payload.spec)
            if payload.spec.admin_user:
                await assign_admin_user(artifactory_client, payload.spec)
            if payload.spec.admin_group:
                await assign_admin_group(artifactory_client, payload.spec)
            return SuccessResponse(status="successful")
        except HTTPException as external_error:
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in Artifactory. {external_error.detail}",
                    status="Failed",
                    status_code=external_error.status_code,
                ).dict(),
                status_code=external_error.status_code,
            )
        except:
            await delete_project(artifactory_client, payload.spec.project_key)

    @router.post("/storage-quota", summary="Increase project storage quota", status_code=201)
    async def storage_quota(payload: ArtifactoryStorageQuotaRequest) -> JSONResponse:
        try:
            await increase_storage_quota(artifactory_client, payload.spec)
            return SuccessResponse(status="successful")
        except HTTPException as external_error:
            return JSONResponse(ExceptionResponse(stdout=f"Exception in Artifactory.{external_error.detail}", status="Failed", status_code=external_error.status_code).dict(), status_code=external_error.status_code)

    @router.get("/permissions/roles/{role_name}", name="get global role", status_code=200)
    async def get_role(role_name: str) -> JSONResponse:
        try:
            role = await get_global_role(artifactory_client, role_name)
            return JSONResponse(role)
        except HTTPException as external_error:
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in Artifactory. {external_error.detail}",
                    status="Failed",
                    status_code=external_error.status_code,
                ).dict(),
                status_code=external_error.status_code,
            )

    @router.post("/permissions", name="grant project permission to user or group", status_code=200)
    async def grant_permission(payload: ArtifactoryPermissionRequest) -> JSONResponse:
        try:
            await assign_project_member(artifactory_client, payload.spec)
            return SuccessResponse(status="successful")
        except HTTPException as external_error:
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in Artifactory. {external_error.detail}",
                    status="Failed",
                    status_code=external_error.status_code,
                ).dict(),
                status_code=external_error.status_code,
            )

    @router.get("/permissions/{project_key}", name="get all permissions for a project", status_code=200)
    async def fetch_permissions(project_key: str) -> JSONResponse:
        try:
            permissions = await get_project_permissions(artifactory_client, project_key)
            return JSONResponse(permissions)
        except HTTPException as external_error:
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in Artifactory. {external_error.detail}",
                    status="Failed",
                    status_code=external_error.status_code,
                ).dict(),
                status_code=external_error.status_code,
            )

    @router.post("/xray/vulnerability-update", name="upload Xray air-gapped vulnerability update", status_code=200)
    async def xray_vulnerability_update(payload: ArtifactoryXrayUpdateRequest) -> JSONResponse:
        try:
            file_bytes = await fetch_vuln_update_from_s3(payload.spec.file_name)
            await upload_xray_vulnerability_update(artifactory_client, file_bytes, payload.spec.file_name)
            return SuccessResponse(status="successful")
        except HTTPException as external_error:
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in Artifactory Xray. {external_error.detail}",
                    status="Failed",
                    status_code=external_error.status_code,
                ).dict(),
                status_code=external_error.status_code,
            )

    return router