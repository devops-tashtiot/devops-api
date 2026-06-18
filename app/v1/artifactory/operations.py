import yaml
from .schemas import ProjectSpec, StorageQuotaBytes, ProjectPermissionSpec, MemberType  # ProjectRole removed — roles fetched live from Artifactory
from typing import Any
from .conf import config
from app.global_conf import global_config
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


async def group_exists_in_jpd(artifactory_client: Any, group_name: str) -> bool:
    try:
        response = await artifactory_client.get(f"{config.ARTIFACTORY_ENDPOINT}/groups/{group_name}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Unexpected error checking if group {group_name} exists: {str(e)}")
        raise


async def sync_ldap_group(artifactory_client: Any, group_name: str) -> None:
    endpoint = f"{config.ARTIFACTORY_ENDPOINT}/ldap/groups/sync"
    try:
        body = {"ldap_setting_name": global_config.ARTIFACTORY_LDAP_SETTING_NAME, "groups": [group_name]}
        response = await artifactory_client.post(endpoint, json=body)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error syncing LDAP group {group_name}: {str(e)}")
        raise


async def assign_project_member(artifactory_client: Any, payload: ProjectPermissionSpec) -> None:
    roles = payload.roles
    if payload.member_type == MemberType.GROUP:
        if not await group_exists_in_jpd(artifactory_client, payload.member_name):
            logger.info(f"Group {payload.member_name} not found in JFrog — importing from LDAP")
            await sync_ldap_group(artifactory_client, payload.member_name)
        endpoint = f"{config.ARTIFACTORY_ENDPOINT}/projects/{payload.project_key}/groups/{payload.member_name}"
        body = {"name": payload.member_name, "roles": roles}
    else:
        endpoint = f"{config.ARTIFACTORY_ENDPOINT}/projects/{payload.project_key}/users/{payload.member_name}"
        body = {"name": payload.member_name, "roles": roles, "ignore_missing_user": False}
    try:
        response = await artifactory_client.put(endpoint, json=body)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error assigning {payload.member_type} {payload.member_name} to project {payload.project_key}: {str(e)}")
        raise


async def get_global_role(artifactory_client: Any, role_name: str) -> dict:
    try:
        response = await artifactory_client.get(f"{config.ARTIFACTORY_ENDPOINT}/roles/{role_name}")
        _handle_response(response)
        return response.json()
    except Exception as e:
        logger.error(f"Unexpected error fetching global role {role_name}: {str(e)}")
        raise


async def get_project_permissions(artifactory_client: Any, project_key: str) -> dict:
    try:
        users_response = await artifactory_client.get(f"{config.ARTIFACTORY_ENDPOINT}/projects/{project_key}/users")
        _handle_response(users_response)
        groups_response = await artifactory_client.get(f"{config.ARTIFACTORY_ENDPOINT}/projects/{project_key}/groups")
        _handle_response(groups_response)
        return {"users": users_response.json(), "groups": groups_response.json()}
    except Exception as e:
        logger.error(f"Unexpected error fetching permissions for project {project_key}: {str(e)}")
        raise