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

`admin_user` is required (see below); `admin_group` is optional and additional. Both are checked
to exist in Jira *before* `create_project` runs at all.

**Why `assert_group_exists` runs before creation:** a nonexistent `admin_group` doesn't crash
`assign_project_admin_group` — Jira's role-assignment endpoint returns a clean `410 Gone` for it
(same as for a nonexistent user in the same call). That's an `HTTPException`, which hits the
`except HTTPException` branch in `routes.py`, **not** the bare `except:` rollback path — and that
branch never deletes anything, so without this pre-check a bad group would leave a real,
half-configured project behind (created + admin_user assigned, no group role) with the caller
told only `410`. `assert_group_exists` (`GET /rest/api/latest/group?groupname={admin_group}` —
exact lookup, genuine `404` if missing, unlike Bitbucket's filter-search endpoint which 200s with
an empty list) now runs before `create_project`, so a bad group fails the whole request cleanly
with nothing created — no rollback needed because there's nothing to roll back.

`assert_user_exists` exists for symmetry and a fast/specific failure before any write happens —
`admin_user` was never actually exposed to the same orphan risk, since `create_project` sets it
as `lead` directly and Jira rejects the entire creation for a nonexistent lead.

On unexpected failure: rollback via `delete_project`. The rollback itself is wrapped in its own
try/except — a failed rollback is logged, not raised, so it can never mask or crash past the
original error. The route always returns a proper `500` `ExceptionResponse` on this path (not a
bare fallthrough with no response body — same historical bug class already fixed in
`app/v1/bitbucket/routes.py`, see that module's `CLAUDE.md`).

## Jira REST API calls

### Create project — `POST /rest/api/latest/project`

```
POST /rest/api/latest/project
Body: {"key": key, "name": name, "description": description, "projectTypeKey": "software"[, "lead": admin_user]}
→ 201
```

**`admin_user` is required, unlike Bitbucket/Confluence.** Jira's project creation
unconditionally requires `lead` to be a real **user** — there is no way to satisfy it with a
group, and no way to omit it: omitting `lead` entirely, or setting it to a group name, both
return `400 {"errors":{"projectLead":"You must specify a valid project lead."}}`. Unlike
Bitbucket/Confluence (where "admin" is purely a permission grant, not an ownership field), Jira's
project model has a mandatory lead-user concept that a group can never substitute for.
`ProjectSpec.admin_user` is therefore a required field (not `Optional`, no "at least one of
admin_user/admin_group" validator like the other modules) — `admin_group` is optional and, when
given, is granted the same project-admin role *in addition to* the required lead user.

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

### Sync user directory — unsupported, `sync_user_directory` always raises `501`

Jira has no supported way to manually trigger a directory sync on demand. Two things confirmed
before landing on `501`:

1. Naively picking `directories[0]` (the old code's approach) isn't safe — on a real instance
   that's the built-in "Jira Internal Directory" (id `1`), not the actual LDAP/AD directory (id
   `10000` here); directory order in the list isn't guaranteed to put the external one first.
2. Even against the *correct* directory id, `POST /rest/crowd/latest/directory/10000/synchronise`
   still 404s: `{"message":"null for uri: .../directory/10000/synchronise", "status-code":404}`.

Same finding already documented for Bitbucket and Confluence (`app/v1/bitbucket/CLAUDE.md`,
`app/v1/confluence/CLAUDE.md`) — same underlying Atlassian Crowd-embedded module, same missing
REST trigger, independently confirmed on Jira too. `sync_user_directory` therefore raises
`HTTPException(501, ...)` unconditionally, matching the other two modules.

## Schema — `ProjectSpec`

| Field | Type | Constraints |
|---|---|---|
| `key` | `str` | required; `^[A-Z][A-Z0-9]+$`; 2-10 chars |
| `name` | `str` | required; max 255 chars |
| `description` | `str` | required; max 1000 chars |
| `admin_user` | `str` (required) | `^[a-z][a-z0-9\-]*$`; max 20 chars |
| `admin_group` | `str \| None` | max 255 chars; no `pattern` — group names left unconstrained (see `.claude/skills/schema_update_best_practice.md`) |

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
