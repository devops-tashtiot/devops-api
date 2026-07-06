# SonarQube API

Manages SonarQube groups with full administrator permissions (global scope + Default permission template), and SonarQube consumer configuration files in a GitOps repository.

## Base path

`/api/devops/v1/sonarqube`

---

## What it does

Each consumer has its own SonarQube instance, addressed as:

```
https://{consumer_name}.sonarqube.{DOMAIN_SUFFIX}
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

---

### `POST /consumer/`

Creates a consumer config YAML and commits it to the GitOps repo at `consumers/{name}/config.yaml`.

**Request body**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | yes | — | Consumer name — used as directory name under `consumers/` |
| `plugins_list` | array of strings | no | `null` | S3 URLs to SonarQube plugin `.jar` files. Serialized as a comma-separated string (`url1, url2`) for the ApplicationSet template (`\| quote \| split ", "`). Entries must not contain commas or quotes. |
| `size` | string | no | `default` | Instance size — `default` omits the key from config.yaml; `medium` and `big` are written explicitly |

**Generated `config.yaml` example:**

```yaml
name: my-consumer
plugins_list: https://s3/sonar-plugins/sonar-auth-oidc-plugin.jar, https://s3/sonar-plugins/community-branch-plugin.jar
size: medium
```

---

### `PUT /consumer/{name}`

Updates an existing consumer config YAML in the GitOps repo.

**Path parameters**

| Param | Type | Description |
|---|---|---|
| `name` | string | Consumer name (directory name under `consumers/`) |

**Request body**

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `plugins_list` | array of strings | no | `null` | Updated list of plugin URLs |
| `size` | string | no | `default` | Updated instance size |

---

### `DELETE /consumer/{name}`

Removes a consumer config YAML from the GitOps repo.

**Path parameters**

| Param | Type | Description |
|---|---|---|
| `name` | string | Consumer name |

---

## GitOps config

Consumer configs are committed to a dedicated Bitbucket repo:

| Env var | Default | Description |
|---|---|---|
| `SONARQUBE_AAS_REPO_SLUG` | `sonarqube-as-a-service` | Bitbucket repo slug |
| `SONARQUBE_GITOPS_DEFAULT_BRANCH` | `master` | Branch to commit to |

Global Git credentials (`GIT_API_URL`, `GIT_TOKEN`, `GIT_USERNAME`, `GIT_PROJECT_KEY`, `GIT_SSH_KEY_PATH`) are shared with other modules via `global_conf.py`.
