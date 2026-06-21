from typing import Any

import yaml
from fastapi import HTTPException
from loguru import logger
from tashtiot_apis_library import Git

from .conf import config
from .schemas import GroupSpec, SonarQubeConsumerSpec, SonarQubeConsumerUpdateSpec, SonarQubeSizeEnum

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


async def create_sonarqube_consumer(git: Git, payload: SonarQubeConsumerSpec) -> None:
    path = f"consumers/{payload.name}/config.yaml"
    data: dict = {"name": payload.name}
    if payload.plugins_list:
        data["plugins_list"] = ", ".join(payload.plugins_list)
    if payload.size != SonarQubeSizeEnum.default:
        data["size"] = payload.size.value
    content = yaml.dump(data, default_flow_style=False, sort_keys=False)
    try:
        await git.add_file(path, f"Add sonarqube consumer config for {payload.name}", content)
    except Exception as e:
        logger.error(f"Unexpected error creating sonarqube consumer config {payload.name}: {str(e)}")
        raise


async def update_sonarqube_consumer(git: Git, name: str, payload: SonarQubeConsumerUpdateSpec) -> None:
    path = f"consumers/{name}/config.yaml"
    data: dict = {"name": name}
    if payload.plugins_list:
        data["plugins_list"] = ", ".join(payload.plugins_list)
    if payload.size != SonarQubeSizeEnum.default:
        data["size"] = payload.size.value
    content = yaml.dump(data, default_flow_style=False, sort_keys=False)
    try:
        await git.update_file(path, f"Update sonarqube consumer config for {name}", content)
    except Exception as e:
        logger.error(f"Unexpected error updating sonarqube consumer config {name}: {str(e)}")
        raise


async def delete_sonarqube_consumer(git: Git, name: str) -> None:
    path = f"consumers/{name}/config.yaml"
    try:
        await git.delete_file(path, f"Delete sonarqube consumer config for {name}")
    except Exception as e:
        logger.error(f"Unexpected error deleting sonarqube consumer config {name}: {str(e)}")
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
