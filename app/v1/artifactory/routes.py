from fastapi.responses import JSONResponse
from app.v1.response_schemas import ExceptionResponse, SuccessResponse
from .schemas import StorageQuotaBytes
from typing import Any
from .operations import increase_storage_quota
from fastapi import APIRouter, HTTPException
from .conf import config

def get_v1_artifactory_router(artifactory_client: Any):
    router = APIRouter(prefix=config.API_PREFIX, tags=config.API_TAGS)
    
    @router.post("/storage-quota", summary="Increase project storage quota", status_code=201)
    async def storage_quota(payload: StorageQuotaBytes) -> JSONResponse:
        try:
            await increase_storage_quota(artifactory_client, payload)
            return SuccessResponse(status="successful")
        except HTTPException as external_error:
            # platform want to return here status_code=http_status.HTTP_502_BAD_GATEWAY but it will not be informative so i return this!
            return JSONResponse(ExceptionResponse(stdout=f"Exception in Artifactory.{external_error.detail}", status="Failed", status_code=external_error.status_code).dict(), status_code=external_error.status_code)

    return router