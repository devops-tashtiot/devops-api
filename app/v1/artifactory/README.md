# Artifactory API

Manages JFrog Artifactory projects — creation with admin assignment and storage quota management.

## Base path

`/api/devops/v1/artifactory`

---

## Endpoints

### `POST /`

Creates a new Artifactory project, sets its storage quota, and grants PROJECT_ADMIN to either a user or a group (exactly one must be provided).
Rolls back (deletes the project) automatically if the admin assignment step fails.

The project key is derived from the name automatically (lowercased, spaces and underscores replaced with hyphens).

**Request body**

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `name` | string | yes | `^[a-zA-Z0-9][a-zA-Z0-9 _\-]+$`, 2–32 chars | Project display name |
| `storage_quota_giga_bytes` | integer | yes | 1–10 | Storage quota in GB |
| `admin_user` | string | at least one | `^[a-z0-9_\-]+$`, max 50 | Username to receive PROJECT_ADMIN |
| `admin_group` | string | at least one | `^[a-zA-Z0-9_\-]+$`, max 255 | Group name to receive PROJECT_ADMIN |

> At least one of `admin_user` or `admin_group` must be provided. Both can be provided to assign admin to a user and a group simultaneously.

---

### `POST /storage-quota`

Increases the storage quota for an existing Artifactory project or repository.

**Request body**

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `name` | string | yes | — | Project or repository name |
| `storage_quota_giga_bytes` | integer | yes | 1–10 | Amount of GB to add to the current quota |

---

### `GET /permissions/roles/{role_name}`

Returns the details of a global role by name from the JFrog Access API.

**Path parameters**

| Param | Type | Description |
|---|---|---|
| `role_name` | string | Name of the global role to fetch |

**Response**

Raw role object returned by `GET /access/api/v1/roles/{role_name}`.

---

### `POST /permissions`

Grants one or more roles to a user or group on an existing project.

If `member_type` is `"group"` and the group is not yet imported into JFrog Platform, it is automatically synced from the configured LDAP setting (`LDAP_SETTING_NAME`) before the role is assigned.

**Request body**

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `project_key` | string | yes | `^[a-z0-9\-]+$`, 2–32 chars | Target project key |
| `member_name` | string | yes | max 255 | Username or group name |
| `member_type` | `"user"` \| `"group"` | yes | — | Whether the member is a user or an LDAP group |
| `roles` | array of roles | yes | at least one | Roles to assign — see `GET /permissions/roles` |

**Config**

| `.env` key | Default | Description |
|---|---|---|
| `ARTIFACTORY_LDAP_SETTING_NAME` | `ldap-ad` | Name of the LDAP setting in JFrog Platform admin (used only when importing missing groups) |

---

### `GET /permissions/{project_key}`

Returns all current user and group role assignments for the given project.

**Response**

```json
{
  "users": [...],
  "groups": [...]
}
```
