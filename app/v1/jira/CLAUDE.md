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
| `POST` | `/user-dirs/sync` | Sync the single user directory (ID auto-discovered) |

> Route paths above are devops-api's own; the upstream Jira endpoints they call are `/rest/crowd/latest/directory` (see below).

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

### List user directories — `GET /rest/crowd/latest/directory`

```
GET /rest/crowd/latest/directory
Header: Accept: application/json   (required — without it Jira defaults to XML and 500s:
  no XML message-body-writer is registered for this endpoint's response type)
→ 200, {"directories": [{"name": ..., "links": [{"href": "https://.../directory/{id}", "rel": "self"}], "sync"?: {...}}, ...]}
```

Confirmed live against Jira 9.12.8 (Data Center). This is the same Atlassian Crowd-embedded
REST resource Confluence uses (`app/v1/confluence/CLAUDE.md` — identical Java class in the
server logs: `com.atlassian.crowd.embedded.admin.rest.entities.DirectoryList`), but the two
products don't return identical shapes: Jira's top-level key is `directories` (plural) and
`links` (plural); Confluence's is `directory` (singular) and `link` (singular). Neither
response includes an `id` field on each directory object — the numeric ID only exists
embedded in `links[0].href` (e.g. `.../directory/10000` → `10000`), which is what
`sync_user_directory` parses out. `GET /rest/api/latest/admin/user-directories` — the
previous guess, copied from Bitbucket's convention — 404s on Jira; Bitbucket's admin REST
API and this Crowd-embedded API are two different things, not the same convention across
products as originally assumed.

Requires Jira **System Administrator** (not just regular Administrator) on the calling
account — `ADMINISTER: true` alone gets a 403 "Client must be authenticated as a system
administrator"; the account needs `SYSTEM_ADMIN: true` (`GET /rest/api/2/mypermissions`),
normally granted via the `jira-system-administrators` group.

### Sync user directory — `POST /rest/crowd/latest/directory/{id}/synchronise`

```
POST /rest/crowd/latest/directory/{id}/synchronise
Header: Accept: application/json
→ id is parsed from the first listed directory's links[0].href, not a response "id" field
   (see above — no such field exists)
```

Note: British spelling (`synchronise`, not `sync`) — inferred from the shared Crowd-embedded
REST resource with Confluence (same convention there), not independently confirmed by firing
this specific POST against live Jira (a state-changing call, not exercised during
verification — only the `GET` was).

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
| `JIRA_CROWD_ENDPOINT` | `/rest/crowd/latest` | Crowd REST API base path — used for user directory listing and sync |

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
