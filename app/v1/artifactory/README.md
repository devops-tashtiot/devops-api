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

---

### `POST /xray/vulnerability-update`

Fetches a Xray air-gapped vulnerability database update archive from MinIO and uploads it to Xray.

**Prerequisites:** archive must be uploaded to the `platform-devops-team/xray-vulnerability-updates/` subfolder in MinIO first.

**Request body**

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `file_name` | string | yes | `^[a-zA-Z0-9_\-\.]+$`, max 255 | Filename of the update archive in the MinIO subfolder |

> Bucket URL configured via `ARTIFACTORY_S3_XRAY_UPDATES_BASE_URL` (default: `http://localhost:9100/platform-devops-team/xray-vulnerability-updates`).

---

## MinIO setup — platform-devops-team bucket

The Xray vulnerability update flow fetches the update archive from a private MinIO bucket called **`platform-devops-team`**. This bucket is internal — no public access policy is applied.

### 1. Start MinIO

```bash
docker compose -f docker-compose.minio.yaml up -d
# S3 API: http://localhost:9100   Console: http://localhost:9101
```

### 2. Create the bucket and subfolder

Log in to the MinIO Console at `http://localhost:9101` (default credentials: `minioadmin` / `minioadmin`), then:

1. **Buckets → Create bucket** — name it `platform-devops-team`
2. Inside the bucket, create the prefix: `xray-vulnerability-updates/`

Or via the `mc` CLI:

```bash
mc alias set local http://localhost:9100 minioadmin minioadmin
mc mb local/platform-devops-team
mc mb local/platform-devops-team/xray-vulnerability-updates
```

> Do **not** apply a public policy to this bucket. Leave it with the default private access — only authenticated MinIO users can read from it.

### 3. Upload a vulnerability update archive

Download the Xray offline update bundle from the [JFrog support portal](https://jfrog.com/knowledge-base/xray-offline-update/) and upload it to the subfolder:

```bash
mc cp ./xray-vuln-update-2026-01-01.zip local/platform-devops-team/xray-vulnerability-updates/
```

### 4. Set env var

Add to `.env`:

```
ARTIFACTORY_S3_XRAY_UPDATES_BASE_URL=http://localhost:9100/platform-devops-team/xray-vulnerability-updates
```
