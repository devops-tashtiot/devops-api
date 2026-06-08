# SonarQube API

Manages SonarQube groups with full administrator permissions (global scope + Default permission template).

## Base path

`/api/devops/latest/sonarqube`

---

## What it does

When a group is created, the API automatically grants it:

- **Global permissions** (configurable via `SONARQUBE_GLOBAL_PERMISSIONS`):
  `admin`, `gateadmin`, `profileadmin`, `provisioning`, `scan`

- **Default template permissions** (configurable via `SONARQUBE_TEMPLATE_PERMISSIONS`):
  `user`, `codeviewer`, `issueadmin`, `securityhotspotadmin`, `admin`, `scan`

The template name defaults to `Default template` and is configurable via `SONARQUBE_ADMIN_TEMPLATE_NAME`.

---

## Endpoints

### `POST /`

Creates a SonarQube group and grants it global admin + Default template permissions.
Rolls back (deletes the group) automatically if any permission step fails.

**Request body**

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `name` | string | yes | `^[a-zA-Z0-9_\-]+$`, max 255 | Group name to create in SonarQube |

---

### `DELETE /{name}`

Deletes a SonarQube group by name.

**Path parameter**

| Param | Type | Description |
|---|---|---|
| `name` | string | Name of the group to delete |
