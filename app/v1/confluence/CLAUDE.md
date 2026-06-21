# Confluence module — developer notes

## How the client is built

`main.py` constructs a single `BaseAPI` client with basic auth from `global_config`:

```
BaseAPI(global_config.CONFLUENCE_API_URL, auth=(global_config.CONFLUENCE_USERNAME, global_config.CONFLUENCE_PASSWORD)).client
```

Passed into `get_v1_confluence_router(confluence_client)` at startup — no per-request reconstruction.

## Routes

| Method | Path | Operation |
|--------|------|-----------|
| `POST` | `/` | Create space + assign admin (user and/or group) |
| `DELETE` | `/{key}` | Delete space |
| `POST` | `/plugin/` | Install plugin from S3 via UPM |
| `DELETE` | `/plugin/{plugin_key:path}` | Uninstall plugin by OSGi key |
| `GET` | `/user-dirs` | List Crowd user directories |
| `POST` | `/user-dirs/sync` | Sync the single Crowd user directory (ID auto-discovered) |
| `POST` | `/space-export/` | Export space to S3 |
| `POST` | `/space-import/` | Import space from S3 |

## Space create flow (POST /)

```
create_space
  → assign_space_admin (user)     [if admin_user set]
  → assign_space_group_admin (group)  [if admin_group set]
```

`admin_user` and `admin_group` are mutually non-exclusive — at least one must be provided. Both can be provided.

### Space permission calls (known working on Confluence 9.3.1)

`POST /rest/api/latest/space/{key}/permission` (singular) returns 404 — do **not** use it.

**User admin (3 calls):**
```
GET  /rest/api/latest/user?username={admin_user}          → resolve userKey
PUT  /rest/api/latest/space/{key}/permissions/user/{userKey}/grant   body: [{"operationKey":"read","targetType":"space"}]
PUT  /rest/api/latest/space/{key}/permissions/user/{userKey}/grant   body: [{"operationKey":"administer","targetType":"space"}]
```

**Group admin (2 calls):**
```
PUT  /rest/api/latest/space/{key}/permissions/group/{admin_group}/grant  body: [{"operationKey":"read","targetType":"space"}]
PUT  /rest/api/latest/space/{key}/permissions/group/{admin_group}/grant  body: [{"operationKey":"administer","targetType":"space"}]
```

`read` must be granted before `administer` — Confluence requires it.

## Plugin install flow (POST /plugin/)

1. Fetch `.jar` from the public `platform-clients` MinIO bucket via anonymous `httpx.AsyncClient` (`CONFLUENCE_S3_PLUGINS_BASE_URL/{plugin_name}`, subfolder `confluence-plugins/`)
2. `GET /rest/plugins/1.0/?os_authType=basic` → extract `upm-token` response header
3. `POST /rest/plugins/1.0/?token={upm_token}` with `multipart/form-data` containing the JAR

**Uninstall:** `DELETE /rest/plugins/1.0/{plugin_key}-key` (UPM appends `-key` suffix internally; route uses `{plugin_key:path}` to handle dotted keys like `com.example.my-plugin`).

**Confluence prerequisite:** Admin → Add-ons → Settings → uncheck "Prevent users from installing add-ons".

## Space export flow (POST /space-export/)

```
POST /rest/api/backup-restore/backup/space  body: {"spaceKeys": [space_key]}
  → returns {id, fileName}
poll GET /rest/api/backup-restore/jobs/{id}  until jobState == "FINISHED"
GET  /rest/api/backup-restore/jobs/{id}/download  → archive bytes
PUT  CONFLUENCE_S3_IMPORTS_BASE_URL/{fileName}  → upload to MinIO (platform-clients/confluence-space-imports/)
```

Returns `{"status": "successful", "archive_name": fileName}`.

## Space import flow (POST /space-import/)

```
GET  CONFLUENCE_S3_IMPORTS_BASE_URL/{archive_name}  → fetch archive bytes from MinIO (platform-clients/confluence-space-imports/)
POST /rest/api/backup-restore/restore/space/upload  (multipart, X-Atlassian-Token: no-check)
  → returns {id}
poll GET /rest/api/backup-restore/jobs/{id}  until jobState == "FINISHED"

`space_key` is not in the schema — Confluence restores the space key directly from the archive and provides no way to override it.
```

## User directories (Crowd REST API)

```
GET  /rest/crowd/latest/directory               → list all directories (auto-selects first)
POST /rest/crowd/latest/directory/{id}/synchronise  → trigger sync (id taken from list response)
```

## Config fields (`conf.py`)

| Field | Default | Description |
|---|---|---|
| `CONFLUENCE_ENDPOINT` | `/rest/api/latest` | Main REST API base path |
| `CONFLUENCE_UPM_ENDPOINT` | `/rest/plugins/1.0` | UPM (plugin manager) base path |
| `CONFLUENCE_CROWD_ENDPOINT` | `/rest/crowd/latest` | Crowd user directory API |
| `CONFLUENCE_BACKUP_RESTORE_ENDPOINT` | `/rest/api/backup-restore` | Backup/restore API |
| `CONFLUENCE_JOB_POLL_INTERVAL` | `2.0` | Seconds between restore/export job status polls |
| `CONFLUENCE_JOB_MAX_POLLS` | `60` | Max poll attempts before timeout (→ 504) |

Global credentials (`CONFLUENCE_USERNAME`, `CONFLUENCE_PASSWORD`) and `CONFLUENCE_API_URL` live in `global_conf.py`.  
S3 bucket URLs (`CONFLUENCE_S3_PLUGINS_BASE_URL`, `CONFLUENCE_S3_IMPORTS_BASE_URL`) also live in `global_conf.py`. Both point into the public **`platform-clients`** bucket (`confluence-plugins/` and `confluence-space-imports/` subfolders).

## Local dev

```bash
docker compose -f ../docker-compose.confluence.yaml up -d
# Confluence at http://localhost:8090  user: admin  pass: 12345678
```

Set in `.env`:
```
CONFLUENCE_API_URL=http://localhost:8090
CONFLUENCE_USERNAME=admin
CONFLUENCE_PASSWORD=12345678
```

MinIO (for plugins and space archives):
```bash
docker compose -f ../docker-compose.minio.yaml up -d
# S3 API: http://localhost:9100   Console: http://localhost:9101
```

## Testing

Tests mock the injected `confluence_client` via `MagicMock` / `AsyncMock` — no real HTTP calls.  
`conftest.py` builds a throw-away `FastAPI` app with just the Confluence router.  
Space-permission tests must account for the multi-call sequence (`get` for userKey lookup + two `put` calls per permission type).
