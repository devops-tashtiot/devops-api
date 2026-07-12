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

## Delete space — asynchronous, `delete_space` polls until confirmed

`DELETE /rest/api/space/{key}` returns 2xx as soon as Confluence **accepts** the deletion, not
once the space is actually removed — confirmed live: `GET /space/{key}` immediately after a
"successful" delete still returned the full space (`200`), and only started 404ing ~20-30s
later. `delete_space` now polls `GET /space/{key}` (reusing `CONFLUENCE_JOB_POLL_INTERVAL`/
`CONFLUENCE_JOB_MAX_POLLS`, same as the export/import job-polling below) until it 404s before
reporting success, raising `504` if it never confirms within the timeout. Without this, a
caller that immediately tries to recreate a space with the same key right after a "successful"
delete could race the background job.

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
4. Poll the returned task URL until the install genuinely finishes (see below) — do not report
   success straight off step 3's response.

**UPM install is asynchronous — confirmed live.** Step 3's response is `202`, not a completed
result: `{"status":{"done":false,...},"links":{"self":"/rest/plugins/1.0/pending/{taskId}"}}`.
Reporting success right after step 3 (the old behavior) is dishonest — a caller that checks
whether the plugin exists immediately afterward can get a `404` because the OSGi bundle
genuinely hasn't finished registering, even though devops-api already said `"successful"`.
`install_plugin` now polls `GET` on the task's `links.self` (reusing `CONFLUENCE_JOB_POLL_INTERVAL`/
`CONFLUENCE_JOB_MAX_POLLS`) until `status.done` is `true`, raising `422` if
`status.contentType` contains `"err"` (a genuine install failure, with `status.errorMessage`
as the detail — confirmed live: a corrupt/invalid jar produces exactly this), or `504` if it
never finishes within the timeout.

**Response body quirk:** the install POST's response is HTML-wrapped —
`<textarea>{...json...}</textarea>` — a long-standing UPM browser-compat quirk for
multipart-upload responses (avoids the browser offering a file-download dialog for a JSON
response). The task-polling `GET` response is plain JSON with no such wrapper. Both are
parsed by the same `_parse_upm_task_response` helper, which strips the wrapper only if
present.

**Uninstall:** `DELETE /rest/plugins/1.0/{plugin_key}-key` (UPM appends `-key` suffix internally; route uses `{plugin_key:path}` to handle dotted keys like `com.example.my-plugin`).

**Confluence prerequisite:** plugin upload is disabled by default in Confluence Data Center
(confirmed live: 403s "Plugins cannot be installed via upload" otherwise) — this platform
keeps it enabled permanently via `-Dupm.plugin.upload.enabled=true`
(`devtools-definition/devtools/confluence/values.yaml`, `confluence.confluence.additionalJvmArgs`),
a deliberate choice since devops-api's plugin install flow depends on it. The older
"Admin → Add-ons → Settings → uncheck 'Prevent users from installing add-ons'" UI toggle is a
separate, additional gate some Confluence versions also enforce — check both if install still
403s.

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
GET  /rest/crowd/latest/directory   → list all directories, unwrapped from {"directory": [...]}
```

`sync_user_directory` always raises `501` — **Confluence has no supported way to trigger a
directory sync on demand**. Confirmed live: `POST /rest/crowd/latest/directory/{id}/
synchronise` 404s even against a real AD-connector directory ID. This is the identical root
cause documented in detail in `app/v1/bitbucket/CLAUDE.md` (same underlying Atlassian
Crowd-embedded module, same missing REST trigger) — see that file for the full investigation,
including why the undocumented web-UI servlet alternative that exists on Bitbucket isn't
usable either (its response can't distinguish a real sync from a silent no-op). Directories
sync on Confluence's own automatic schedule; there is no reliable programmatic way to force
one.

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
