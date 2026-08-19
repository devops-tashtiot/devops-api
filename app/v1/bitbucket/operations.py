from typing import Any

from fastapi import HTTPException
from loguru import logger
from tashtiot_apis_library.fastapi_template.utils import BaseAPI

from app.global_conf import global_config

from .conf import config
from .schemas import MirrorProjectSpec, ProjectSpec


def _handle_response(response):
    if response.status_code > 299:
        try:
            errors = response.json().get("errors", [])
            detail = errors[0]["message"] if errors else response.text
        except Exception:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)


async def _assert_user_exists(bitbucket_client: Any, admin_user: str):
    endpoint = f"{config.BITBUCKET_ENDPOINT}/admin/users?filter={admin_user}"
    try:
        response = await bitbucket_client.get(endpoint)
        _handle_response(response)
        if not response.json().get("values"):
            raise HTTPException(
                status_code=404,
                detail=f"User '{admin_user}' does not exist in Bitbucket",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error checking user {admin_user} exists: {e!s}")
        raise


async def _assert_group_exists(bitbucket_client: Any, admin_group: str):
    endpoint = f"{config.BITBUCKET_ENDPOINT}/admin/groups?filter={admin_group}"
    try:
        response = await bitbucket_client.get(endpoint)
        _handle_response(response)
        if not response.json().get("values"):
            raise HTTPException(
                status_code=404,
                detail=f"Group '{admin_group}' does not exist in Bitbucket",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error checking group {admin_group} exists: {e!s}")
        raise


async def validate_admin_principals(bitbucket_client: Any, payload: ProjectSpec):
    if payload.admin_user:
        await _assert_user_exists(bitbucket_client, payload.admin_user)
    if payload.admin_group:
        await _assert_group_exists(bitbucket_client, payload.admin_group)


async def create_project(bitbucket_client: Any, payload: ProjectSpec) -> dict:
    key, name, description, endpoint = (
        payload.key,
        payload.name,
        payload.description,
        f"{config.BITBUCKET_ENDPOINT}/projects",
    )
    try:
        body = {
            "key": key,
            "name": name,
            "description": description,
            "public": payload.public,
        }
        response = await bitbucket_client.post(endpoint, json=body)
        _handle_response(response)
        return response.json()
    except Exception as e:
        logger.error(f"Unexpected error creating project {key}: {e!s}")
        raise


async def _get_registered_mirror_server(bitbucket_client: Any) -> dict:
    # Discovered live via the Mirroring API rather than a configured name — this platform
    # registers exactly one physical Smart Mirrors server (Administration > Mirroring), so
    # there's nothing to disambiguate by name; devops-api just uses whichever one exists.
    endpoint = f"{config.BITBUCKET_MIRRORING_ENDPOINT}/mirrorServers"
    start = 0
    mirrors: list[dict] = []
    try:
        while True:
            response = await bitbucket_client.get(
                endpoint, params={"start": start, "limit": 100}
            )
            _handle_response(response)
            page = response.json()
            mirrors.extend(page["values"])
            if page.get("isLastPage", True):
                break
            start = page["nextPageStart"]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error listing Bitbucket mirror servers: {e!s}")
        raise
    if not mirrors:
        raise HTTPException(
            status_code=404,
            detail="No Bitbucket Smart Mirrors server is registered on this instance",
        )
    if len(mirrors) > 1:
        names = [m.get("name") for m in mirrors]
        raise HTTPException(
            status_code=409,
            detail=f"Multiple Bitbucket Smart Mirrors servers are registered {names} — "
            "devops-api only supports a deployment with exactly one",
        )
    return mirrors[0]


async def _find_upstream_id(mirror_client: Any) -> str:
    # The mirror server tracks our main Bitbucket instance as one of its "upstreams" —
    # resolved live by matching baseUrl rather than assuming an ID, since the upstreamId is
    # assigned by the mirror server itself when the two instances were first connected.
    endpoint = f"{config.BITBUCKET_MIRRORING_ENDPOINT}/upstreamServers"
    start = 0
    try:
        while True:
            response = await mirror_client.get(
                endpoint, params={"start": start, "limit": 100}
            )
            _handle_response(response)
            page = response.json()
            for upstream in page["values"]:
                if upstream.get("baseUrl") == global_config.BITBUCKET_API_URL:
                    return upstream["id"]
            if page.get("isLastPage", True):
                break
            start = page["nextPageStart"]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error listing upstream servers on mirror: {e!s}")
        raise
    raise HTTPException(
        status_code=502,
        detail="This Bitbucket instance is not registered as an upstream on the target "
        "mirror server — the mirror farm connection must be set up first",
    )


async def register_project_with_mirror(
    bitbucket_client: Any, key: str, project_id: int
) -> None:
    mirror = await _get_registered_mirror_server(bitbucket_client)
    # Same admin credentials as the main Bitbucket — per this platform's mirror setup, the
    # physical mirror servers share the same auth as the source instance.
    mirror_client = BaseAPI(
        mirror["baseUrl"],
        auth=(global_config.BITBUCKET_USERNAME, global_config.BITBUCKET_PASSWORD),
    ).client
    upstream_id = await _find_upstream_id(mirror_client)
    endpoint = (
        f"{config.BITBUCKET_MIRRORING_ENDPOINT}/upstreamServers/{upstream_id}"
        f"/settings/projects/{project_id}"
    )
    try:
        response = await mirror_client.post(endpoint)
        _handle_response(response)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error registering project {key} with mirror: {e!s}")
        raise


async def create_mirror_project(
    bitbucket_client: Any, payload: MirrorProjectSpec
) -> dict:
    # mirrored_env_destination is purely a display-name suffix — it does NOT name a
    # Bitbucket Smart Mirrors server. The actual mirror server is discovered live (see
    # _get_registered_mirror_server), independent of which suffix was chosen.
    mirrored_name_payload = payload.model_copy(
        update={"name": f"{payload.name} - {payload.mirrored_env_destination}"}
    )
    project = await create_project(bitbucket_client, mirrored_name_payload)
    await register_project_with_mirror(bitbucket_client, payload.key, project["id"])
    return project


async def list_repos(bitbucket_client: Any, key: str) -> list[dict]:
    endpoint = f"{config.BITBUCKET_ENDPOINT}/projects/{key}/repos"
    repos = []
    start = 0
    try:
        while True:
            response = await bitbucket_client.get(
                endpoint, params={"start": start, "limit": 100}
            )
            _handle_response(response)
            page = response.json()
            repos.extend(page["values"])
            if page.get("isLastPage", True):
                break
            start = page["nextPageStart"]
        return repos
    except Exception as e:
        logger.error(f"Unexpected error listing repos for project {key}: {e!s}")
        raise


async def delete_repo(bitbucket_client: Any, key: str, repo_slug: str) -> None:
    endpoint = f"{config.BITBUCKET_ENDPOINT}/projects/{key}/repos/{repo_slug}"
    try:
        response = await bitbucket_client.delete(endpoint)
        _handle_response(response)
        logger.info(f"Repo {key}/{repo_slug} deleted")
    except Exception as e:
        logger.error(f"Unexpected error deleting repo {key}/{repo_slug}: {e!s}")
        raise


async def delete_project(bitbucket_client: Any, key: str) -> None:
    # Bitbucket refuses to delete a project that still contains repositories — confirmed
    # live: DELETE /projects/{key} returns 409 IntegrityException ("cannot be deleted because
    # it has repositories") whenever any repo exists under it. Delete all repos first so the
    # project delete itself can succeed.
    for repo in await list_repos(bitbucket_client, key):
        await delete_repo(bitbucket_client, key, repo["slug"])

    endpoint = f"{config.BITBUCKET_ENDPOINT}/projects/{key}"
    try:
        response = await bitbucket_client.delete(endpoint)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error deleting project {key}: {e!s}")
        raise


async def assign_admin_group_permission(bitbucket_client: Any, payload: ProjectSpec):
    key, admin_group, base_endpoint = (
        payload.key,
        payload.admin_group,
        f"{config.BITBUCKET_ENDPOINT}/projects",
    )
    endpoint = f"{base_endpoint}/{key}/permissions/groups?name={admin_group}&permission=PROJECT_ADMIN"
    try:
        response = await bitbucket_client.put(endpoint)
        _handle_response(response)
    except Exception as e:
        logger.error(
            f"Unexpected error assigning admin group permission to project {key}: {e!s}"
        )
        raise


async def assign_admin_permission(bitbucket_client: Any, payload: ProjectSpec):
    key, admin_user, base_endpoint = (
        payload.key,
        payload.admin_user,
        f"{config.BITBUCKET_ENDPOINT}/projects",
    )
    endpoint = f"{base_endpoint}/{key}/permissions/users?name={admin_user}&permission=PROJECT_ADMIN"
    try:
        response = await bitbucket_client.put(endpoint)
        _handle_response(response)
    except Exception as e:
        logger.error(
            f"Unexpected error assigning admin permission to project {key}: {e!s}"
        )
        raise


async def sync_user_directory(bitbucket_client: Any) -> None:
    # Bitbucket Data Center has no supported way to manually trigger a directory sync.
    # /rest/crowd/latest/directory/{id}/synchronise (Jira/Confluence's working path) 404s here.
    # The web UI's internal servlet action (/plugins/servlet/embedded-crowd/directories/sync)
    # accepts the request and returns 302, but live testing proved that response is not a
    # reliable success signal: the very first call happened to coincide with Bitbucket's own
    # ~30-minute automatic sync schedule, but every subsequent call (verified independently
    # both via tight API polling and directly in the Bitbucket admin UI) produced zero effect —
    # no in-progress state, no updated timestamp. Building on it would report false successes
    # on requests that silently did nothing. See app/v1/bitbucket/CLAUDE.md for the full
    # investigation. Directories can only be synced by waiting for Bitbucket's own schedule or
    # via direct admin UI login — there is no reliable programmatic trigger.
    raise HTTPException(
        status_code=501,
        detail="Bitbucket has no supported API to trigger a user directory sync on demand. "
        "Directories sync on Bitbucket's own automatic schedule; use the admin UI to check "
        "status, not this endpoint to force one.",
    )
