# Jira module — developer notes

## How the client is built

`main.py` constructs a single `BaseAPI` client with basic auth from `global_config`:

```
BaseAPI(global_config.JIRA_API_URL, auth=(global_config.JIRA_USERNAME, global_config.JIRA_PASSWORD)).client
```

Passed into `get_v1_jira_router(jira_client)` at startup — no per-request reconstruction.

## Routes

| Method | Path | Operation |
|--------|------|-----------|
| `POST` | `/` | Create project + assign admin (user and/or group) |
| `DELETE` | `/{project_key}` | Delete project |
| `GET` | `/user-dirs` | List user directories |
| `POST` | `/user-dirs/{directory_id}/sync` | Sync a user directory |

## Project create flow (POST /)

```
create_project  (sets lead=admin_user when admin_user is provided)
  → assign_project_admin_user  [if admin_user set]
  → assign_project_admin_group [if admin_group set]
```

`admin_user` and `admin_group` are mutually non-exclusive — at least one must be provided.

On unexpected failure: rollback via `delete_project`.

## Jira REST API calls

### Create project — `POST /rest/api/latest/project`

```
POST /rest/api/latest/project
Body: {"key": key, "name": name, "description": description, "projectTypeKey": "software"[, "lead": admin_user]}
→ 201
```

### Delete project — `DELETE /rest/api/latest/project/{key}`

```
DELETE /rest/api/latest/project/{key}
→ 204
```

### Assign admin user — `POST /rest/api/latest/project/{key}/role/10002`

```
POST /rest/api/latest/project/{key}/role/10002
Body: {"user": [admin_user]}
→ 200
```

Role ID `10002` is the Jira built-in "Administrators" role. The ID is hardcoded because Jira does not expose a stable name-to-ID lookup that avoids this value on fresh instances.

### Assign admin group — `POST /rest/api/latest/project/{key}/role/10002`

```
POST /rest/api/latest/project/{key}/role/10002
Body: {"group": [admin_group]}
→ 200
```

### List user directories — `GET /rest/api/latest/admin/user-dirs`

```
GET /rest/api/latest/admin/user-dirs
→ 200, JSON array of directory objects
```

### Sync user directory — `POST /rest/api/latest/admin/user-dirs/{id}/sync`

```
POST /rest/api/latest/admin/user-dirs/{id}/sync
→ 200/204
```

## Schema — `ProjectSpec`

| Field | Type | Constraints |
|---|---|---|
| `key` | `str` | required; `^[A-Z][A-Z0-9]+$`; max 10 chars |
| `name` | `str` | required; max 255 chars |
| `description` | `str` | required; max 1000 chars |
| `admin_user` | `Optional[str]` | `^[a-z0-9_\-]+$`; max 50 chars |
| `admin_group` | `Optional[str]` | `^[a-zA-Z0-9_\-]+$`; max 255 chars |

Model validator: at least one of `admin_user` / `admin_group` must be provided.

## Config fields (`conf.py`)

| Field | Default | Description |
|---|---|---|
| `JIRA_ENDPOINT` | `/rest/api/latest` | Jira REST API base path |

Global credentials (`JIRA_USERNAME`, `JIRA_PASSWORD`) and `JIRA_API_URL` live in `global_conf.py`.

## Local dev

```bash
# No dedicated compose file — use an existing Jira Data Center or Server instance
# Set in .env:
JIRA_API_URL=http://localhost:8080
JIRA_USERNAME=admin
JIRA_PASSWORD=<password>
```

## Testing

Tests mock the injected `jira_client` via `MagicMock` / `AsyncMock`.  
`conftest.py` builds a throw-away `FastAPI` app with just the Jira router.  
`POST /` triggers up to 3 calls: create + admin-user assign + admin-group assign.
