import yaml
from .schemas import StorageQuotaBytes
from typing import Any
from .conf import config
from loguru import logger
from fastapi import HTTPException

def _handle_response(response):
    if response.status_code > 299:
        raise HTTPException(status_code=response.status_code, detail=f"errors: {response.text}")

async def create_project(bitbucket_client: Any, payload: ProjectSpec):
    key, name, description, public, endpoint = payload.key, payload.name, payload.description, payload.public, f"{config.BITBUCKET_ENDPOINT}/projects"
    try:
        body = {
            "key": key,
            "name": name,
            "description": description,
            "public": public
        }
=            response = await bitbucket_client.post(base_endpoint, json=body)
            _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error creating project {key}: {str(e)}")
        raise

async def delete_project(bitbucket_client: Any, payload: ProjectSpec):
    key, base_endpoint = payload.key, f"{config.BITBUCKET_ENDPOINT}/projects"
    endpoint = f"{base_endpoint}/{key}"
    try:
        print("hereeeeee")
        response = await bitbucket_client.delete(endpoint)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error deleting project {key}: {str(e)}")
        raise

async def assign_admin_permission(bitbucket_client: Any, payload: ProjectSpec):
    key, name, admin_user, base_endpoint = payload.key, payload.name, payload.admin_user, f"{config.BITBUCKET_ENDPOINT}/projects"
    endpoint = f"{base_endpoint}/{key}/permissions/users?name={admin_user}&permission=PROJECT_ADMIN"
    print(endpoint)
    try:
        response = await bitbucket_client.put(endpoint)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error assigning admin permission to project {key}: {str(e)}")
        raise