# SonarQube module — developer notes

## How the client is built

Unlike other modules that share a single pre-built httpx client, `routes.py:_build_client()` constructs a fresh client **per request** from the `consumer_name` field in the payload:

```
https://{consumer_name}.sonarqube.{DOMAIN_SUFFIX}
```

Auth always uses the global credentials from `.env` (`SONARQUBE_USERNAME` / `SONARQUBE_PASSWORD`).  
`main.py` therefore calls `get_v1_sonarqube_router()` with no arguments.

## SonarQube REST API calls

### Create group — `POST /api/user_groups/create`

```
POST /api/user_groups/create?name={name}
→ 200, JSON body with group details
```

### Delete group — `POST /api/user_groups/delete`

```
POST /api/user_groups/delete?name={name}
→ 204
```

Note: SonarQube uses `POST` for delete, not `DELETE`.

### Assign global permissions — `POST /api/permissions/add_group`

Called once per permission in `SONARQUBE_GLOBAL_PERMISSIONS`:

```
POST /api/permissions/add_group?groupName={name}&permission={permission}
→ 204
```

Default permissions granted: `admin`, `gateadmin`, `profileadmin`, `provisioning`, `scan`.

### Assign template permissions — `POST /api/permissions/add_group_to_template`

Called once per permission in `SONARQUBE_TEMPLATE_PERMISSIONS`:

```
POST /api/permissions/add_group_to_template?groupName={name}&templateName={template}&permission={permission}
→ 204
```

Default template: `Default template` (set via `SONARQUBE_ADMIN_TEMPLATE_NAME`).  
Default permissions granted: `user`, `codeviewer`, `issueadmin`, `securityhotspotadmin`, `admin`, `scan`.

## Create flow (POST /)

```
create_group → assign_global_permissions (×5) → assign_template_permissions (×6)
```

Total: **12 POST calls** to SonarQube per group creation.  
On any failure: automatic rollback via `delete_group`.

## Sizes — `GET /sizes`

Returns the allowed `size` enum values for consumer configs, sourced live from
`SONARQUBE_ALLOWED_SIZES` (`global_conf.py`): `["default", "medium", "big"]`. Confirmed live —
`GET /api/devops/v1/sonarqube/sizes` returns `200 ["default","medium","big"]`. No external calls.

## Consumer config (GitOps) — `POST/PUT/DELETE /consumer/*`

Each of these writes/updates/deletes `consumers/{name}/config.yaml` in a dedicated Bitbucket
repo via the injected `Git` connector (see `operations.py`: `create_sonarqube_consumer`,
`update_sonarqube_consumer`, `delete_sonarqube_consumer`). Unlike the group routes, `main.py`
constructs this `Git` client once at startup (`GIT_PROJECT_KEY` / `SONARQUBE_AAS_REPO_SLUG` /
`SONARQUBE_GITOPS_DEFAULT_BRANCH`), not per-request.

| Route | Git call | Path |
|---|---|---|
| `POST /consumer/` | `git.add_file` | `consumers/{name}/config.yaml` |
| `PUT /consumer/{name}` | `git.update_file` | `consumers/{name}/config.yaml` |
| `DELETE /consumer/{name}` | `git.delete_file` | `consumers/{name}/config.yaml` |

`config.yaml` always includes `name`; `plugins_list` (comma-joined) and `size` are only written
when non-default (`size` omits the key entirely when `default`).

### Fixed bug — `DELETE /consumer/{name}` was unreachable (route-shadowing)

`DELETE /{consumer_name}/{name}` (group delete) and `DELETE /consumer/{name}` (consumer-config
delete) are both two-segment paths under the same HTTP method. FastAPI/Starlette matches routes
in **registration order**, and the group-delete route was registered first — so every call to
`DELETE /consumer/{name}` was actually being routed to group-delete with
`consumer_name="consumer"`, silently trying to delete a SonarQube group on a tenant literally
named `consumer` instead of deleting the GitOps config file. Caught via a unit test asserting
`mock_git.delete_file` was called and finding it never was. **Fixed** by registering the
`/consumer/*` routes before the generic `/{consumer_name}/{name}` wildcard in `routes.py`.

**Residual constraint**: a real SonarQube tenant/consumer literally named `consumer` still can't
have its group deleted via `DELETE /{consumer_name}/{name}` — that request will always match
`DELETE /consumer/{name}` (consumer-config delete) instead, since the literal segment wins.
Considered out of scope to redesign the URL scheme for; treat `consumer` as a reserved
`consumer_name`.

### Live environment note — GitOps repo did not exist

Live-checked directly against the real Bitbucket instance (2026-07-13): the configured
`GIT_PROJECT_KEY` (`ARGO`) and `SONARQUBE_AAS_REPO_SLUG` (`sonarqube-as-a-service`) repo did
**not** exist yet — only Bitbucket project `NATI` existed, and no repo named
`sonarqube-as-a-service` existed anywhere. This meant all three consumer routes were previously
non-functional against the real cluster (not a code bug — the GitOps prerequisite was simply
never provisioned). `tests/v1/sonarqube/test_sonarqube_consumer_e2e.py`'s module-scoped setup
fixture now creates the project/repo idempotently if missing (and leaves them in place — they
are shared platform infrastructure, not disposable test fixtures) as a side effect of adding e2e
coverage.

## Config fields (`conf.py`)

| Field | Default | Description |
|---|---|---|
| `SONARQUBE_ENDPOINT` | `/api` | SonarQube Web API base path |
| `SONARQUBE_SCHEME` | `https` | URL scheme (`http` for local dev) |
| `SONARQUBE_PORT` | `""` | Port (empty = scheme default; `9000` for local dev) |
| `SONARQUBE_ADMIN_TEMPLATE_NAME` | `Default template` | Permission template name |
| `SONARQUBE_GLOBAL_PERMISSIONS` | see above | Overridable via `.env` |
| `SONARQUBE_TEMPLATE_PERMISSIONS` | see above | Overridable via `.env` |

Global credentials (`SONARQUBE_USERNAME`, `SONARQUBE_PASSWORD`) and `DOMAIN_SUFFIX` live in `global_conf.py`.

## Local dev

```bash
docker compose -f ../docker-compose.sonarqube.yaml up -d
# SonarQube at http://localhost:9000  user: admin  pass: SonarqubeDevops1!
```

Set in `.env`:
```
SONARQUBE_SCHEME=http
SONARQUBE_PORT=9000
```

## Testing

Tests mock `BaseAPI` via an autouse fixture in `conftest.py` — `patch_base_api` patches `app.v1.sonarqube.routes.BaseAPI` so `_build_client()` returns the shared mock without making real HTTP calls. `mock_git` (also in `conftest.py`) covers the consumer-config routes the same way.

- `test_sonarqube_routes.py` — unit tests (mocked) for all 6 routes: group create/delete, `GET /sizes`, `POST/PUT/DELETE /consumer/*`.
- `test_sonarqube_schema.py` — pydantic validation edge cases.
- `test_sonarqube_group_e2e.py` — real e2e: group create/delete against a live SonarQube instance.
- `test_sonarqube_consumer_e2e.py` — real e2e: consumer config create/update/delete against a live Bitbucket GitOps repo, plus `GET /sizes`. Its module-scoped setup fixture creates the `ARGO` project / `sonarqube-as-a-service` repo if missing (see "Live environment note" above) and never tears them down.
