# ArgoCD API

Manages ArgoCD consumer configuration files in a GitOps repository (Bitbucket).
Each consumer config is a YAML file committed to `{env}/consumers/{name}/config.yaml`.

## Base path

`/api/devops/latest/argocd`

---

## Configuration

The GitOps repo connection is set in the environment:

| Env var | Description |
|---|---|
| `GIT_API_URL` | Bitbucket Server URL |
| `GIT_TOKEN` | Personal access token |
| `GIT_USERNAME` | Git user |
| `GIT_PROJECT_KEY` | Bitbucket project key |
| `ARGOCD_GITOPS_REPO_SLUG` | Repo slug (default: `argocd-configs`) |
| `ARGOCD_GITOPS_DEFAULT_BRANCH` | Branch to commit to (default: `master`) |
| `ARGOCD_ALLOWED_ENVS` | Allowed environment names (e.g. `["prod","dr","int"]`) |
| `ARGOCD_ALLOWED_SIZES` | Allowed instance sizes (default: `extraLarge`, `large`, `medium`, `small`) |
| `ARGOCD_ALLOWED_RESOURCES` | Allowed resource kinds (default: `ExternalSecret`, `ConfigMap`, `Deployment`) |

---

## Endpoints

### `POST /`

Creates a consumer config YAML and commits it to the GitOps repo.

**Request body**

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `name` | string | yes | `^[a-zA-Z0-9_\-]+$`, max 255 | Consumer name — used as directory name under `consumers/` |
| `environment` | string | yes | one of `ARGOCD_ALLOWED_ENVS` | Target environment |
| `size` | string | yes | one of `ARGOCD_ALLOWED_SIZES` | ArgoCD instance size |
| `include_resources` | array of strings | yes | each one of `ARGOCD_ALLOWED_RESOURCES`, min 1 item | Kubernetes resource kinds to include |
| `ad_admin_group` | string | yes | `^[a-zA-Z0-9_\-]+$`, max 255 | Active Directory group to grant admin access |

---

### `DELETE /{env}/{name}`

Removes a consumer config YAML from the GitOps repo.

**Path parameters**

| Param | Type | Description |
|---|---|---|
| `env` | string | Environment name (e.g. `prod`) |
| `name` | string | Consumer name |

---

### `GET /sizes`

Returns the list of valid ArgoCD instance sizes for this deployment.

---

### `GET /include-resources`

Returns the list of valid Kubernetes resource kinds for `include_resources`.

---

### `GET /environments`

Returns the list of valid environments for this deployment.
