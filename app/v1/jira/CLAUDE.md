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
assert_user_exists                    (always — admin_user is required)
assert_group_exists  [if admin_group set]
  → create_project  (always sets lead=admin_user — Jira requires it)
  → assign_project_admin_user  (always — admin_user is required)
  → assign_project_admin_group [if admin_group set]
```

`admin_user` is required (see below); `admin_group` is optional and additional. Both are
checked to exist in Jira *before* `create_project` runs at all.

**`assert_group_exists` pre-check (added after a live-confirmed orphan bug):** a nonexistent
`admin_group` doesn't crash `assign_project_admin_group` — Jira's role-assignment endpoint
returns a clean `410 Gone` for it, same as it does for a nonexistent user in the same call.
That's an `HTTPException`, which hits the `except HTTPException` branch in `routes.py`, **not**
the bare `except:` rollback path — and that branch never deletes anything. Confirmed live:
created a real project with a valid `admin_user`, sent a nonexistent `admin_group`, got `410`,
then checked directly — the project still existed, half-configured (created + admin_user
assigned, no group role). `admin_group` is only ever touched by the later, separate
role-assignment call, which is what exposes this. `assert_group_exists`
(`GET /rest/api/latest/group?groupname={admin_group}` — exact lookup, genuine `404` if
missing, unlike Bitbucket's filter-search endpoint which 200s with an empty list) now runs
before `create_project`, so a bad group fails the whole request cleanly with nothing ever
created — no rollback needed because there's nothing to roll back.

**`assert_user_exists` pre-check:** unlike `admin_group`, `admin_user` was never actually
exposed to the orphan bug above — `create_project` sets it as `lead` directly, and Jira
rejects the entire creation for a nonexistent lead (confirmed live), so there's no window
where a project exists without a valid lead. This check exists anyway, for a fast/specific
failure before any write to Jira happens at all, and for symmetry with `assert_group_exists`
and with Bitbucket's `validate_admin_principals` shape (`GET /rest/api/latest/user?username=
{admin_user}` — same exact-lookup/genuine-404 behavior as the group endpoint).

On unexpected failure: rollback via `delete_project`. The rollback itself is wrapped in its
own try/except — a failed rollback is logged, not raised, so it can never mask or crash past
the original error. The route always returns a proper `500` `ExceptionResponse` on this path
now; it used to fall through with no `return` at all after the rollback delete, meaning a
caller saw `200 null` for what was actually a failed-and-rolled-back create — same historical
bug already fixed in `app/v1/bitbucket/routes.py` (see that module's `CLAUDE.md`), found here
independently while adding rollback test coverage for Jira and confirming the response body,
not just the delete call, on a live run.

## Jira REST API calls

### Create project — `POST /rest/api/latest/project`

```
POST /rest/api/latest/project
Body: {"key": key, "name": name, "description": description, "projectTypeKey": "software"[, "lead": admin_user]}
→ 201
```

**`admin_user` is required, unlike Bitbucket/Confluence.** Confirmed live, three ways, that
Jira's project creation unconditionally requires `lead` to be a real **user** — there is no
way to satisfy it with a group, and no way to omit it:
1. Omitting `lead` entirely → `400 {"errors":{"projectLead":"You must specify a valid project lead."}}`
2. `admin_group`-only (no `lead` set) → identical `400`
3. Setting `lead` to a **group name** directly (e.g. `"lead":"devops-tashtiot"`) → identical `400`

Unlike Bitbucket/Confluence (where "admin" is purely a permission grant, not an ownership
field), Jira's project model has a mandatory lead-user concept that a group can never
substitute for. `ProjectSpec.admin_user` is therefore a required field (not `Optional`, no
"at least one of admin_user/admin_group" validator like the other modules) — `admin_group` is
optional and, when given, is granted the same project-admin role *in addition to* the
required lead user.

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

### Sync user directory — unsupported, `sync_user_directory` always raises `501`

Jira has no supported way to manually trigger a directory sync on demand. Confirmed live, two
ways, before landing on `501`:

1. The old code picked `directories[0]`, which on a real instance is the built-in "Jira
   Internal Directory" (id `1`), not the actual LDAP/AD directory that would ever need syncing
   (id `10000` here) — directory order in the list isn't guaranteed to put the external one
   first, so this was already picking the wrong directory.
2. Even against the *correct* directory id, `POST /rest/crowd/latest/directory/10000/
   synchronise` still 404s: `{"message":"null for uri: .../directory/10000/synchronise",
   "status-code":404}`.

This is the identical finding already documented for Bitbucket and Confluence
(`app/v1/bitbucket/CLAUDE.md`, `app/v1/confluence/CLAUDE.md`) — same underlying Atlassian
Crowd-embedded module, same missing REST trigger, now independently confirmed on Jira too
rather than just assumed-by-analogy. `sync_user_directory` therefore raises
`HTTPException(501, ...)` unconditionally, without calling Jira at all, matching the pattern
used by the other two modules for the identical situation.

## Schema — `ProjectSpec`

| Field | Type | Constraints |
|---|---|---|
| `key` | `str` | required; `^[A-Z][A-Z0-9]+$`; max 10 chars |
| `name` | `str` | required; max 255 chars |
| `description` | `str` | required; max 1000 chars |
| `admin_user` | `str` (required) | `^[a-z0-9_\-]+$`; max 50 chars |
| `admin_group` | `Optional[str]` | `^[a-zA-Z0-9_\-]+$`; max 255 chars |

No cross-field validator — `admin_user` is required on its own (see "Create project" above
for why Jira, unlike Bitbucket/Confluence, can't accept a group in place of a lead user).

## Config fields (`conf.py`)

| Field | Default | Description |
|---|---|---|
| `JIRA_ENDPOINT` | `/rest/api/latest` | Jira REST API base path |
| `JIRA_CROWD_ENDPOINT` | `/rest/crowd/latest` | Crowd REST API base path — used for user directory listing and sync |

Global credentials (`JIRA_USERNAME`, `JIRA_PASSWORD`) and `JIRA_API_URL` live in `global_conf.py`.

## Testing

Tests mock the injected `jira_client` via `MagicMock` / `AsyncMock`.  
`conftest.py` builds a throw-away `FastAPI` app with just the Jira router.  
`POST /` triggers up to 3 calls: create + admin-user assign + admin-group assign.
