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

`admin_user` and `admin_group` are mutually non-exclusive — at least one must be provided, and
both can be set together (assigns both a user and a group admin).

On unexpected failure after project creation: rollback via `delete_project(key)`. The rollback
itself is wrapped in its own try/except — a failed rollback is logged, not raised, so it can
never mask or crash past the original error. The route always returns a proper `500`
`ExceptionResponse` on this path (not a bare fallthrough with no response body).

## Bitbucket REST API calls

### Create project — `POST /rest/api/latest/projects`

```
POST /rest/api/latest/projects
Body: {"key": key, "name": name, "description": description, "public": <caller-supplied, default false>}
→ 201
```

`ProjectSpec.public` is a real, caller-settable `bool` field (default `False`) — `create_project`
passes it through to Bitbucket unmodified. Sending `"public": true` really does create a public
project.

### Delete project — cascades repo deletion first

Bitbucket **refuses to delete a project that still contains repositories**:
`DELETE /rest/api/latest/projects/{key}` on a project with any repo inside returns `409` with
`{"errors":[{"message":"The project \"{key}\" cannot be deleted because it has repositories.",
"exceptionName":"com.atlassian.bitbucket.IntegrityException"}]}` — regardless of repo size, even
a single empty repo triggers it.

`delete_project` therefore lists all repos under the project first and deletes each one before
deleting the project itself:

```
GET    /rest/api/latest/projects/{key}/repos?start={start}&limit=100   (paginated via list_repos)
  → {"values": [{"slug": ..., ...}], "isLastPage": bool, "nextPageStart": int}
DELETE /rest/api/latest/projects/{key}/repos/{repo_slug}    for each repo
  → 202 (Accepted — genuinely asynchronous under the hood; git data purge happens in background)
DELETE /rest/api/latest/projects/{key}
  → 204
```

No polling is needed between the repo deletes and the project delete: even though a repo delete
returns `202`, an immediate `GET` on that repo already 404s, and the project delete that follows
immediately succeeds with `204`. Bitbucket's REST-visible state (both repo and project) flips to
"gone" synchronously with the API response; only the on-disk data purge is asynchronous.
`delete_project` does not poll for confirmation (unlike Confluence's space delete — see
`app/v1/confluence/CLAUDE.md` — which has a real accepted-but-not-yet-gone race).

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

Confirmed against Bitbucket Data Center 10.2.2 with a real AD-connected directory.
`GET /rest/api/1.0/admin/user-directories` (the Bitbucket-native admin REST API) also works and
returns a friendlier `{"name", "type", "isActive", "description"}` shape, but **never exposes an
id field at all** — not even embedded in a link — so it cannot support the sync operation below.
Bitbucket shares the same Atlassian Crowd-embedded REST resource Jira and Confluence use (see
`app/v1/jira/CLAUDE.md`, `app/v1/confluence/CLAUDE.md`); its shape matches Confluence's exactly
(`directory`/`link`, singular), not Jira's (`directories`/`links`, plural) — same underlying
module, inconsistent JSON key pluralization across products. The numeric ID only exists embedded
in `link[0].href` (e.g. `.../directory/32769` → `32769`), which `sync_user_directory` parses out.

### Sync user directory — unsupported, `sync_user_directory` always raises `501`

Bitbucket Data Center has **no supported way to trigger a directory sync on demand**. Investigated
thoroughly against Bitbucket Data Center 10.2.2 before concluding this:

1. `POST /rest/crowd/latest/directory/{id}/synchronise` — the path Jira/Confluence use
   successfully for the same shared Crowd-embedded resource — **404s on Bitbucket** even with the
   correct connector directory ID.
2. `POST /rest/api/1.0/admin/user-directories/{id}/sync` also 404s with a real ID.
3. The Bitbucket **web UI** does have a working "Synchronize" action, reachable via an
   undocumented internal servlet: `POST /plugins/servlet/embedded-crowd/directories/sync?directoryId={id}`.
   It accepts Basic Auth and always returns `302` — but that response is **not a reliable success
   signal**: repeat calls verified via tight API polling (`currentStartTime`/`lastStartTime`
   unchanged over 90+ seconds) and the admin UI directly produced zero effect despite an identical
   `302` each time. The one apparent success coincided with Bitbucket's own internal automatic
   sync schedule (~30 minutes apart), not the manual trigger — the servlet likely silently
   no-ops/throttles repeats with no way to tell from the response.

Reporting `"successful"` on a request that almost always silently does nothing would be worse
than not having the feature, so `sync_user_directory` raises `HTTPException(501, ...)`
unconditionally without calling Bitbucket at all. `GET /user-dirs` is unaffected. Tracked publicly
upstream since 2014 in [BSERV-5108](https://jira.atlassian.com/browse/BSERV-5108), still open —
revisit if Atlassian ever ships this.

## Schema — `ProjectSpec`

| Field | Type | Constraints |
|---|---|---|
| `key` | `str` | required; `^[a-zA-Z0-9_\-]+$`; max 255 chars |
| `name` | `str` | required; `^[a-zA-Z0-9_\-]+$`; max 255 chars |
| `description` | `str` | required; max 1000 chars |
| `public` | `bool` | optional; default `False`; passed through verbatim to Bitbucket |
| `admin_user` | `Optional[str]` | `^[a-z0-9]+$`; max 15 chars |
| `admin_group` | `Optional[str]` | `^[a-zA-Z0-9_\-]+$`; max 255 chars |

Model validator: at least one of `admin_user` / `admin_group` must be provided.

## Config fields (`conf.py`)

| Field | Default | Description |
|---|---|---|
| `BITBUCKET_ENDPOINT` | `/rest/api/latest` | Bitbucket REST API base path |
| `BITBUCKET_CROWD_ENDPOINT` | `/rest/crowd/latest` | Crowd REST API base path — used for user directory listing and sync |

Global credentials (`BITBUCKET_USERNAME`, `BITBUCKET_PASSWORD`) and `BITBUCKET_API_URL` live in `global_conf.py`.

## Testing

Tests mock the injected `bitbucket_client` via `MagicMock` / `AsyncMock`.
`conftest.py` builds a throw-away `FastAPI` app with just the Bitbucket router.
`POST /` triggers up to 3 calls: create (`post`) + user assign (`put`) + group assign (`put`).

In the e2e file, always use a `yield`-based cleanup fixture, not a plain pre-test call — a plain
call once left real `E2ETEST`/`E2EREPOTEST` projects stuck in Bitbucket after an unrelated auth
failure partway through a test.
