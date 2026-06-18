# SonarQube API

Manages SonarQube groups with full administrator permissions (global scope + Default permission template).

## Base path

`/api/devops/v1/sonarqube`

---

## What it does

Each consumer has its own SonarQube instance, addressed as:

```
{SONARQUBE_SCHEME}://{consumer_name}.sonarqube.{DOMAIN_SUFFIX}[:{SONARQUBE_PORT}]
```

Credentials are taken from `SONARQUBE_USERNAME` / `SONARQUBE_PASSWORD` in `.env`.

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
| `consumer_name` | string | yes | `^[a-zA-Z0-9_\-]+$`, max 255 | Identifies the target SonarQube instance |
| `name` | string | yes | `^[a-zA-Z0-9_\-]+$`, max 255 | Group name to create in SonarQube |

---

### `DELETE /{consumer_name}/{name}`

Deletes a SonarQube group by name.

**Path parameters**

| Param | Type | Description |
|---|---|---|
| `consumer_name` | string | Identifies the target SonarQube instance |
| `name` | string | Name of the group to delete |
