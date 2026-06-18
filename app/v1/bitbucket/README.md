# Bitbucket API

Manages Bitbucket Server projects and Active Directory user directory synchronisation.

## Base path

`/api/devops/v1/bitbucket`

---

## Endpoints

### `POST /`

Creates a new Bitbucket project and grants PROJECT_ADMIN to the specified user and/or group.
Rolls back (deletes the project) automatically if any permission step fails.

**Request body**

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `key` | string | yes | `^[a-zA-Z0-9_\-]+$`, max 255 | Project key (unique identifier) |
| `name` | string | yes | `^[a-zA-Z0-9_\-]+$`, max 255 | Project display name |
| `description` | string | yes | max 1000 | Project description |
| `admin_user` | string | at least one | `^[a-z0-9]+$`, max 15 | Username to receive PROJECT_ADMIN |
| `admin_group` | string | at least one | `^[a-zA-Z0-9_\-]+$`, max 255 | Group name to receive PROJECT_ADMIN |

> At least one of `admin_user` or `admin_group` must be provided. Both can be given simultaneously.

---

### `GET /user-dirs`

Returns all user directories configured in Bitbucket (including AD/LDAP directories).

**Response** — JSON array from Bitbucket's `/rest/api/latest/admin/user-dirs`.

---

### `POST /user-dirs/{directory_id}/sync`

Triggers an Active Directory synchronisation for the specified user directory.

**Path parameter**

| Param | Type | Description |
|---|---|---|
| `directory_id` | integer | ID of the user directory to sync (use `GET /user-dirs` to find IDs) |
