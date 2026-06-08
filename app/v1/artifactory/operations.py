import yaml
from .schemas import ProjectSpec, StorageQuotaBytes
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

async def create_project(artifactory_client: Any, payload: ProjectSpec) -> None:
    endpoint = f"{config.ARTIFACTORY_ENDPOINT}/projects"
    try:
        body = {
            "display_name": payload.name,
            "project_key": payload.project_key,
            "storage_quota_bytes": convert_gb_to_bytes(payload.storage_quota_giga_bytes),
        }
        response = await artifactory_client.post(endpoint, json=body)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error creating project {payload.project_key}: {str(e)}")
        raise


async def delete_project(artifactory_client: Any, project_key: str) -> None:
    endpoint = f"{config.ARTIFACTORY_ENDPOINT}/projects/{project_key}"
    try:
        response = await artifactory_client.delete(endpoint)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error deleting project {project_key}: {str(e)}")
        raise


async def assign_admin_user(artifactory_client: Any, payload: ProjectSpec) -> None:
    endpoint = f"{config.ARTIFACTORY_ENDPOINT}/projects/{payload.project_key}/users/{payload.admin_user}"
    try:
        body = {"name": payload.admin_user, "roles": ["PROJECT_ADMIN"], "ignore_missing_user": False}
        response = await artifactory_client.put(endpoint, json=body)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error assigning admin user to project {payload.project_key}: {str(e)}")
        raise


async def assign_admin_group(artifactory_client: Any, payload: ProjectSpec) -> None:
    endpoint = f"{config.ARTIFACTORY_ENDPOINT}/projects/{payload.project_key}/groups/{payload.admin_group}"
    try:
        body = {"name": payload.admin_group, "roles": ["PROJECT_ADMIN"]}
        response = await artifactory_client.put(endpoint, json=body)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error assigning admin group to project {payload.project_key}: {str(e)}")
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