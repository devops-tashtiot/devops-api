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

async def list_repos(bitbucket_client: Any, key: str) -> list[dict]:
    endpoint = f"{config.BITBUCKET_ENDPOINT}/projects/{key}/repos"
    repos = []
    start = 0
    try:
        while True:
            response = await bitbucket_client.get(endpoint, params={"start": start, "limit": 100})
            _handle_response(response)
            page = response.json()
            repos.extend(page["values"])
            if page.get("isLastPage", True):
                break
            start = page["nextPageStart"]
        return repos
    except Exception as e:
        logger.error(f"Unexpected error listing repos for project {key}: {str(e)}")
        raise


async def delete_repo(bitbucket_client: Any, key: str, repo_slug: str) -> None:
    endpoint = f"{config.BITBUCKET_ENDPOINT}/projects/{key}/repos/{repo_slug}"
    try:
        response = await bitbucket_client.delete(endpoint)
        _handle_response(response)
        logger.info(f"Repo {key}/{repo_slug} deleted")
    except Exception as e:
        logger.error(f"Unexpected error deleting repo {key}/{repo_slug}: {str(e)}")
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
    endpoint = f"{config.BITBUCKET_CROWD_ENDPOINT}/directory"
    try:
        response = await bitbucket_client.get(endpoint, headers={"Accept": "application/json"})
        _handle_response(response)
        return response.json()["directory"]
    except Exception as e:
        logger.error(f"Unexpected error listing user directories: {str(e)}")
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
