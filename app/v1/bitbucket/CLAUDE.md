# Bitbucket module — developer notes

## How the client is built

`main.py` constructs a single `BaseAPI` client with basic auth from `global_config`:

```
BaseAPI(global_config.BITBUCKET_API_URL, auth=(global_config.BITBUCKET_USERNAME, global_config.BITBUCKET_PASSWORD)).client
```

Passed into `get_v1_bitbucket_router(bitbucket_client)` at startup — no per-request reconstruction.

## Routes

| Method | Path | Operation |
|--------|------|-----------|
| `POST` | `/` | Create project + assign admin (user and/or group) |
| `DELETE` | `/{key}` | Delete project |
| `GET` | `/user-dirs` | List user directories |
| `POST` | `/user-dirs/sync` | Sync the single user directory (ID auto-discovered) |

> Route paths above are devops-api's own; the upstream Bitbucket endpoints they call are `/rest/crowd/latest/directory` (see below).

## Project create flow (POST /)

```
validate_admin_principals         ← fails here if user/group not found; project is never created
  → _assert_user_exists           [if admin_user set]
  → _assert_group_exists          [if admin_group set]
create_project
  → assign_admin_permission       [if admin_user set]
  → assign_admin_group_permission [if admin_group set]
```

`admin_user` and `admin_group` are mutually non-exclusive — at least one must be provided.

On unexpected failure after project creation: rollback via `delete_project(key)`.

## Bitbucket REST API calls

### Create project — `POST /rest/api/latest/projects`

```
POST /rest/api/latest/projects
Body: {"key": key, "name": name, "description": description, "public": false}
→ 201
```

Projects are always created as private (`public: false` is hardcoded — the field is not exposed to callers).

### Delete project — `DELETE /rest/api/latest/projects/{key}`

```
DELETE /rest/api/latest/projects/{key}
→ 204
```

### Assign user admin — pre-check + `PUT`

```
# 1. Pre-check: confirm user exists
GET /rest/api/latest/admin/users?filter={admin_user}
→ 200, values array; raises 404 "User '{admin_user}' does not exist in Bitbucket" if not found

# 2. Assign permission
PUT /rest/api/latest/projects/{key}/permissions/users?name={admin_user}&permission=PROJECT_ADMIN
→ 204
```

### Assign group admin — pre-check + `PUT`

```
# 1. Pre-check: confirm group exists
GET /rest/api/latest/admin/groups?filter={admin_group}
→ 200, values array; raises 404 "Group '{admin_group}' does not exist in Bitbucket" if not found

# 2. Assign permission
PUT /rest/api/latest/projects/{key}/permissions/groups?name={admin_group}&permission=PROJECT_ADMIN
→ 204
```

### List user directories — `GET /rest/crowd/latest/directory`

```
GET /rest/crowd/latest/directory
Header: Accept: application/json
→ 200, {"directory": [{"name": ..., "link": [{"href": "https://.../directory/{id}", "rel": "self"}], "synchronisation"?: {...}}, ...]}
```

Confirmed live against Bitbucket Data Center 10.2.2 with a real AD-connected directory.
`GET /rest/api/1.0/admin/user-directories` (the Bitbucket-native admin REST API) also works
and returns a friendlier `{"name", "type", "isActive", "description"}` shape, but **never
exposes an id field at all** — not even embedded in a link — so it cannot support the sync
operation below. Bitbucket shares the same Atlassian Crowd-embedded REST resource Jira and
Confluence use (see `app/v1/jira/CLAUDE.md`, `app/v1/confluence/CLAUDE.md`); its shape
matches Confluence's exactly (`directory`/`link`, singular), not Jira's (`directories`/
`links`, plural) — same underlying module, inconsistent JSON key pluralization across
products. Neither response includes an `id` field on each directory object; the numeric ID
only exists embedded in `link[0].href` (e.g. `.../directory/32769` → `32769`), which is what
`sync_user_directory` parses out.

### Sync user directory — `POST /rest/crowd/latest/directory/{id}/synchronise`

```
POST /rest/crowd/latest/directory/{id}/synchronise
Header: Accept: application/json
→ id is parsed from the first listed directory's link[0].href, not a response "id" field
   (see above — no such field exists in either the Crowd or native admin API)
```

British spelling (`synchronise`, not `sync`) — confirmed live: the old `.../admin/
user-directories/{id}/sync` path this used to call 404s; this corrected Crowd-based path
returns 200 against a real AD-connector directory.

## Schema — `ProjectSpec`

| Field | Type | Constraints |
|---|---|---|
| `key` | `str` | required; `^[a-zA-Z0-9_\-]+$`; max 255 chars |
| `name` | `str` | required; `^[a-zA-Z0-9_\-]+$`; max 255 chars |
| `description` | `str` | required; max 1000 chars |
| `admin_user` | `Optional[str]` | `^[a-z0-9]+$`; max 15 chars |
| `admin_group` | `Optional[str]` | `^[a-zA-Z0-9_\-]+$`; max 255 chars |

Model validator: at least one of `admin_user` / `admin_group` must be provided.

## Config fields (`conf.py`)

| Field | Default | Description |
|---|---|---|
| `BITBUCKET_ENDPOINT` | `/rest/api/latest` | Bitbucket REST API base path |
| `BITBUCKET_CROWD_ENDPOINT` | `/rest/crowd/latest` | Crowd REST API base path — used for user directory listing and sync |

Global credentials (`BITBUCKET_USERNAME`, `BITBUCKET_PASSWORD`) and `BITBUCKET_API_URL` live in `global_conf.py`.

## Local dev

```bash
docker compose -f ../docker-compose.bitbucket.yaml up -d
# Bitbucket at http://localhost:7990  user: admin  pass: 12345678
```

Set in `.env`:
```
BITBUCKET_API_URL=http://localhost:7990
BITBUCKET_USERNAME=admin
BITBUCKET_PASSWORD=12345678
```

## Testing

Tests mock the injected `bitbucket_client` via `MagicMock` / `AsyncMock`.  
`conftest.py` builds a throw-away `FastAPI` app with just the Bitbucket router.  
`POST /` triggers up to 3 calls: create (`post`) + user assign (`put`) + group assign (`put`).
