# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Dev bootstrap (first time on a machine)

```bash
# 1. Install the library from PyPI (requirements.txt pins the version)
pip install tashtiot-apis-library==0.1.0

# 2. Edit .env directly (do NOT copy .env.example — .env is the live config file)
# Minimum for local dev — disable ArgoCD if you have no SSH key:
#   ARGOCD_ENABLE_API=false
# Confluence local stack: CONFLUENCE_API_URL=http://localhost:8090, user admin, pass 12345678
# Bitbucket  local stack: BITBUCKET_API_URL=http://localhost:7990,   user admin, pass 12345678
# SonarQube  local stack: SONARQUBE_API_URL=http://localhost:9000,   user admin, pass SonarqubeDevops1!
# ArgoCD allowed envs: ARGOCD_ALLOWED_ENVS=["prod"] for network A, ["prod","dr","int"] for network B

# 3. Start the server (from this directory)
uvicorn app.main:create_app --factory --port 5000
```

## Commands

```bash
# Install dependencies (install library editable first if developing locally)
pip install -e ../apis-library
pip install -r requirements.txt

# Run the dev server
uvicorn app.main:create_app --factory --reload --port 5000

# Run all tests
pytest

# Run a specific test suite
pytest tests/v1/dns -v
pytest tests/v1/sonarqube -v
pytest tests/v2/dns -v

# Run a single test file
pytest tests/v1/sonarqube/test_sonarqube_routes.py -v

# Run with coverage
pytest --cov=app --cov-report=term-missing
```

## Architecture

The app is a FastAPI service that orchestrates DNS records, HAProxy load-balancer configs, and chat messages by delegating to external platforms (AWX, ArgoCD, Vault, Bitbucket/Git). All external client objects are constructed once in `app/main.py:create_app()` and passed into router factories as arguments — there is no global state or DI framework.

**Entry point:** `app/main.py` — `create_app()` builds the FastAPI app via `tashtiot_apis_library.general_create_app()`, instantiates external service clients, and mounts routers.

**Module layout** — every feature under `app/v1/<feature>/` follows this four-file convention:
- `conf.py` — `pydantic-settings` class, reads `.env`; instantiated as `config` at module level
- `schemas.py` — Pydantic request/response models
- `routes.py` — router factory `get_<feature>_router(...)` that closes over injected clients
- `operations.py` / `operation_*.py` — async business logic called by the router

**Configuration** — each module (`global_conf.py`, `v1/dns/conf.py`, `v1/haproxy/conf.py`, `v1/chat/conf.py`) has its own `pydantic-settings` class. All read from `.env` (see `.env.example`). Required fields without defaults must be in `.env` before the app starts (notably `HAPROXY_*`, `ARGOCD_*`, `VAULT_*`).

**Internal library** — `tashtiot-apis-library` (version-pinned in `requirements.txt`) provides `general_create_app`, `BaseAPI`, `Git`, `ArgoCD`, `Vault`, `AWX` connectors, and shared response types like `ArgoOperationResponse` / `ExternalServiceError`. Treat it as a black-box SDK.

**Connector usage rule** — always import and use the high-level service classes (`ArgoCD`, `Git`, `Vault`, `AWX`) from `tashtiot_apis_library`. Never import or instantiate the low-level `*Client` classes (e.g. `ArgoCDClient`, `GitClient`) directly — those are internal implementation details of the library. Each service class is instantiated once in `app/main.py:create_app()` and passed into router factories. See `app/v1/haproxy/operations.py` as the reference pattern for ArgoCD.

**Tests** — `tests/v1/` and `tests/v2/` mirror the app structure. Fixtures (client, mock clients, sample payloads) live in `conftest.py` files at each level. `pytest.ini` sets `pythonpath = .` so imports start from the repo root.

**CI** — GitHub Actions, `.github/workflows/docker-publish.yml`, is the *actual* active
pipeline (do not trust `.woodpecker/build.yaml` — it targets a different registry
(`artifactory.app.com`), its one step only runs `when: event: tag`, and no tag-push happens
in normal workflow, so it never actually builds anything; treat it as dead/vestigial).

The GitHub Actions workflow fires on **every push to `master`** (not just tags), unless the
commit message contains `chore(release):` (guards against its own bump commits looping). On
each qualifying push it, in order:

1. Bumps the version via `git-cliff` (conventional-commit-driven — reads commit message
   prefixes like `fix:`/`feat:` to decide the version bump) and writes `CHANGELOG.md`
2. Commits `chore(release): vX.Y.Z [skip ci]` and creates+pushes a matching git tag
3. Builds and pushes `ghcr.io/devops-tashtiot/devops-api:vX.Y.Z` (and `:latest`)
4. Clones `devtools-definition`, `sed`s the new tag into
   `devtools/devops-api/values.yaml`, commits, and pushes to its `main` — **no manual
   version bump in `devtools-definition` is needed or expected; a bot does it
   automatically within ~1 minute of your push.**

Net effect: **a plain `git push` to this repo's `master` is a full release+deploy** — ArgoCD
picks up the `devtools-definition` bump and rolls the new image out on its own. There is no
separate "cut a release" step to remember. To check whether a given push actually shipped:
`gh run list --repo devops-tashtiot/devops-api` (look for a `success` "Build & Publish Docker
Image" run against your commit), then check `devtools-definition`'s git log for the matching
`chore(devops-api): bump image tag to vX.Y.Z` commit.

---

## Writing tests for a service module

Reference implementation: `tests/v1/sonarqube/`. Every service test suite has three files.

**`conftest.py`** — mock the httpx client, build a throw-away FastAPI app with just that router:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.v1.<service>.routes import get_v1_<service>_router

@pytest.fixture
def mock_<service>_client():
    client = MagicMock()
    ok = MagicMock()
    ok.status_code = 200
    ok.text = ""
    client.post = AsyncMock(return_value=ok)   # also mock .put / .delete if used
    return client

@pytest.fixture
def client(mock_<service>_client):
    app = FastAPI()
    app.include_router(get_v1_<service>_router(mock_<service>_client))
    return TestClient(app)
```

**`test_<service>_routes.py`** — assert status codes, call counts, and exact params:

```python
from app.v1.<service>.conf import config
PREFIX = config.API_PREFIX

def test_create_returns_200(client, mock_<service>_client):
    response = client.post(f"{PREFIX}/", json={"name": "check"})
    assert response.status_code == 200
    assert response.json()["status"] == "successful"

def test_create_calls_all_operations(client, mock_<service>_client):
    client.post(f"{PREFIX}/", json={"name": "check"})
    assert mock_<service>_client.post.call_count == <N>   # one per operation
    endpoints = [c.args[0] for c in mock_<service>_client.post.call_args_list]
    assert any("<expected_endpoint>" in ep for ep in endpoints)
```

**`test_<service>_schema.py`** — pydantic validation edge cases: valid names, empty, special chars, length limits.

Rules:
- Never use a real HTTP client in unit tests — always `AsyncMock`
- Assert `call_count` to ensure no operation is silently skipped
- Use `call_args_list` + `c.args[0]` (endpoint) and `c.kwargs["params"]` to verify exact payloads

---

## Verifying an API against a real instance

Read credentials from `.env`, then call each endpoint with curl. Confirm the full operation chain and verify final state.

**SonarQube — create group + assign permissions:**

```bash
# 1. Create group
curl -s -u admin:<pass> -X POST "http://localhost:9000/api/user_groups/create?name=<name>" | python3 -m json.tool

# 2. Assign global admin permission (204 = success)
curl -s -u admin:<pass> -X POST "http://localhost:9000/api/permissions/add_group?groupName=<name>&permission=admin" -w "\nHTTP %{http_code}"

# 3. Assign to Default template (204 = success)
curl -s -u admin:<pass> -X POST "http://localhost:9000/api/permissions/add_group_to_template?groupName=<name>&templateName=Default+template&permission=admin" -w "\nHTTP %{http_code}"

# 4. Verify state
curl -s -u admin:<pass> "http://localhost:9000/api/permissions/groups?permission=admin" | python3 -m json.tool
```

Expected: group appears in the `permissions/groups` response with `"permissions": ["admin"]`.

Local SonarQube: `docker compose -f ../docker-compose.sonarqube.yaml up -d`

---

## README maintenance rule

Every module under `app/v1/` has a `README.md`. **Any time you add, remove, or change an endpoint, a request field, or a config-driven behaviour in a module, you must update that module's `README.md` to reflect the change.** The README must always stay in sync with the actual routes and schemas.

---

## Module CLAUDE.md maintenance rule

Every module under `app/v1/` has a `CLAUDE.md` (e.g. `app/v1/sonarqube/CLAUDE.md`, `app/v1/confluence/CLAUDE.md`). **Any time you make a change to a module — routes, operations, schemas, conf, or any API call details — you must update that module's `CLAUDE.md` to reflect the change.** This includes:

- Adding or removing endpoints → update the Routes table
- Changing request/response fields → update the Schemas section
- Changing the sequence or number of API calls in an operation flow → update the flow description and call counts
- Adding or removing config fields → update the Config fields table
- Discovering quirks about the target service's API (e.g. a non-standard status code, a required header, a known broken endpoint) → add a note in the relevant section

The module `CLAUDE.md` is the authoritative developer reference for that service. It must stay in sync with the actual code at all times.

---

## Prefer live API lookups over hardcoded values

**Never hardcode enumerable values that the target service can return via its own API.** Examples: project roles, permission types, user groups, repository categories. Instead:

1. Add an operation that fetches the list from the service (e.g. `GET /projects/{key}/roles`)
2. Expose it as a `GET` route so callers can discover valid values at runtime
3. Accept the value as a plain `str` (or `list[str]`) in request schemas — do not gate with a Python `Enum`

**Concrete examples:**
- Artifactory project roles — `GET /access/api/v1/projects/{project_key}/roles` returns `[{"name": "Developer"}, ...]`; do NOT define a `ProjectRole` enum, use `list[str]` and expose `GET /permissions/roles/{project_key}`
- Jira project roles — `GET /rest/api/latest/role` returns all global roles with IDs; resolve the admin role by name at call time instead of hardcoding the numeric ID

The rule: if the service has an API for it, fetch it. Only hardcode a value when no such API exists.

---

## Extending existing modules vs. creating new ones

**Bitbucket** and **Confluence** are umbrella modules — any new Bitbucket or Confluence feature goes inside `app/v1/bitbucket/` or `app/v1/confluence/` respectively. Do **not** create a separate module (e.g. `bitbucket_userdirs/`, `confluence_groups/`) for each new operation. Instead:
- Add endpoint fields to the existing `conf.py`
- Add operation functions to `operations.py`
- Add route handlers to `routes.py`
- Add schemas to `schemas.py` if new request/response shapes are needed

Only create a new `app/v1/<service>/` directory for an entirely new external service (e.g. a new platform like SonarQube or Artifactory).

---

## How to add a new API module

Follow these exact steps every time. Use Bitbucket (`app/v1/bitbucket/`) and Confluence (`app/v1/confluence/`) as reference implementations.

### Step 1 — Create `app/v1/<service>/conf.py`

```python
from pydantic_settings import BaseSettings
from pydantic import Field

class <Service>Config(BaseSettings):

    API_PREFIX: str = Field(
        default="/api/devops/v1/<service>",
        description="API prefix for api exposure",
    )

    <SERVICE>_ENDPOINT: str = Field(
        default="/rest/api/latest",         # adjust to the actual base path
        description="API endpoint for <service>",
    )

    API_TAGS: list[str] = Field(
        default=["v1 - <Service> Operations"],
        description="Tags used for OpenAPI documentation grouping.",
    )

config = <Service>Config()
```

Rules:
- Class name: `<Service>Config`
- Always three fields: `API_PREFIX`, `<SERVICE>_ENDPOINT`, `API_TAGS`
- Module-level singleton: `config = <Service>Config()`
- No `model_config` needed here — global `.env` loading lives in `global_conf.py`

---

### Step 2 — Create `app/v1/<service>/schemas.py`

```python
from pydantic import BaseModel, Field

class <Resource>Spec(BaseModel):
    key: str = Field(
        ...,
        description="...",
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_\-]+$",
    )
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1, max_length=1000)
    admin_user: str = Field(
        ...,
        description="user with admin privileges",
        min_length=1,
        max_length=50,
        pattern=r"^[a-z0-9_\-]+$",
    )
    # add other fields as needed (e.g. public: bool = Field(False, ...))
```

Rules:
- One schema per resource (e.g. `ProjectSpec`, `SpaceSpec`)
- Use `Field(...)` (required) or `Field(default, ...)` (optional)
- Always add `min_length`/`max_length` and `pattern` on string fields that go into URLs or payloads

---

### Step 3 — Create `app/v1/<service>/operations.py`

```python
from .schemas import <Resource>Spec
from typing import Any
from .conf import config
from loguru import logger
from fastapi import HTTPException


def _handle_response(response):
    if response.status_code > 299:
        raise HTTPException(status_code=response.status_code, detail=f"errors: {response.text}")


async def create_<resource>(<service>_client: Any, payload: <Resource>Spec):
    key, name, endpoint = payload.key, payload.name, f"{config.<SERVICE>_ENDPOINT}/<resources>"
    try:
        body = {"key": key, "name": name, ...}
        response = await <service>_client.post(endpoint, json=body)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error creating <resource> {key}: {str(e)}")
        raise


async def delete_<resource>(<service>_client: Any, payload: <Resource>Spec):
    key, endpoint = payload.key, f"{config.<SERVICE>_ENDPOINT}/<resources>/{payload.key}"
    try:
        response = await <service>_client.delete(endpoint)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error deleting <resource> {key}: {str(e)}")
        raise


async def assign_admin_permission(<service>_client: Any, payload: <Resource>Spec):
    key, admin_user = payload.key, payload.admin_user
    # Use query params, same pattern as Bitbucket:
    endpoint = f"{config.<SERVICE>_ENDPOINT}/<resources>/{key}/permission?username={admin_user}&permission=ADMIN"
    try:
        response = await <service>_client.put(endpoint)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error assigning admin to <resource> {key}: {str(e)}")
        raise
```

Rules:
- Always define `_handle_response(response)` — raises `HTTPException` on status > 299
- Every function: unpack payload fields at the top, build `endpoint`, wrap body in `try/except`
- Log with `logger.error(...)` and re-raise on unexpected errors
- Never swallow exceptions — the router handles rollback

---

### Step 4 — Create `app/v1/<service>/routes.py`

```python
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.v1.response_schemas import ExceptionResponse, SuccessResponse
from .schemas import <Resource>Spec
from typing import Any
from .conf import config
from .operations import create_<resource>, delete_<resource>, assign_admin_permission


def get_v1_<service>_router(<service>_client: Any):
    router = APIRouter(prefix=config.API_PREFIX, tags=config.API_TAGS)

    @router.post("/", name="create <resource>", status_code=200)
    async def create_new_<resource>(payload: <Resource>Spec) -> JSONResponse:
        try:
            await create_<resource>(<service>_client, payload)
            await assign_admin_permission(<service>_client, payload)
            return SuccessResponse(status="successful")
        except HTTPException as external_error:
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in <Service>. {external_error.detail}",
                    status="Failed",
                    status_code=external_error.status_code,
                ).dict(),
                status_code=external_error.status_code,
            )
        except:
            await delete_<resource>(<service>_client, payload)   # rollback

    return router
```

Rules:
- Router factory name: `get_v1_<service>_router(<service>_client)`
- `prefix` and `tags` always come from `config`
- Create endpoint is always `POST /`
- **Every `POST /` create endpoint must have a matching `DELETE /{identifier}` endpoint** — no create without a delete
- Error handling: catch `HTTPException` → return `ExceptionResponse`; bare `except` → call delete for rollback
- Return `SuccessResponse(status="successful")` on happy path

---

### Step 5 — Wire into `app/global_conf.py`

Add three fields per new service inside `DevopsStaticSettings`:

```python
ENABLE_<SERVICE>_API: bool = Field(
    description="enable or disable <service> api",
    default=True,
)

<SERVICE>_API_URL: str = Field(
    description="<SERVICE> api url",
    default="https://private-<service>.org",
)

<SERVICE>_PASSWORD: str = Field(
    description="<SERVICE> username's password",
    default="sheker",
)

<SERVICE>_USERNAME: str = Field(
    description="<SERVICE> username",
    default="svc-lcl-<service>-api",
)
```

Use `auth=` (basic auth) for services like Bitbucket/Confluence/Jira/SonarQube/Artifactory.
Use `headers={"Authorization": f"Bearer {token}"}` only for genuinely token-based services (e.g. ArgoCD/Git connectors via the internal library).

---

### Step 6 — Wire into `app/main.py`

```python
# 1. Add import at the top
from .v1.<service>.routes import get_v1_<service>_router

# 2. Add inside create_app(), after existing routers
if global_config.ENABLE_<SERVICE>_API:
    <service>_client = BaseAPI(
        global_config.<SERVICE>_API_URL,
        auth=(global_config.<SERVICE>_USERNAME, global_config.<SERVICE>_PASSWORD)
    ).client
    app.include_router(get_v1_<service>_router(<service>_client))
```

---

## Existing modules reference

| Module        | Auth type  | Endpoint base            | Resource  | Operations                              |
|---------------|------------|--------------------------|-----------|------------------------------------------|
| `artifactory` | Basic auth | `/access/api/v1`       | project   | increase storage quota                   |
| `bitbucket`   | Basic auth | `/rest/api/latest`       | project   | create, delete, assign admin; list/sync user dirs |
| `confluence`  | Basic auth | `/rest/api/latest`       | space     | create, delete, assign user/group admin; plugin install/uninstall; space import; list/sync user dirs |
| `jira`        | Basic auth | `/rest/api/latest`       | project   | create (`POST /`), delete (`DELETE /{key}`), assign admin; list/sync user dirs |
| `argocd`      | Git connector | `consumers/` (git path) | consumer config | create (`POST /`), delete (`DELETE /{name}`), get sizes, get include-resources |
| `sonarqube`   | Basic auth | `/api`                   | group     | create (`POST /`), delete (`DELETE /{name}`), global admin + template admin    |

---

## Confluence module — design notes

**Plugin install flow:**
1. User uploads a `.jar` to the MinIO bucket (`http://localhost:9101`)
2. API fetches the JAR via `httpx.AsyncClient` (no credentials — bucket is public-read)
3. API calls `GET /rest/plugins/1.0/?os_authType=basic` to get a fresh `upm-token` from Confluence
4. API uploads the JAR via `POST /rest/plugins/1.0/?token=<upm-token>` as `multipart/form-data`

**Space import flow:**
1. User uploads a `.zip` space export to the MinIO bucket (`http://localhost:9101`)
2. API fetches the archive from S3 and uploads it to `/rest/api/backup-restore/restore/space/upload`
3. API polls `/rest/api/backup-restore/jobs/{id}` until `jobState == "FINISHED"` or timeout

**Key env vars** (in `app/v1/confluence/conf.py`):
- `CONFLUENCE_S3_PLUGINS_BASE_URL` — bucket URL for plugins (default: `http://localhost:9100/platform-clients/confluence-plugins`)
- `CONFLUENCE_S3_IMPORTS_BASE_URL` — bucket URL for space archives (default: `http://localhost:9100/platform-clients/confluence-space-imports`)
- `CONFLUENCE_UPM_ENDPOINT` — UPM base path (default: `/rest/plugins/1.0`)
- `CONFLUENCE_JOB_POLL_INTERVAL` / `CONFLUENCE_JOB_MAX_POLLS` — restore job polling config

**Confluence prerequisite — allow plugin uploads:**
Admin → Add-ons / Manage apps → Settings → uncheck "Prevent users from installing add-ons"

**UPM plugin key convention:**
DELETE takes the OSGi key (e.g. `com.example.my-plugin`). UPM appends `-key` internally. The route uses `{plugin_key:path}` to handle dotted keys correctly.

**MinIO setup:** `docker compose -f docker-compose.minio.yaml up -d` (S3 API on port 9100, console on 9101).

---

## Confluence 9.3.1 REST API — known working endpoints

The standard `POST /rest/api/latest/space/{key}/permission` (singular) **returns 404 and does not work** in Confluence 9.3.1. Use the endpoints below instead.

### Space permission grant (user)

```
# Step 1 — resolve username to userKey
GET /rest/api/latest/user?username={username}
→ response body contains "userKey"

# Step 2 — grant read first (required by Confluence before any other permission)
PUT /rest/api/latest/space/{spaceKey}/permissions/user/{userKey}/grant
Body: [{"operationKey": "read", "targetType": "space"}]
→ 204

# Step 3 — grant administer
PUT /rest/api/latest/space/{spaceKey}/permissions/user/{userKey}/grant
Body: [{"operationKey": "administer", "targetType": "space"}]
→ 204
```

### Space permission grant (group)

Same body format; same read-before-administer requirement:

```
PUT /rest/api/latest/space/{spaceKey}/permissions/group/{groupName}/grant
Body: [{"operationKey": "read", "targetType": "space"}]
→ 204

PUT /rest/api/latest/space/{spaceKey}/permissions/group/{groupName}/grant
Body: [{"operationKey": "administer", "targetType": "space"}]
→ 204
```

### Read all space permissions

```
GET /rest/api/latest/space/{spaceKey}/permissions
→ 200, array of {operation: {operationKey, targetType}, subject: {type, userKey|name}, spaceKey}
```

### Create a user (admin API)

```
POST /rest/api/latest/admin/user
Body: {"userName": "...", "password": "...", "email": "...", "fullName": "..."}
→ 200, body contains "userKey"
```
Note: fields are `userName` (not `username`) and `fullName` (not `displayName`).

### Create a group (admin API)

```
POST /rest/api/latest/admin/group
Body: {"type": "group", "name": "..."}
→ 201
```
Note: the `"type": "group"` field is required — omitting it causes a 400.

---

## Schema pattern — mutually exclusive optional fields

When a resource can be administered by either a user OR a group (but not both), use this pattern in `schemas.py`:

```python
from pydantic import BaseModel, Field, model_validator
from typing import Optional

class ResourceSpec(BaseModel):
    # ... other fields ...

    admin_user: Optional[str] = Field(
        default=None,
        description="Username to receive ADMIN permission",
        min_length=1, max_length=50, pattern=r"^[a-z0-9_\-]+$",
    )
    admin_group: Optional[str] = Field(
        default=None,
        description="Group name to receive ADMIN permission",
        min_length=1, max_length=255, pattern=r"^[a-z0-9_\-]+$",
    )

    @model_validator(mode="after")
    def require_exactly_one_admin(self) -> "ResourceSpec":
        if not self.admin_user and not self.admin_group:
            raise ValueError("Provide either admin_user or admin_group")
        if self.admin_user and self.admin_group:
            raise ValueError("Provide only one of admin_user or admin_group, not both")
        return self
```

In `routes.py`, branch on which field is set:
```python
if payload.admin_user:
    await assign_space_admin(client, payload)
else:
    await assign_space_group_admin(client, payload)
```

## Response schemas (`app/v1/response_schemas.py`)

- `SuccessResponse(status="successful")` — returned on happy path
- `ExceptionResponse(stdout=..., status="Failed", status_code=...)` — returned inside `JSONResponse` on `HTTPException`
