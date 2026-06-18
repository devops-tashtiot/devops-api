# SonarQube module — developer notes

## How the client is built

Unlike other modules that share a single pre-built httpx client, `routes.py:_build_client()` constructs a fresh client **per request** from the `consumer_name` field in the payload:

```
{SONARQUBE_SCHEME}://{consumer_name}.sonarqube.{DOMAIN_SUFFIX}[:{SONARQUBE_PORT}]
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

Tests mock `BaseAPI` via an autouse fixture in `conftest.py` — `patch_base_api` patches `app.v1.sonarqube.routes.BaseAPI` so `_build_client()` returns the shared mock without making real HTTP calls.
