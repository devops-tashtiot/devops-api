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


# admin_user is technically already validated as a side effect of create_project (it's sent
# as the project lead, and Jira rejects creation outright for a nonexistent one — confirmed
# live) — that alone never orphans anything, since create_project is the first call and fails
# atomically. This explicit pre-check exists anyway so a bad admin_user fails fast with a
# clean, specific message before any write to Jira happens at all, matching admin_group's
# check below and Bitbucket's validate_admin_principals shape, rather than relying on
# create_project's own error message as the only signal.
async def assert_user_exists(jira_client: Any, admin_user: str) -> None:
    endpoint = f"{config.JIRA_ENDPOINT}/user?username={admin_user}"
    try:
        response = await jira_client.get(endpoint)
        _handle_response(response)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error checking user {admin_user} exists: {str(e)}")
        raise


# admin_group's gap is real, not just defensive symmetry like admin_user's above: it's only
# used in the later, separate assign_project_admin_group call, which Jira reports as a clean
# 410 rather than a crash — meaning it hit the `except HTTPException` branch in routes.py, not
# the bare `except:` rollback path, and was silently leaving a half-configured project
# (created, admin_user assigned, group assignment failed) behind. Confirmed live: created a
# real project, sent a nonexistent group, got 410, and the project still existed afterward.
# Checking existence up front — before create_project ever runs — means a bad admin_group
# fails the whole request cleanly, with nothing to roll back.
async def assert_group_exists(jira_client: Any, admin_group: str) -> None:
    # Unlike Bitbucket's filter-search endpoint (200 with an empty "values" list when nothing
    # matches), Jira's exact-lookup group endpoint returns a genuine 404 with its own clean
    # "The group named 'X' does not exist" message — _handle_response already surfaces that
    # correctly, no extra empty-result check needed here.
    endpoint = f"{config.JIRA_ENDPOINT}/group?groupname={admin_group}"
    try:
        response = await jira_client.get(endpoint)
        _handle_response(response)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error checking group {admin_group} exists: {str(e)}")
        raise


async def create_project(jira_client: Any, payload: ProjectSpec) -> None:
    endpoint = f"{config.JIRA_ENDPOINT}/project"
    try:
        body = {
            "key": payload.key,
            "name": payload.name,
            "description": payload.description,
            "projectTypeKey": "software",
            "lead": payload.admin_user,
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
    endpoint = f"{config.JIRA_CROWD_ENDPOINT}/directory"
    try:
        response = await jira_client.get(endpoint, headers={"Accept": "application/json"})
        _handle_response(response)
        return response.json()["directories"]
    except Exception as e:
        logger.error(f"Unexpected error listing user directories: {str(e)}")
        raise


async def sync_user_directory(jira_client: Any) -> None:
    # Jira has no supported way to manually trigger a directory sync on demand — confirmed
    # live against a real LDAP-connected directory: POST /rest/crowd/latest/directory/{id}/
    # synchronise 404s even with the *correct* directory id (not just id 1, the wrong,
    # internal-directory id this code used to pick first). Same underlying Atlassian
    # Crowd-embedded module, same missing REST trigger as Bitbucket and Confluence — see
    # app/v1/bitbucket/CLAUDE.md for the full investigation. Directories sync on Jira's own
    # automatic schedule; there is no reliable programmatic way to force one on demand.
    raise HTTPException(
        status_code=501,
        detail="Jira has no supported API to trigger a user directory sync on demand. "
        "Directories sync on Jira's own automatic schedule; use the admin UI to check "
        "status, not this endpoint to force one.",
    )
