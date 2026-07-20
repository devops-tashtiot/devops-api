# Artifactory module — developer notes

## How the client is built

`main.py` constructs a single `BaseAPI` client with basic auth from `global_config` (same pattern as Bitbucket/Confluence/Jira/SonarQube):

```
BaseAPI(global_config.ARTIFACTORY_API_URL, auth=(global_config.ARTIFACTORY_USERNAME, global_config.ARTIFACTORY_PASSWORD)).client
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

Global credentials (`ARTIFACTORY_USERNAME`, `ARTIFACTORY_PASSWORD`), URL (`ARTIFACTORY_API_URL`), LDAP setting name (`ARTIFACTORY_LDAP_SETTING_NAME`), and `ARTIFACTORY_S3_XRAY_UPDATES_BASE_URL` live in `global_conf.py`.

## Live-check findings (2026-07-14)

Followed the same "check all APIs live against the cluster" procedure used for
Bitbucket/Jira/SonarQube/ArgoCD. All 6 routes currently fail live, for two distinct,
compounding reasons — neither is a bug in this module's request/response handling itself.

### 1. `ARTIFACTORY_USERNAME`/`ARTIFACTORY_PASSWORD` are still the dev placeholder defaults

`app/global_conf.py` defaults these to `svc-lcl-artifactory-api` / `sheker` (Hebrew for "lie" —
clearly a dev-only placeholder). Unlike every other tool's credentials in
`devtools-definition/devtools/devops-api/values.yaml` (which overrides `BITBUCKET_*`,
`JIRA_*`, etc. with real values), **`ARTIFACTORY_USERNAME`/`ARTIFACTORY_PASSWORD` are never
overridden there at all** — confirmed via `grep`, no match. The live deployment is
authenticating against the real Artifactory with fake credentials. Every route that calls
Artifactory returns `401` with `"Exception in Artifactory. HTTP 401 Unauthorized"`.

### 2. Even with real credentials, Artifactory's Access API rejects Basic auth entirely

This is the deeper, more important finding — fixing (1) alone will not make this module work.
Confirmed live, `kubectl exec`-ing directly into `artifactory-0` and calling `localhost:8082`
(bypassing all routing/Cloudflare/TLS, using the real admin password from
`/devtools/admin/password`):

```
GET  http://localhost:8082/artifactory/api/repositories        (classic API) → 200, real data
GET  http://localhost:8082/access/api/v1/projects/{key}        (Access API)  → 401 Unsupported authentication method Basic
POST http://localhost:8082/access/api/v1/tokens                (Access API)  → 401 Unsupported authentication method Basic
```

**Basic auth works on the classic `/artifactory/api/*` REST API but is rejected outright on
every `/access/api/v1/*` endpoint** — including the token-minting endpoint itself, so there is
no way to bootstrap a Bearer token via Basic auth against this specific deployment either. This
module's entire design (`main.py` builds one `BaseAPI` client with `auth=(username, password)`,
same pattern as Bitbucket/Confluence/Jira/SonarQube) assumes Basic auth works against
`ARTIFACTORY_ENDPOINT` (`/access/api/v1`) — that assumption is wrong for this Artifactory
instance/version, independent of which credentials are used.

**Not yet resolved — needs a real design decision, not just a config fix:**
- Real fix likely requires switching this module to Bearer-token auth against the Access API —
  e.g. a long-lived Identity Token generated once through Artifactory's own Admin UI (User
  Profile → Generate Identity Token), stored in SSM the same way other secrets are, with
  `operations.py`'s `_handle_response`/client construction changed to send
  `Authorization: Bearer <token>` instead of Basic auth for this module specifically. Whether
  Artifactory has a platform-level toggle to re-enable Basic auth on the Access API instead
  (some JFrog Platform versions expose this under Administration → Access Tokens) has not been
  checked — worth investigating as a possibly simpler alternative before committing to a token
  rework.
- The `ARTIFACTORY_USERNAME`/`ARTIFACTORY_PASSWORD` placeholder-credentials gap in
  `devtools-definition` should be fixed regardless (real credentials, wired the same way as the
  other tools) — necessary either way, just not sufficient on its own until (2) is also
  resolved.

## Testing

Tests mock the injected `artifactory_client` via `MagicMock` / `AsyncMock`.  
`conftest.py` builds a throw-away `FastAPI` app with just the Artifactory router.  
`POST /` triggers up to 3 calls: create (`post`) + user assign (`put`) + group assign (`put`).  
`POST /storage-quota` triggers 2 calls: get current quota (`get`) + update (`put`).  
`POST /xray/vulnerability-update` mocks `httpx.AsyncClient` (S3 fetch) via `unittest.mock.patch` and asserts 1 `post` call to the Xray endpoint.
