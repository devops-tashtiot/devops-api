# API Catalogue — example-api v1

All modules live under `app/v1/<service>/`. Each follows the four-file convention: `conf.py`, `schemas.py`, `operations.py`, `routes.py`. Router is wired in `app/main.py` gated by `ENABLE_<SERVICE>_API`.

---

## Bitbucket — `app/v1/bitbucket/`

**Prefix:** `/api/devops/v1/bitbucket`  
**Auth:** Basic auth (username + password)  
**Base endpoint:** `/rest/api/latest`

### Schemas
| Schema | Fields |
|---|---|
| `ProjectSpec` | `key` (alphanum+`_-`, 1-255), `name` (alphanum+`_-`, 1-255), `description` (1-1000), `public: bool = False`, `admin_user` (optional, 1-15, `[a-z0-9]`), `admin_group` (optional, 1-255). At least one of `admin_user`/`admin_group` required. |

### Endpoints
| Method | Path | Body | Description |
|---|---|---|---|
| `POST` | `/` | `ProjectSpec` | Create project + optionally assign user/group admin |
| `GET` | `/user-dirs` | — | List user/group directories |
| `POST` | `/user-dirs/{directory_id}/sync` | — | Sync a directory by ID |

**Notes:** No explicit DELETE endpoint — rollback only happens on create failure.

---

## Confluence — `app/v1/confluence/`

**Prefix:** `/api/devops/v1/confluence`  
**Auth:** Basic auth  
**Base endpoints:** `/rest/api/latest`, `/rest/plugins/1.0` (UPM), `/rest/crowd/latest` (user dirs), `/rest/api/backup-restore` (import/export)

### Schemas
| Schema | Fields |
|---|---|
| `SpaceSpec` | `key` (`[A-Z0-9]+`, 1-255), `name` (1-255), `description` (1-1000), `admin_user` (optional, `[a-z0-9_\-]`, 1-50), `admin_group` (optional, `[a-z0-9_\-]`, 1-255). At least one required. |
| `PluginInstallSpec` | `plugin_name` (must end `.jar`, `[a-zA-Z0-9][-._]*`, 5-255) |
| `SpaceImportSpec` | `space_key` (`[A-Z][A-Z0-9]*`, 1-50), `archive_name` (must end `.zip`, 5-255) |
| `SpaceExportSpec` | `space_key` (`[A-Z][A-Z0-9]*`, 1-50) |

### Endpoints
| Method | Path | Body | Description |
|---|---|---|---|
| `POST` | `/` | `SpaceSpec` | Create space + assign user and/or group admin |
| `POST` | `/plugin/` | `PluginInstallSpec` | Fetch JAR from S3 → get UPM token → install plugin |
| `DELETE` | `/plugin/{plugin_key:path}` | — | Uninstall plugin by OSGi key (dotted key, path param) |
| `GET` | `/user-dirs` | — | List user/group directories |
| `POST` | `/user-dirs/{directory_id}/sync` | — | Sync a directory |
| `POST` | `/space-export/` | `SpaceExportSpec` | Trigger export job → poll → download → upload to S3 |
| `POST` | `/space-import/` | `SpaceImportSpec` | Fetch `.zip` from S3 → upload to restore endpoint → poll job |

**S3 bucket env vars:**
- `CONFLUENCE_S3_PLUGINS_BASE_URL` — default `http://localhost:9100/platform-clients/confluence-plugins`
- `CONFLUENCE_S3_IMPORTS_BASE_URL` — default `http://localhost:9100/platform-clients/confluence-space-imports`

**Key behaviour:**
- Permission grant requires two steps: grant `read` first, then `administer`
- Space delete is the rollback on create failure
- Plugin key in DELETE uses `{plugin_key:path}` to handle dotted OSGi keys

---

## Jira — `app/v1/jira/`

**Prefix:** `/api/devops/v1/jira`  
**Auth:** Basic auth  
**Base endpoint:** `/rest/api/latest`

### Schemas
| Schema | Fields |
|---|---|
| `ProjectSpec` | `key` (`[A-Z][A-Z0-9]+`, 1-10), `name` (1-255), `description` (1-1000), `admin_user` (optional, `[a-z0-9_\-]`, 1-50), `admin_group` (optional, `[a-zA-Z0-9_\-]`, 1-255). At least one required. |

### Endpoints
| Method | Path | Body | Description |
|---|---|---|---|
| `POST` | `/` | `ProjectSpec` | Create project + assign user and/or group admin |
| `DELETE` | `/{project_key}` | — | Delete project by key |
| `GET` | `/user-dirs` | — | List user/group directories |
| `POST` | `/user-dirs/{directory_id}/sync` | — | Sync a directory |

---

## SonarQube — `app/v1/sonarqube/`

**Prefix:** `/api/devops/v1/sonarqube`  
**Auth:** Basic auth  
**Base endpoint:** `/api`

### Schemas
| Schema | Fields |
|---|---|
| `GroupSpec` | `name` (`[a-zA-Z0-9_\-]`, 1-255) |

### Endpoints
| Method | Path | Body | Description |
|---|---|---|---|
| `POST` | `/` | `GroupSpec` | Create group + grant all global permissions + assign to Default template |
| `DELETE` | `/{name}` | — | Delete group by name |

**Config-driven permissions:**
- `SONARQUBE_GLOBAL_PERMISSIONS` — default `["admin","gateadmin","profileadmin","provisioning","scan"]`
- `SONARQUBE_TEMPLATE_PERMISSIONS` — default `["user","codeviewer","issueadmin","securityhotspotadmin","admin","scan"]`
- `SONARQUBE_ADMIN_TEMPLATE_NAME` — default `"Default template"`

---

## Artifactory — `app/v1/artifactory/`

**Prefix:** `/api/devops/v1/artifactory`  *(note: `v1` not `latest`)*  
**Auth:** Bearer token  
**Base endpoint:** `/access/api/v1`

### Schemas
| Schema | Fields |
|---|---|
| `ProjectSpec` | `name` (`[a-zA-Z0-9][a-zA-Z0-9 _\-]+`, 2-32), `storage_quota_giga_bytes` (int, 1-10), `admin_user` (optional, `[a-z0-9_\-]`, 1-50), `admin_group` (optional, `[a-zA-Z0-9_\-]`, 1-255). At least one required. `project_key` property: lowercase, spaces → hyphens. |
| `StorageQuotaBytes` | `name` (project/repo name), `storage_quota_giga_bytes` (int, 1-10) |
| `ProjectPermissionSpec` | `project_key` (`[a-z0-9\-]`, 2-32), `member_name` (1-255), `member_type` (`"user"` or `"group"`), `roles` (list of `ProjectRole`, min 1) |
| `ProjectRole` (enum) | `Developer`, `Contributor`, `Viewer`, `Release Manager`, `Project Admin` |
| `MemberType` (enum) | `user`, `group` |

### Endpoints
| Method | Path | Body | Description |
|---|---|---|---|
| `POST` | `/` | `ProjectSpec` | Create project + assign user/group admin |
| `POST` | `/storage-quota` | `StorageQuotaBytes` | Increase project storage quota |
| `GET` | `/permissions/roles` | — | List available project roles |
| `POST` | `/permissions` | `ProjectPermissionSpec` | Grant roles to a user or group on a project |
| `GET` | `/permissions/{project_key}` | — | Get all permissions for a project |

---

## ArgoCD — `app/v1/argocd/`

**Prefix:** `/api/devops/v1/argocd`  
**Auth:** Git connector (`tashtiot_apis_library.Git`) for gitops operations; ArgoCD API token in payload for cluster-secret operations  
**Base path (git):** `consumers/` directory in gitops repo

### Schemas

Cluster-secret auth is a single required `token` field — an ArgoCD API token for the target
`{app_name}` instance. (Earlier docs here described a mutually-exclusive `token` vs
`argocd_username`+`argocd_password` mode with a `_validate_argocd_auth` validator; that never
matched the actual code, which always required `username`+`password` only, and those in turn
were passed to `ArgoCD.from_credentials()` — a method that doesn't exist in the pinned
`tashtiot-apis-library`. Fixed 2026-07-14 by switching to the library's real constructor,
`ArgoCD(base_url, api_key, timeout)`, which is token-based from the start.)

| Schema | Fields |
|---|---|
| `ConsumerConfigSpec` | `name` (`[a-zA-Z0-9_\-]`, 1-255), `environment` (from `ARGOCD_ALLOWED_ENVS`), `size` (from `ARGOCD_ALLOWED_SIZES`), `include_resources` (list from `ARGOCD_ALLOWED_RESOURCES`, min 1), `ad_admin_group` (`[a-zA-Z0-9_\-]`, 1-255) |
| `ClusterSecretSpec` | `token` (required, ArgoCD API token), `chosen_name` (`[a-zA-Z0-9_\-]`, 1-255), `app_name` (`[a-zA-Z0-9_\-]`, 1-255), `application_clusters` (list of `ApplicationCluster`, min 1) |
| `ApplicationCluster` | `name` (default `"openshift"`), `namespace` (1-1000), `address` (cluster API URL, 1-2048), `token` (service account token — unrelated to the ArgoCD API token above, this is the *target Kubernetes cluster's* SA token) |
| `ClusterSecretUpdateSpec` | `token` (required, ArgoCD API token), `application_clusters` |
| `ClusterSecretIdentifier` | `token` (required, ArgoCD API token), `app_name`, `chosen_name` |

### Endpoints
| Method | Path | Body/Params | Description |
|---|---|---|---|
| `GET` | `/sizes` | — | List allowed sizes |
| `GET` | `/include-resources` | — | List allowed resource kinds |
| `GET` | `/environments` | — | List allowed environments |
| `POST` | `/` | `ConsumerConfigSpec` | Create consumer config in gitops repo |
| `DELETE` | `/{env}/{name}` | path params | Delete consumer config from gitops repo |
| `POST` | `/cluster-secret` | `ClusterSecretSpec` | Create cluster-secret ArgoCD app |
| `DELETE` | `/cluster-secret` | `ClusterSecretIdentifier` (query) | Delete cluster-secret ArgoCD app |
| `PUT` | `/cluster-secret/{app_name}/{chosen_name}` | `ClusterSecretUpdateSpec` | Edit cluster-secret ArgoCD app |

**Config-driven:**
- `ARGOCD_ALLOWED_ENVS` — from `global_conf.py` (e.g. `["prod"]` or `["prod","dr","int"]`)
- `ARGOCD_ALLOWED_SIZES` — default `["extraLarge","large","medium","small"]`
- `ARGOCD_ALLOWED_RESOURCES` — default `["ExternalSecret","ConfigMap","Deployment"]`
- `ARGOCD_GITOPS_DEFAULT_BRANCH` — default `"master"`
- `ARGOCD_APPLICATION_SET_TIMEOUT` — default 300s

---

## Common patterns across all modules

- **Happy path response:** `SuccessResponse(status="successful")` from `app/v1/response_schemas.py`
- **Error response:** `JSONResponse(ExceptionResponse(stdout=..., status="Failed", status_code=...).dict(), status_code=...)`
- **Rollback on bare except:** call delete/cleanup before re-raise
- **`_handle_response(response)`:** raises `HTTPException` when `status_code > 299`
- **`admin_user` / `admin_group` pattern:** `model_validator` enforces at-least-one; routes branch on which is set
