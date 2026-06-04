import yaml
from .schemas import StorageQuotaBytes
from typing import Any
from .conf import config
from loguru import logger
from fastapi import HTTPException

def _handle_response(response):
    if response.status_code > 299:
        raise HTTPException(status_code=response.status_code, detail=f"errors: {response.text}")

def convert_gb_to_bytes(gb):
    return int(gb * 1024 ** 3)

async def get_storage_quota_bytes(artifactory_client: Any, project_key: str) -> int:
    try:
        response = await artifactory_client.get(f"{config.ARTIFACTORY_ENDPOINT}/projects/{project_key}")
        _handle_response(response)
        return yaml.safe_load(response.text)['storage_quota_bytes']
    except Exception as e:
        logger.error(f"Unexpected error getting storage quota of project {project_key}: {str(e)}")
        raise

async def increase_storage_quota(artifactory_client: Any, payload: StorageQuotaBytes):
    project_key, storage_quota_bytes, endpoint = payload.name, convert_gb_to_bytes(payload.storage_quota_giga_bytes), f"{config.ARTIFACTORY_ENDPOINT}/projects/{payload.name}"
    try:
        current_storage_quota = await get_storage_quota_bytes(artifactory_client, project_key)
        body = \
            {
                "storage_quota_bytes": storage_quota_bytes + current_storage_quota,
            }
        response = await artifactory_client.put(endpoint, json=body)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error updating project quota of project {project_key}: {str(e)}")
        raise