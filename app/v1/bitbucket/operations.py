from .schemas import ProjectSpec
from typing import Any
from .conf import config
from loguru import logger
from fastapi import HTTPException

def _handle_response(response):
    if response.status_code > 299:
        try:
            errors = response.json().get("errors", [])
            detail = errors[0]["message"] if errors else response.text
        except Exception:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)

async def create_project(bitbucket_client: Any, payload: ProjectSpec):
    key, name, description, endpoint = payload.key, payload.name, payload.description, f"{config.BITBUCKET_ENDPOINT}/projects"
    try:
        body = {
            "key": key,
            "name": name,
            "description": description,
            "public": payload.public,
        }
        response = await bitbucket_client.post(endpoint, json=body)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error creating project {key}: {str(e)}")
        raise

async def delete_project(bitbucket_client: Any, key: str) -> None:
    endpoint = f"{config.BITBUCKET_ENDPOINT}/projects/{key}"
    try:
        response = await bitbucket_client.delete(endpoint)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error deleting project {key}: {str(e)}")
        raise

async def assign_admin_group_permission(bitbucket_client: Any, payload: ProjectSpec):
    key, admin_group, base_endpoint = payload.key, payload.admin_group, f"{config.BITBUCKET_ENDPOINT}/projects"
    endpoint = f"{base_endpoint}/{key}/permissions/groups?name={admin_group}&permission=PROJECT_ADMIN"
    try:
        response = await bitbucket_client.put(endpoint)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error assigning admin group permission to project {key}: {str(e)}")
        raise


async def assign_admin_permission(bitbucket_client: Any, payload: ProjectSpec):
    key, admin_user, base_endpoint = payload.key, payload.admin_user, f"{config.BITBUCKET_ENDPOINT}/projects"
    endpoint = f"{base_endpoint}/{key}/permissions/users?name={admin_user}&permission=PROJECT_ADMIN"
    try:
        response = await bitbucket_client.put(endpoint)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error assigning admin permission to project {key}: {str(e)}")
        raise


async def list_user_directories(bitbucket_client: Any) -> list[dict]:
    endpoint = f"{config.BITBUCKET_ENDPOINT}/admin/user-dirs"
    try:
        response = await bitbucket_client.get(endpoint)
        _handle_response(response)
        return response.json()
    except Exception as e:
        logger.error(f"Unexpected error listing user directories: {str(e)}")
        raise


async def sync_user_directory(bitbucket_client: Any) -> None:
    directories = await list_user_directories(bitbucket_client)
    if not directories:
        raise HTTPException(status_code=404, detail="No user directories found in Bitbucket")
    directory_id = directories[0]["id"]
    endpoint = f"{config.BITBUCKET_ENDPOINT}/admin/user-dirs/{directory_id}/sync"
    try:
        response = await bitbucket_client.post(endpoint)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error syncing user directory {directory_id}: {str(e)}")
        raise
