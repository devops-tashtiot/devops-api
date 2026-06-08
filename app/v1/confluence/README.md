# Confluence API

Manages Confluence spaces, plugins, space imports, and Active Directory user directory synchronisation.

## Base path

`/api/devops/latest/confluence`

---

## Endpoints

### `POST /`

Creates a new Confluence space and grants admin permission to either a user or a group (exactly one must be provided).
Rolls back (deletes the space) automatically if the permission step fails.

**Request body**

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `key` | string | yes | `^[A-Z0-9]+$`, max 255 | Space key (uppercase) |
| `name` | string | yes | max 255 | Space display name |
| `description` | string | yes | max 1000 | Space description |
| `admin_user` | string | at least one | `^[a-z0-9_\-]+$`, max 50 | Username to receive space admin |
| `admin_group` | string | at least one | `^[a-z0-9_\-]+$`, max 255 | Group name to receive space admin |

> At least one of `admin_user` or `admin_group` must be provided. Both can be given to assign admin to a user and a group simultaneously.

---

### `POST /plugin/`

Fetches a `.jar` plugin from the shared S3/MinIO bucket and installs it into Confluence via UPM.

**Prerequisites:** plugin must be uploaded to the bucket first; Admin must have disabled "Prevent users from installing add-ons" in Confluence settings.

**Request body**

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `plugin_name` | string | yes | must end with `.jar`, max 255 | Filename in the S3 plugins bucket |

> Bucket URL configured via `S3_PLUGINS_BASE_URL` (default: `http://localhost:9100/confluence-plugins`).

---

### `DELETE /plugin/{plugin_key}`

Uninstalls a plugin from Confluence by its OSGi bundle key.

**Path parameter**

| Param | Type | Description |
|---|---|---|
| `plugin_key` | string | OSGi plugin key (e.g. `com.example.my-plugin`). Periods are handled correctly. |

---

### `POST /space-import/`

Fetches a `.zip` space export archive from S3, uploads it to Confluence's backup-restore API, and polls until the restore job completes.

**Prerequisites:** archive must be uploaded to the bucket first.

**Request body**

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `space_key` | string | yes | `^[A-Z][A-Z0-9]*$`, max 50 | Key of the space to restore — must match the key inside the archive |
| `archive_name` | string | yes | must end with `.zip`, max 255 | Filename in the S3 imports bucket |

> Bucket URL configured via `S3_IMPORTS_BASE_URL` (default: `http://localhost:9100/confluence-space-imports`).  
> Poll tuning: `JOB_POLL_INTERVAL` (default 2 s), `JOB_MAX_POLLS` (default 60).

---

### `GET /user-dirs`

Returns all user directories configured in Confluence (including AD/LDAP directories).

---

### `POST /user-dirs/{directory_id}/sync`

Triggers an Active Directory synchronisation for the specified user directory.

**Path parameter**

| Param | Type | Description |
|---|---|---|
| `directory_id` | integer | ID of the directory to sync (use `GET /user-dirs` to find IDs) |
