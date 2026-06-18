from typing import Any

from fastapi import HTTPException
from loguru import logger

from .conf import config
from .schemas import GroupSpec

SONARQUBE_GLOBAL_PERMISSIONS = config.SONARQUBE_GLOBAL_PERMISSIONS
SONARQUBE_TEMPLATE_PERMISSIONS = config.SONARQUBE_TEMPLATE_PERMISSIONS


def _handle_response(response):
    if response.status_code > 299:
        try:
            errors = response.json().get("errors", [])
            detail = errors[0]["msg"] if errors else response.text
        except Exception:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)


async def create_group(sonarqube_client: Any, payload: GroupSpec):
    name, endpoint = payload.name, f"{config.SONARQUBE_ENDPOINT}/user_groups/create"
    try:
        response = await sonarqube_client.post(endpoint, params={"name": name})
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error creating group {name}: {str(e)}")
        raise


async def delete_group(sonarqube_client: Any, payload: GroupSpec):
    name, endpoint = payload.name, f"{config.SONARQUBE_ENDPOINT}/user_groups/delete"
    try:
        response = await sonarqube_client.post(endpoint, params={"name": name})
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error deleting group {name}: {str(e)}")
        raise


async def assign_global_permissions(sonarqube_client: Any, payload: GroupSpec):
    name, endpoint = payload.name, f"{config.SONARQUBE_ENDPOINT}/permissions/add_group"
    try:
        for permission in config.SONARQUBE_GLOBAL_PERMISSIONS:
            response = await sonarqube_client.post(endpoint, params={"groupName": name, "permission": permission})
            _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error assigning global permissions to group {name}: {str(e)}")
        raise


async def assign_template_permissions(sonarqube_client: Any, payload: GroupSpec):
    name, endpoint = payload.name, f"{config.SONARQUBE_ENDPOINT}/permissions/add_group_to_template"
    try:
        for permission in config.SONARQUBE_TEMPLATE_PERMISSIONS:
            response = await sonarqube_client.post(
                endpoint,
                params={
                    "groupName": name,
                    "templateName": config.SONARQUBE_ADMIN_TEMPLATE_NAME,
                    "permission": permission,
                },
            )
            _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error assigning template permissions to group {name}: {str(e)}")
        raise
