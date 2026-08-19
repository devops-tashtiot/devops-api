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
| `POST` | `/mirror` | Create project registered with a Smart Mirrors server + assign admin |
| `DELETE` | `/{key}` | Delete project (either kind — same route) |
| `POST` | `/user-dirs/sync` | Sync the single user directory (ID auto-discovered) |

> Route paths above are devops-api's own; the upstream Bitbucket endpoints they call are `/rest/crowd/latest/directory` (see below).

## Project create flow (POST / and POST /mirror)

`POST /` and `POST /mirror` are two independent route handlers in `routes.py` (each with its own
validate → create → assign admin → rollback-on-failure block, deliberately not sharing a helper —
matches this module's usual one-handler-per-route style); only the create call in the middle
differs:

```
validate_admin_principals         ← fails here if user/group not found; project is never created
  → _assert_user_exists           [if admin_user set]
  → _assert_group_exists          [if admin_group set]
create_project (POST /) OR create_mirror_project (POST /mirror)
  → assign_admin_permission       [if admin_user set]
  → assign_admin_group_permission [if admin_group set]
```

**`POST /mirror` is a separate endpoint/schema (`MirrorProjectSpec`), not a `mirror` boolean flag
on the plain create endpoint** — the endpoint you call is what says "this is a mirror", so
`mirrored_env_destination` is simply a required field on `MirrorProjectSpec` instead of a
conditionally-required field guarded by a second validator. `create_mirror_project` builds the
suffixed name via `payload.model_copy(update={"name": ...})` and delegates the actual project
creation to `create_project`, then registers the result with the chosen physical Smart Mirrors
server — see "Mirror registration" below. `DELETE /{key}` is unchanged and deletes either kind of
project the same way (mirroring only affects creation, not deletion).

`admin_user` and `admin_group` are mutually non-exclusive — at least one must be provided, and
both can be set together (assigns both a user and a group admin). This validator lives on the
base `ProjectSpec` and is inherited by `MirrorProjectSpec`.

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

**`mirrored_env_destination` (POST /mirror only) — name suffix, plus real registration with a
Bitbucket Smart Mirrors physical mirror server.** `create_mirror_project` builds a copy of the
payload with `" - {mirrored_env_destination}"` (`mirrored_env_destination` is
`Literal["Nati", "Kat"]`, required on `MirrorProjectSpec`) appended to `name`, then calls the
same `create_project` the plain endpoint uses — `body["name"]` becomes e.g. `"My Project - Nati"`.
`key` is untouched.

### Mirror registration — Bitbucket Data Center's Smart Mirrors REST API

`mirrored_env_destination` names one of this instance's **registered physical mirror servers**
(Bitbucket Data Center's Smart Mirrors farm feature — a mirror is a separate, real Bitbucket
server instance, not something devops-api creates). `create_mirror_project` looks the mirror up
live rather than hardcoding its URL, then registers the new project with it:

```
GET  /rest/mirroring/1.0/mirrorServers?start={start}&limit=100     (paginated, on the main instance)
  → {"values": [{"id", "baseUrl", "name", "productType", "productVersion", "lastSeenDate",
                 "enabled"}], "isLastPage": bool, "nextPageStart": int}
  → _find_mirror_server matches by name (case-insensitive) against mirrored_env_destination,
    raises 404 if no mirror is registered under that name

GET  {mirror_baseUrl}/rest/mirroring/1.0/upstreamServers?start={start}&limit=100
     (paginated, called against the *mirror server's own* API, same BITBUCKET_USERNAME/
     BITBUCKET_PASSWORD credentials as the main instance — confirmed this platform's mirrors
     share auth with the source)
  → _find_upstream_id matches by baseUrl against global_config.BITBUCKET_API_URL, raises 502
    if this instance isn't registered as an upstream on that mirror (the farm connection
    itself — pairing the two Bitbucket instances — must already exist; devops-api cannot
    create that pairing, only use it)

POST {mirror_baseUrl}/rest/mirroring/1.0/upstreamServers/{upstreamId}/settings/projects/{projectId}
     (no body — projectId is the numeric id from create_project's response, not the string key)
  → configures the mirror to mirror this specific project
```

**Not yet verified live** — written from Atlassian's REST API docs
(`bitbucket-mirroring-upstream-rest.html` / `bitbucket-mirroring-mirror-rest.html`), not
confirmed against a real Smart Mirrors farm (this sandbox has no live access to the deployed
Bitbucket instance, and its actual Smart Mirrors setup — whether "Nati"/"Kat" mirrors exist,
whether the upstream pairing is established — is unconfirmed). In particular:
- The exact response field names (`id`, `baseUrl`, `name` on `mirrorServers`; `id`, `baseUrl` on
  `upstreamServers`) come from Atlassian's example JSON, not a live call against this instance's
  Bitbucket version — confirm they match before relying on this in production.
- `POST .../settings/projects/{projectId}` is documented as "configures the mirror to mirror the
  provided project[s]" with no example request/response body; if it 404s or needs a body, check
  `PUT {mirror_baseUrl}/rest/mirroring/1.0/upstreamServers/{upstreamId}/settings` instead (takes
  `{"mode": "...", "projectIds": [...]}` — but don't set `mode` to `ALL_PROJECTS` from this code:
  Atlassian's docs describe that switch as irreversible without fully removing and re-adding the
  mirror).
- If registration fails after `create_project` already succeeded, the route's existing bare
  `except Exception` rollback (`delete_project`) covers it like any other post-create failure —
  no special-cased rollback was added for this specifically.

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
unconditionally without calling Bitbucket at all. Tracked publicly
upstream since 2014 in [BSERV-5108](https://jira.atlassian.com/browse/BSERV-5108), still open —
revisit if Atlassian ever ships this.

## Schema — `ProjectSpec` and `MirrorProjectSpec`

| Field | Type | Constraints |
|---|---|---|
| `key` | `str` | required; `^[A-Z][A-Z0-9_]*$`; 2-10 chars |
| `name` | `str` | required; `^[a-zA-Z0-9_\-\s]+$`; max 80 chars |
| `description` | `str` | required; max 1000 chars |
| `public` | `bool` | optional; default `False`; passed through verbatim to Bitbucket |
| `admin_user` | `str \| None` | `^[a-z][a-z0-9\-]*$`; max 20 chars |
| `admin_group` | `str \| None` | max 255 chars; no `pattern` — Bitbucket/AD group names are left unconstrained |

`MirrorProjectSpec` (`POST /mirror` only, `BitbucketMirrorProjectRequest.spec`) extends
`ProjectSpec` with one additional required field:

| Field | Type | Constraints |
|---|---|---|
| `mirrored_env_destination` | `Literal["Nati", "Kat"]` | required; appended to `name` as `" - {mirrored_env_destination}"` |

Model validator (inherited by both): at least one of `admin_user` / `admin_group` must be
provided. `mirrored_env_destination` has no separate conditional validator anymore — it's simply
a required field on `MirrorProjectSpec`, since the endpoint itself (`POST /mirror` vs `POST /`)
now determines whether mirroring applies.

**Aligned to Bitbucket Data Center's actual project-key constraints** (previously the schema
allowed any 1-255 char alphanumeric string, which was far looser than what Bitbucket itself
enforces): `key` must start with a letter and be uppercase-only, 2-10 chars — matching
Bitbucket's own project key rules, not an arbitrary internal convention. `name` now explicitly
allows whitespace (project display names are free text in Bitbucket's UI). `admin_user` allows
hyphens now (useful for service-account-style usernames like `svc-devops-tashtiot`) and its max
length grew from 15 to 20. `admin_group` dropped its `pattern` entirely per the skill's RBAC
guidance — group names (AD/LDAP-backed) commonly contain spaces and other characters Bitbucket
does not reject, so constraining them was an artificial restriction not required by the target
service.

## Config fields (`conf.py`)

| Field | Default | Description |
|---|---|---|
| `BITBUCKET_ENDPOINT` | `/rest/api/latest` | Bitbucket REST API base path |
| `BITBUCKET_CROWD_ENDPOINT` | `/rest/crowd/latest` | Crowd REST API base path — used for user directory listing and sync |
| `BITBUCKET_MIRRORING_ENDPOINT` | `/rest/mirroring/1.0` | Smart Mirrors REST API base path — see "Mirror registration" above |

Global credentials (`BITBUCKET_USERNAME`, `BITBUCKET_PASSWORD`) and `BITBUCKET_API_URL` live in `global_conf.py`.

## Testing

Tests mock the injected `bitbucket_client` via `MagicMock` / `AsyncMock`.
`conftest.py` builds a throw-away `FastAPI` app with just the Bitbucket router.
`POST /` triggers up to 3 calls: create (`post`) + user assign (`put`) + group assign (`put`).

In the e2e file, always use a `yield`-based cleanup fixture, not a plain pre-test call — a plain
call once left real `E2ETEST`/`E2EREPOTEST` projects stuck in Bitbucket after an unrelated auth
failure partway through a test.
