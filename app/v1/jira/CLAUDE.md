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
create_project  (always sets lead=admin_user — Jira requires it)
  → assign_project_admin_user  (always — admin_user is required)
  → assign_project_admin_group [if admin_group set]
```

`admin_user` is required (see below); `admin_group` is optional and additional.

On unexpected failure: rollback via `delete_project`.

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

### Sync user directory — broken two ways, confirmed live

**Bug 1 — wrong directory picked.** `sync_user_directory` always uses `directories[0]`, which
on a real instance is the built-in "Jira Internal Directory" (id `1`), not the actual LDAP/AD
directory that would ever need syncing (id `10000` here). Directory order in the list isn't
guaranteed to put the external directory first.

**Bug 2 — the endpoint doesn't work on Jira at all, even with the correct ID.** Confirmed
live: `POST /rest/crowd/latest/directory/10000/synchronise` (the *correct*, LDAP directory
ID, not directory `1`) still returns `404 {"message":"null for uri: .../directory/10000/
synchronise","status-code":404}`. This is the identical finding already documented for
Bitbucket and Confluence (`app/v1/bitbucket/CLAUDE.md`, `app/v1/confluence/CLAUDE.md`) — same
underlying Atlassian Crowd-embedded module, same missing REST trigger, now independently
confirmed on Jira too rather than just assumed-by-analogy. `sync_user_directory` currently
still attempts the call and surfaces a raw upstream `404` as a `"Failed"` response instead of
the clean `501` Bitbucket/Confluence use for the identical situation — not yet aligned to that
pattern as of this writing.

```
POST /rest/crowd/latest/directory/{id}/synchronise
Header: Accept: application/json
→ 404 on this instance, regardless of which directory id is used
```

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
