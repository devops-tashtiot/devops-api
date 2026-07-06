# Artifactory module — developer notes

## How the client is built

`main.py` constructs a single `BaseAPI` client with a Bearer token header from `global_config`:

```
BaseAPI(global_config.ARTIFACTORY_API_URL, headers={"Authorization": f"Bearer {global_config.ARTIFACTORY_API_TOKEN}"}).client
```

Passed into `get_v1_artifactory_router(artifactory_client)` at startup — no per-request reconstruction.

## Routes

| Method | Path | Operation |
|--------|------|-----------|
| `POST` | `/` | Create project + assign admin (user and/or group) |
| `POST` | `/storage-quota` | Increase project storage quota |
| `GET` | `/permissions/roles/{role_name}` | Get a global role definition |
| `POST` | `/permissions` | Grant a role to a user or group on a project |
| `GET` | `/permissions/{project_key}` | Get all users and groups with roles on a project |
| `POST` | `/xray/vulnerability-update` | Upload air-gapped Xray vulnerability DB update from S3 |

## Project create flow (POST /)

```
create_project
  → assign_admin_user   [if admin_user set]
  → assign_admin_group  [if admin_group set]
```

At least one of `admin_user` / `admin_group` must be provided.

On unexpected failure: rollback via `delete_project(project_key)`.

**Key derived:** `project_key = name.lower().replace(" ", "-").replace("_", "-")` — computed by `ProjectSpec.project_key` property.

## Artifactory REST API calls

### Create project — `POST /access/api/v1/projects`

```
POST /access/api/v1/projects
Body: {"display_name": name, "project_key": project_key, "storage_quota_bytes": bytes}
→ 201
```

Storage quota is converted from GB: `gb * 1024³`.

### Delete project — `DELETE /access/api/v1/projects/{project_key}`

```
DELETE /access/api/v1/projects/{project_key}
→ 204
```

### Assign admin user — `PUT /access/api/v1/projects/{key}/users/{username}`

```
PUT /access/api/v1/projects/{key}/users/{username}
Body: {"name": username, "roles": ["PROJECT_ADMIN"], "ignore_missing_user": false}
→ 200/204
```

### Assign admin group — `PUT /access/api/v1/projects/{key}/groups/{groupname}`

```
PUT /access/api/v1/projects/{key}/groups/{groupname}
Body: {"name": groupname, "roles": ["PROJECT_ADMIN"]}
→ 200/204
```

### Increase storage quota — `PUT /access/api/v1/projects/{key}`

```
GET  /access/api/v1/projects/{key}        → current storage_quota_bytes
PUT  /access/api/v1/projects/{key}
Body: {"storage_quota_bytes": current + new_bytes}
→ 200
```

### Assign project member (any role) — `POST /permissions`

Handles both users and groups. If the member is a group and it does not exist in the JFrog Platform Deployment (JPD), it is imported from LDAP first:

```
GET  /access/api/v1/groups/{group_name}           → check existence
POST /access/api/v1/ldap/groups/sync
     Body: {"ldap_setting_name": ARTIFACTORY_LDAP_SETTING_NAME, "groups": [group_name]}

PUT  /access/api/v1/projects/{project_key}/groups/{member_name}
     Body: {"name": member_name, "roles": [...roles]}
```

For users:
```
PUT  /access/api/v1/projects/{project_key}/users/{member_name}
     Body: {"name": member_name, "roles": [...roles], "ignore_missing_user": false}
```

### Get global role — `GET /permissions/roles/{role_name}`

```
GET /access/api/v1/roles/{role_name}
→ 200, role definition JSON
```

### Get project permissions — `GET /permissions/{project_key}`

```
GET /access/api/v1/projects/{project_key}/users   → users
GET /access/api/v1/projects/{project_key}/groups  → groups
→ {"users": [...], "groups": [...]}
```

### Xray air-gapped vulnerability update — `POST /xray/vulnerability-update`

Flow:
1. Fetch the update archive from MinIO (`ARTIFACTORY_S3_XRAY_UPDATES_BASE_URL/{file_name}`) via anonymous `httpx.AsyncClient` — bucket: `platform-devops-team`, subfolder: `xray-vulnerability-updates/`
2. POST it to Xray as `multipart/form-data`:

```
POST /xray/api/v1/system/offline_updates
files={"file": (file_name, file_bytes, "application/octet-stream")}
→ 200
```

The archive must be pre-uploaded to the `platform-devops-team/xray-vulnerability-updates/` subfolder in MinIO before calling this endpoint.

## Schemas

### `ProjectSpec`

| Field | Type | Constraints |
|---|---|---|
| `name` | `str` | required; `^[a-zA-Z0-9][a-zA-Z0-9 _\-]+$`; 2–32 chars |
| `storage_quota_giga_bytes` | `int` | required; 1–10 GB |
| `admin_user` | `Optional[str]` | `^[a-z0-9_\-]+$`; max 50 chars |
| `admin_group` | `Optional[str]` | `^[a-zA-Z0-9_\-]+$`; max 255 chars |

### `StorageQuotaBytes`

| Field | Type | Constraints |
|---|---|---|
| `name` | `str` | project key |
| `storage_quota_giga_bytes` | `int` | 1–10 GB; additive (added to current quota) |

### `ProjectPermissionSpec`

| Field | Type | Constraints |
|---|---|---|
| `project_key` | `str` | `^[a-z0-9\-]+$`; 2–32 chars |
| `member_name` | `str` | username or group name |
| `member_type` | `MemberType` | `"user"` or `"group"` |
| `roles` | `list[str]` | non-empty; use `GET /permissions/roles/{name}` to discover valid values |

### `XrayVulnUpdateSpec`

| Field | Type | Constraints |
|---|---|---|
| `file_name` | `str` | required; `^[a-zA-Z0-9_\-\.]+$`; 1–255 chars; archive must exist in `platform-devops-team/xray-vulnerability-updates/` in MinIO |

## Config fields (`conf.py`)

| Field | Default | Description |
|---|---|---|
| `ARTIFACTORY_ENDPOINT` | `/access/api/v1` | Artifactory Access REST API base path |
| `ARTIFACTORY_XRAY_ENDPOINT` | `/xray/api/v1` | Xray REST API base path |

Global token (`ARTIFACTORY_API_TOKEN`), URL (`ARTIFACTORY_API_URL`), LDAP setting name (`ARTIFACTORY_LDAP_SETTING_NAME`), and `ARTIFACTORY_S3_XRAY_UPDATES_BASE_URL` live in `global_conf.py`.

## Local dev

```bash
docker compose -f ../docker-compose.artifactory.yaml up -d
# Set ARTIFACTORY_API_URL and ARTIFACTORY_API_TOKEN in .env
```

## Testing

Tests mock the injected `artifactory_client` via `MagicMock` / `AsyncMock`.  
`conftest.py` builds a throw-away `FastAPI` app with just the Artifactory router.  
`POST /` triggers up to 3 calls: create (`post`) + user assign (`put`) + group assign (`put`).  
`POST /storage-quota` triggers 2 calls: get current quota (`get`) + update (`put`).  
`POST /xray/vulnerability-update` mocks `httpx.AsyncClient` (S3 fetch) via `unittest.mock.patch` and asserts 1 `post` call to the Xray endpoint.
