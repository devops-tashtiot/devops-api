# ArgoCD API

Manages ArgoCD consumer configuration files in a GitOps repository (Bitbucket).
Each consumer config is a YAML file committed to `{env}/consumers/{name}/config.yaml`.

## Base path

`/api/devops/v1/argocd`

---

## Configuration

The GitOps repo connection is set in the environment:

| Env var | Description |
|---|---|
| `GIT_API_URL` | Bitbucket Server URL |
| `GIT_TOKEN` | Personal access token |
| `GIT_USERNAME` | Git user |
| `GIT_PROJECT_KEY` | Bitbucket project key |
| `ARGOCD_AAS_REPO_SLUG` | Repo slug (default: `argocd`) |
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
| `extra_roles` | array of strings | no | see [RBAC policy lines](#rbac-policy-lines) | Additional ArgoCD RBAC policy lines (`g`/`p` entries) written verbatim into the consumer config |
| `config` | object | no | see [ArgoCD config overrides](#argocd-config-overrides) | Optional ArgoCD configuration overrides injected into the consumer's config.yaml |

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

### `GET /rbac-resources`

Returns the list of valid ArgoCD RBAC resource kinds for `p_lines[].resource` (`applications`, `applicationsets`, `clusters`, `projects`, `repositories`, `accounts`, `certificates`, `gpgkeys`, `logs`, `exec`, `extensions`, `*`).

---

### `GET /rbac-actions`

Returns the list of valid ArgoCD RBAC actions for `p_lines[].action` (`get`, `create`, `update`, `delete`, `sync`, `action`, `override`, `invoke`, `*`).

---

### `GET /environments`

Returns the list of valid environments for this deployment.

---

### `POST /cluster-secret`

Registers one or more Kubernetes clusters as ArgoCD cluster secrets by creating (and syncing) an ArgoCD `Application` that deploys the `cluster-secret` Helm chart. Before creating the Application, each `application_clusters[]` entry's token is validated by running `kubectl auth can-i "*" "*"` against that cluster's own API server — a `401` means the token is invalid or the server is unreachable, a `403` means the token lacks admin rights.

This endpoint blocks until the sync it triggers has actually finished (not just been dispatched) before returning `200` — bounded by `ARGOCD_APPLICATION_SET_TIMEOUT` (default 300s). This avoids a race where a caller's very next request (an update or delete) would otherwise hit ArgoCD's "another operation is already in progress" error.

devops-api authenticates its own call to ArgoCD's API via SSO (a `client_credentials` token minted against `clusters-provision/clusters/rhbk`'s dedicated `devops-api-argocd` service-account client) — there is no ArgoCD API token in the request body; callers never supply ArgoCD credentials at all.

**Request body**

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `chosen_name` | string | yes | `^[a-zA-Z0-9_\-]+$`, max 255 | Prefix for the ArgoCD app name — final name is `{chosen_name}-cluster-secret` |
| `app_name` | string | yes | `^[a-zA-Z0-9_\-]+$`, max 255 | Consumer name — used to build the target ArgoCD instance URL `https://{app_name}.argocd.{DOMAIN_SUFFIX}` |
| `application_clusters` | array, min 1 | yes | | Clusters to register — each has `name`, `namespace` (comma-separated for multiple), `address`, `token` (that target cluster's own service-account token — unrelated to ArgoCD auth) |

---

### `DELETE /cluster-secret`

Deletes the ArgoCD `Application` created by `POST /cluster-secret`. Blocks until the deletion is confirmed (not just accepted) before returning `200` — required before an Application with the same name can be recreated.

**Query parameters**: `app_name`, `chosen_name` (both required).

---

### `PUT /cluster-secret/{app_name}/{chosen_name}`

Updates an existing cluster-secret Application's Helm parameters (replaces `application_clusters`) and re-syncs it. Like `POST /cluster-secret`, blocks until that sync has actually finished before returning `200`.

**Path parameters**: `app_name`, `chosen_name`.

**Request body**: `application_clusters` (same shape as `POST /cluster-secret`).

---

## RBAC policy lines

`extra_roles` is an optional list of ArgoCD RBAC policy strings. Each entry must match one of:

- **`g` line** — group/user assignment: `g, <subject>, <role>`
- **`p` line** — permission rule: `p, <subject>, <resource>, <action>, <object>, <allow|deny>`

Valid resources: `applications`, `applicationsets`, `clusters`, `projects`, `repositories`, `accounts`, `certificates`, `gpgkeys`, `logs`, `exec`, `extensions`, `*`

Valid actions: `get`, `create`, `update`, `delete`, `sync`, `action`, `override`, `invoke`, `*`

**Examples:**

```json
{
  "extra_roles": [
    "g, \"DEV_MyTeam\", role:myteam",
    "p, role:myteam, applications, *, myteam/*, allow",
    "p, role:myteam, clusters, get, https://api.example.com:6443, allow"
  ]
}
```

---

## ArgoCD config overrides

The optional `config` field injects ArgoCD configuration into the consumer's `config.yaml`. It has two sub-fields:

### `extra_argocd_cm_args`

Key-value pairs written into the `argocd-cm` ConfigMap. Any key is accepted — there is no
namespace whitelist (see `app/v1/argocd/CLAUDE.md` for why: a hardcoded list would need to be
kept in sync by hand with ArgoCD's own evolving config schema, and there's no live API to check
against instead). It's the caller's responsibility to pass keys ArgoCD actually recognizes;
see [ArgoCD's `argocd-cm` reference](https://argo-cd.readthedocs.io/en/stable/operator-manual/argocd-cm-yaml/)
for the real, current schema.

Values must be `string`, `boolean`, `integer`, or `float` — no nested objects or lists. Multiline string values (e.g. `resource.links`) are validated as YAML.

### `extra_argocd_params`

Key-value pairs written into the `argocd-cmd-params-cm` ConfigMap. Same as above — any key is
accepted, no namespace whitelist; see
[ArgoCD's `argocd-cmd-params-cm` reference](https://argo-cd.readthedocs.io/en/stable/operator-manual/argocd-cmd-params-cm-yaml/)
for the real, current schema.

**Example:**

```json
{
  "config": {
    "extra_argocd_cm_args": {
      "kustomize.buildOptions": "--enable-helm --load-restrictor=LoadRestrictionsNone",
      "application.resourceTrackingMethod": "annotation+label",
      "resource.links": "- title: Resource in OpenShift's UI\n  url: https://example.com\n  if: resource.kind == \"Deployment\"\n"
    },
    "extra_argocd_params": {
      "applicationsetcontroller.enable.policy.override": false
    }
  }
}
```
