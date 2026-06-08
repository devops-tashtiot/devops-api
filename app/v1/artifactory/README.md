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
