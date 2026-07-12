import asyncio
from typing import Any

import httpx
from fastapi import HTTPException
from loguru import logger

from .conf import config
from .schemas import PluginInstallSpec, SpaceExportSpec, SpaceImportSpec, SpaceSpec
from app.global_conf import global_config
from app.helpers import fetch_from_s3


def _handle_response(response):
    if response.status_code > 299:
        try:
            errors = response.json().get("errors", [])
            detail = errors[0]["message"] if errors else response.text
        except Exception:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)


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


async def delete_space(confluence_client: Any, key: str):
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
    url = f"{global_config.CONFLUENCE_S3_PLUGINS_BASE_URL}/{payload.plugin_name}"
    return await fetch_from_s3(url, label=payload.plugin_name)


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
    endpoint = f"{config.CONFLUENCE_CROWD_ENDPOINT}/directory"
    try:
        response = await confluence_client.get(endpoint, headers={"Accept": "application/json"})
        _handle_response(response)
        return response.json()["directory"]
    except Exception as e:
        logger.error(f"Unexpected error listing user directories: {str(e)}")
        raise


async def sync_user_directory(confluence_client: Any) -> None:
    # Confluence has no supported way to manually trigger a directory sync — confirmed live
    # against a real AD-connector directory ID: POST /rest/crowd/latest/directory/{id}/synchronise
    # 404s (identical to Bitbucket, see app/v1/bitbucket/CLAUDE.md for the full investigation —
    # same underlying Atlassian Crowd-embedded module, same missing REST trigger, same undocumented
    # web-UI-only alternative that proved unreliable there). Directories sync on Confluence's own
    # automatic schedule; there is no reliable programmatic way to force one on demand.
    raise HTTPException(
        status_code=501,
        detail="Confluence has no supported API to trigger a user directory sync on demand. "
        "Directories sync on Confluence's own automatic schedule; use the admin UI to check "
        "status, not this endpoint to force one.",
    )


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


async def trigger_space_export(confluence_client: Any, payload: SpaceExportSpec) -> tuple[int, str]:
    endpoint = f"{config.CONFLUENCE_BACKUP_RESTORE_ENDPOINT}/backup/space"
    try:
        response = await confluence_client.post(endpoint, json={"spaceKeys": [payload.space_key]})
        _handle_response(response)
        job = response.json()
        logger.info(f"Export job {job['id']} created for space {payload.space_key}")
        return job["id"], job["fileName"]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger export for space {payload.space_key}: {e}")
        raise HTTPException(status_code=502, detail=f"Space export trigger failed: {e}")


async def poll_export_job(confluence_client: Any, job_id: int) -> None:
    endpoint = f"{config.CONFLUENCE_BACKUP_RESTORE_ENDPOINT}/jobs/{job_id}"
    for attempt in range(config.CONFLUENCE_JOB_MAX_POLLS):
        try:
            response = await confluence_client.get(endpoint)
            _handle_response(response)
            job = response.json()
            state = job.get("jobState", "UNKNOWN")
            logger.debug(f"Export job {job_id}: state={state} (attempt {attempt + 1})")
            if state == "FINISHED":
                logger.info(f"Export job {job_id} completed successfully")
                return
            if state == "FAILED":
                error_msg = job.get("errorMessage", "Unknown error")
                raise HTTPException(status_code=422, detail=f"Confluence space export failed: {error_msg}")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error polling export job {job_id}: {e}")
            raise HTTPException(status_code=502, detail=f"Error polling export job: {e}")
        await asyncio.sleep(config.CONFLUENCE_JOB_POLL_INTERVAL)
    raise HTTPException(
        status_code=504,
        detail=f"Export job {job_id} did not finish within {config.CONFLUENCE_JOB_MAX_POLLS * config.CONFLUENCE_JOB_POLL_INTERVAL:.0f}s",
    )


async def download_export(confluence_client: Any, job_id: int) -> bytes:
    endpoint = f"{config.CONFLUENCE_BACKUP_RESTORE_ENDPOINT}/jobs/{job_id}/download"
    try:
        response = await confluence_client.get(endpoint)
        _handle_response(response)
        logger.info(f"Downloaded export archive for job {job_id} ({len(response.content)} bytes)")
        return response.content
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download export for job {job_id}: {e}")
        raise HTTPException(status_code=502, detail=f"Export download failed: {e}")


async def upload_archive_to_s3(archive_bytes: bytes, archive_name: str) -> None:
    url = f"{global_config.CONFLUENCE_S3_IMPORTS_BASE_URL}/{archive_name}"
    try:
        async with httpx.AsyncClient(verify=False, timeout=60.0) as client:
            response = await client.put(
                url,
                content=archive_bytes,
                headers={"Content-Type": "application/zip"},
            )
            if response.status_code not in (200, 204):
                raise HTTPException(status_code=502, detail=f"S3 upload returned {response.status_code}")
            logger.info(f"Uploaded {archive_name} to S3 ({len(archive_bytes)} bytes)")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload archive {archive_name} to S3: {e}")
        raise HTTPException(status_code=502, detail=f"S3 upload failed: {e}")


async def upload_plugin_to_s3(plugin_bytes: bytes, plugin_name: str) -> None:
    url = f"{global_config.CONFLUENCE_S3_PLUGINS_BASE_URL}/{plugin_name}"
    try:
        async with httpx.AsyncClient(verify=False, timeout=60.0) as client:
            response = await client.put(
                url,
                content=plugin_bytes,
                headers={"Content-Type": "application/java-archive"},
            )
            if response.status_code not in (200, 204):
                raise HTTPException(status_code=502, detail=f"S3 upload returned {response.status_code}")
            logger.info(f"Uploaded plugin {plugin_name} to S3 ({len(plugin_bytes)} bytes)")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload plugin {plugin_name} to S3: {e}")
        raise HTTPException(status_code=502, detail=f"S3 plugin upload failed: {e}")




async def fetch_archive_from_s3(payload: SpaceImportSpec) -> bytes:
    url = f"{global_config.CONFLUENCE_S3_IMPORTS_BASE_URL}/{payload.archive_name}"
    return await fetch_from_s3(url, label=payload.archive_name)


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
    for attempt in range(config.CONFLUENCE_JOB_MAX_POLLS):
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
        await asyncio.sleep(config.CONFLUENCE_JOB_POLL_INTERVAL)
    raise HTTPException(
        status_code=504,
        detail=f"Restore job {job_id} did not finish within {config.CONFLUENCE_JOB_MAX_POLLS * config.CONFLUENCE_JOB_POLL_INTERVAL:.0f}s",
    )
