# Bitbucket API

Manages Bitbucket Server projects and Active Directory user directory synchronisation.

## Base path

`/api/v1/devops/bitbucket`

---

## Endpoints

### `POST /`

Creates a new Bitbucket project and grants PROJECT_ADMIN to the specified user and/or group.
Rolls back (deletes the project) automatically if any permission step fails.

**Request body**

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `key` | string | yes | `^[A-Z][A-Z0-9_]*$`, 2-10 chars | Project key (unique identifier) |
| `name` | string | yes | `^[a-zA-Z0-9_\-\s]+$`, max 80 | Project display name |
| `description` | string | yes | max 1000 | Project description |
| `public` | boolean | no | default `false` | Project visibility — passed through verbatim to Bitbucket |
| `admin_user` | string | at least one | `^[a-z][a-z0-9\-]*$`, max 20 | Username to receive PROJECT_ADMIN |
| `admin_group` | string | at least one | max 255, no pattern | Group name to receive PROJECT_ADMIN |

> At least one of `admin_user` or `admin_group` must be provided. Both can be given simultaneously.

---

### `POST /mirror`

Creates a new Bitbucket project registered with this deployment's physical Smart Mirrors server,
and grants PROJECT_ADMIN to the specified user and/or group. Rolls back (deletes the project)
automatically if any later step fails.

**Request body** — same fields as `POST /`, plus:

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `mirror_suffix_project_names` | array of strings | no | defaults to `BITBUCKET_MIRROR_SUFFIX_PROJECT_NAMES` (`Nati`, `Kat`) | The set of valid **naming suffixes** for this request — not mirror server names |
| `mirrored_env_destination` | array of strings | yes | non-empty, no duplicates; each entry must be in `mirror_suffix_project_names` | Naming suffix(es) — joined by `+` and appended to the end of `name`. Does **not** control which or how many mirror servers get used |

> The actual project name sent to Bitbucket becomes `"{name} - {destinations joined by '+'}"`
> (e.g. `["Nati", "Kat"]` → `"{name} - Nati+Kat"`) — `key` is unaffected. Separately, after the
> project is created it's registered **exactly once** with this instance's single registered
> physical Smart Mirrors server, discovered live via Bitbucket's Smart Mirrors REST API (see
> `app/v1/bitbucket/CLAUDE.md`'s "Mirror registration" section for the exact calls).
> `mirrored_env_destination` is unrelated to which mirror gets used — it only affects the
> project's display name.

---

### `DELETE /{key}`

Deletes a Bitbucket project (created via either `POST /` or `POST /mirror`). Bitbucket refuses to
delete a project that still contains repositories (`409 IntegrityException`), so this endpoint
first lists and deletes every repository under the project, then deletes the project itself.

---

### `POST /user-dirs/sync`

Triggers a synchronisation of the configured user directory (ID is auto-discovered, not
supplied by the caller).
