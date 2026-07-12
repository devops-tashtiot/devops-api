# Jira API

Manages Jira Server/Data Center projects with admin assignment, and Active Directory user directory synchronisation.

## Base path

`/api/devops/v1/jira`

---

## Endpoints

### `POST /`

Creates a new Jira project (type: `software`), sets the specified user as project lead, and grants them the Administrators role (role ID `10002`).
Rolls back (deletes the project) automatically if the permission step fails.

**Request body**

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `key` | string | yes | `^[A-Z][A-Z0-9]+$`, max 10 | Project key (uppercase, unique) |
| `name` | string | yes | max 255 | Project display name |
| `description` | string | yes | max 1000 | Project description |
| `admin_user` | string | at least one | `^[a-z0-9_\-]+$`, max 50 | Username to set as project lead and administrator |
| `admin_group` | string | at least one | `^[a-zA-Z0-9_\-]+$`, max 255 | Group name to receive project administrator role |

> At least one of `admin_user` or `admin_group` must be provided. Both can be given simultaneously.

---

### `DELETE /{project_key}`

Deletes a Jira project by key.

**Path parameter**

| Param | Type | Description |
|---|---|---|
| `project_key` | string | Key of the project to delete |

---

### `GET /user-dirs`

Returns all user directories configured in Jira (including AD/LDAP directories). Requires
the calling account to have Jira **System Administrator** permission, not just regular
Administrator.

**Response** — JSON array (unwrapped from Jira's `{"directories": [...]}`) from
`/rest/crowd/latest/directory`.

---

### `POST /user-dirs/sync`

Triggers a synchronisation of the first user directory returned by `GET /user-dirs` (ID is
auto-discovered, not supplied by the caller).
