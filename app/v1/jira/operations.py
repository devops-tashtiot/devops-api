from typing import Any
from .conf import config
from .schemas import ProjectSpec
from loguru import logger
from fastapi import HTTPException


def _handle_response(response):
    if response.status_code > 299:
        try:
            body = response.json()
            messages = body.get("errorMessages", [])
            field_errors = list(body.get("errors", {}).values())
            detail = messages[0] if messages else (field_errors[0] if field_errors else response.text)
        except Exception:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)


async def create_project(jira_client: Any, payload: ProjectSpec) -> None:
    endpoint = f"{config.JIRA_ENDPOINT}/project"
    try:
        body = {
            "key": payload.key,
            "name": payload.name,
            "description": payload.description,
            "projectTypeKey": "software",
            **({"lead": payload.admin_user} if payload.admin_user else {}),
        }
        response = await jira_client.post(endpoint, json=body)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error creating project {payload.key}: {str(e)}")
        raise


async def delete_project(jira_client: Any, payload: ProjectSpec) -> None:
    endpoint = f"{config.JIRA_ENDPOINT}/project/{payload.key}"
    try:
        response = await jira_client.delete(endpoint)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error deleting project {payload.key}: {str(e)}")
        raise


async def assign_project_admin_user(jira_client: Any, payload: ProjectSpec) -> None:
    endpoint = f"{config.JIRA_ENDPOINT}/project/{payload.key}/role/10002"
    try:
        response = await jira_client.post(endpoint, json={"user": [payload.admin_user]})
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error assigning admin user to project {payload.key}: {str(e)}")
        raise


async def assign_project_admin_group(jira_client: Any, payload: ProjectSpec) -> None:
    endpoint = f"{config.JIRA_ENDPOINT}/project/{payload.key}/role/10002"
    try:
        response = await jira_client.post(endpoint, json={"group": [payload.admin_group]})
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error assigning admin group to project {payload.key}: {str(e)}")
        raise


async def list_user_directories(jira_client: Any) -> list[dict]:
    endpoint = f"{config.JIRA_ENDPOINT}/admin/user-dirs"
    try:
        response = await jira_client.get(endpoint)
        _handle_response(response)
        return response.json()
    except Exception as e:
        logger.error(f"Unexpected error listing user directories: {str(e)}")
        raise


async def sync_user_directory(jira_client: Any, directory_id: int) -> None:
    endpoint = f"{config.JIRA_ENDPOINT}/admin/user-dirs/{directory_id}/sync"
    try:
        response = await jira_client.post(endpoint)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error syncing user directory {directory_id}: {str(e)}")
        raise
