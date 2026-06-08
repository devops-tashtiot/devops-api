import asyncio
from typing import Any

import httpx
from fastapi import HTTPException
from loguru import logger

from .conf import config
from .schemas import PluginInstallSpec, SpaceImportSpec, SpaceSpec


def _handle_response(response):
    if response.status_code > 299:
        raise HTTPException(status_code=response.status_code, detail=f"errors: {response.text}")


async def create_space(confluence_client: Any, payload: SpaceSpec):
    key, name, description = payload.key, payload.name, payload.description
    endpoint = f"{config.CONFLUENCE_ENDPOINT}/space"
    try:
        body = {
            "key": key,
            "name": name,
            "description": {
                "plain": {
                    "value": description,
                    "representation": "plain",
                }
            },
        }
        response = await confluence_client.post(endpoint, json=body)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error creating space {key}: {str(e)}")
        raise


async def delete_space(confluence_client: Any, payload: SpaceSpec):
    key = payload.key
    endpoint = f"{config.CONFLUENCE_ENDPOINT}/space/{key}"
    try:
        response = await confluence_client.delete(endpoint)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error deleting space {key}: {str(e)}")
        raise


async def assign_space_admin(confluence_client: Any, payload: SpaceSpec):
    key, admin_user = payload.key, payload.admin_user
    try:
        user_resp = await confluence_client.get(f"{config.CONFLUENCE_ENDPOINT}/user?username={admin_user}")
        _handle_response(user_resp)
        user_key = user_resp.json().get("userKey")

        grant_endpoint = f"{config.CONFLUENCE_ENDPOINT}/space/{key}/permissions/user/{user_key}/grant"
        for op in [{"operationKey": "read", "targetType": "space"}, {"operationKey": "administer", "targetType": "space"}]:
            _handle_response(await confluence_client.put(grant_endpoint, json=[op]))
    except Exception as e:
        logger.error(f"Unexpected error assigning user admin to space {key}: {str(e)}")
        raise


async def assign_space_group_admin(confluence_client: Any, payload: SpaceSpec):
    key, admin_group = payload.key, payload.admin_group
    try:
        grant_endpoint = f"{config.CONFLUENCE_ENDPOINT}/space/{key}/permissions/group/{admin_group}/grant"
        for op in [{"operationKey": "read", "targetType": "space"}, {"operationKey": "administer", "targetType": "space"}]:
            _handle_response(await confluence_client.put(grant_endpoint, json=[op]))
    except Exception as e:
        logger.error(f"Unexpected error assigning group admin to space {key}: {str(e)}")
        raise


async def fetch_plugin_from_public_s3(payload: PluginInstallSpec) -> bytes:
    url = f"{config.S3_PLUGINS_BASE_URL}/{payload.plugin_name}"
    try:
        async with httpx.AsyncClient(verify=False, timeout=60.0) as client:
            response = await client.get(url)
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Plugin not found in S3: {payload.plugin_name}")
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail=f"S3 returned {response.status_code} for {url}")
            logger.info(f"Fetched {payload.plugin_name} from S3 ({len(response.content)} bytes)")
            return response.content
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch plugin {payload.plugin_name} from S3: {e}")
        raise HTTPException(status_code=502, detail=f"S3 fetch failed: {e}")


async def get_upm_token(confluence_client: Any) -> str:
    endpoint = f"{config.CONFLUENCE_UPM_ENDPOINT}/?os_authType=basic"
    try:
        response = await confluence_client.get(endpoint)
        _handle_response(response)
        token = response.headers.get("upm-token")
        if not token:
            raise HTTPException(status_code=502, detail="Confluence did not return a upm-token header")
        logger.info("Fetched UPM token from Confluence")
        return token
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get UPM token: {e}")
        raise HTTPException(status_code=502, detail=f"UPM token fetch failed: {e}")


async def install_plugin(confluence_client: Any, plugin_bytes: bytes, plugin_name: str, upm_token: str) -> None:
    endpoint = f"{config.CONFLUENCE_UPM_ENDPOINT}/?token={upm_token}"
    try:
        response = await confluence_client.post(
            endpoint,
            files={"plugin": (plugin_name, plugin_bytes, "application/octet-stream")},
        )
        _handle_response(response)
        logger.info(f"Installed plugin {plugin_name} via UPM")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to install plugin {plugin_name}: {e}")
        raise HTTPException(status_code=502, detail=f"Plugin install failed: {e}")


async def list_user_directories(confluence_client: Any) -> list[dict]:
    endpoint = f"{config.CONFLUENCE_ENDPOINT}/admin/user-dirs"
    try:
        response = await confluence_client.get(endpoint)
        _handle_response(response)
        return response.json()
    except Exception as e:
        logger.error(f"Unexpected error listing user directories: {str(e)}")
        raise


async def sync_user_directory(confluence_client: Any, directory_id: int) -> None:
    endpoint = f"{config.CONFLUENCE_ENDPOINT}/admin/user-dirs/{directory_id}/sync"
    try:
        response = await confluence_client.post(endpoint)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error syncing user directory {directory_id}: {str(e)}")
        raise


async def uninstall_plugin(confluence_client: Any, plugin_key: str) -> None:
    # UPM resource path appends "-key" suffix to the plugin key
    endpoint = f"{config.CONFLUENCE_UPM_ENDPOINT}/{plugin_key}-key"
    try:
        response = await confluence_client.delete(endpoint)
        _handle_response(response)
        logger.info(f"Plugin {plugin_key} uninstalled from Confluence")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to uninstall plugin {plugin_key}: {e}")
        raise HTTPException(status_code=502, detail=f"Plugin uninstall failed: {e}")


async def fetch_archive_from_s3(payload: SpaceImportSpec) -> bytes:
    url = f"{config.S3_IMPORTS_BASE_URL}/{payload.archive_name}"
    try:
        async with httpx.AsyncClient(verify=False, timeout=60.0) as client:
            response = await client.get(url)
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Archive not found in S3: {payload.archive_name}")
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail=f"S3 returned {response.status_code} for {url}")
            logger.info(f"Fetched {payload.archive_name} from S3 ({len(response.content)} bytes)")
            return response.content
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch archive {payload.archive_name} from S3: {e}")
        raise HTTPException(status_code=502, detail=f"S3 fetch failed: {e}")


async def upload_archive_and_start_restore(confluence_client: Any, archive_bytes: bytes, archive_name: str) -> int:
    endpoint = f"{config.CONFLUENCE_BACKUP_RESTORE_ENDPOINT}/restore/space/upload"
    try:
        response = await confluence_client.post(
            endpoint,
            files={"file": (archive_name, archive_bytes, "application/zip")},
            headers={"X-Atlassian-Token": "no-check"},
        )
        _handle_response(response)
        job_id = response.json()["id"]
        logger.info(f"Restore job {job_id} created for archive {archive_name}")
        return job_id
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload archive {archive_name} to Confluence restore API: {e}")
        raise HTTPException(status_code=502, detail=f"Confluence restore upload failed: {e}")


async def poll_restore_job(confluence_client: Any, job_id: int) -> dict:
    endpoint = f"{config.CONFLUENCE_BACKUP_RESTORE_ENDPOINT}/jobs/{job_id}"
    for attempt in range(config.JOB_MAX_POLLS):
        try:
            response = await confluence_client.get(endpoint)
            _handle_response(response)
            job = response.json()
            state = job.get("jobState", "UNKNOWN")
            logger.debug(f"Restore job {job_id}: state={state} (attempt {attempt + 1})")
            if state == "FINISHED":
                logger.info(f"Restore job {job_id} completed successfully")
                return job
            if state == "FAILED":
                error_msg = job.get("errorMessage", "Unknown error")
                raise HTTPException(status_code=422, detail=f"Confluence space restore failed: {error_msg}")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error polling restore job {job_id}: {e}")
            raise HTTPException(status_code=502, detail=f"Error polling restore job: {e}")
        await asyncio.sleep(config.JOB_POLL_INTERVAL)
    raise HTTPException(
        status_code=504,
        detail=f"Restore job {job_id} did not finish within {config.JOB_MAX_POLLS * config.JOB_POLL_INTERVAL:.0f}s",
    )
