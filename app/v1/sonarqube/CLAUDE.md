# SonarQube module — developer notes

## How the client is built

Unlike other modules that share a single pre-built httpx client, `routes.py:_build_client()` constructs a fresh client **per request** from the `consumer_name` field in the payload:

```
https://{consumer_name}.sonarqube.{DOMAIN_SUFFIX}
```

Auth always uses the global credentials from `.env` (`SONARQUBE_USERNAME` / `SONARQUBE_PASSWORD`).  
`main.py` therefore calls `get_v1_sonarqube_router()` with no arguments.

### Correction (2026-07-13) — group create/delete is currently broken live too

The earlier live-check pass on this module (see git history) reported group create/delete as
"already covered, working" based on the pre-existing `test_sonarqube_group_e2e.py` file
existing — **that test was never actually re-executed against the live cluster in that pass**,
only read as a reference pattern. Investigating the ArgoCD module surfaced the same class of
bug here: `_build_client(consumer_name)` builds `https://{consumer_name}.sonarqube.{DOMAIN_SUFFIX}`,
but **no wildcard DNS record exists** for `*.sonarqube.devopstashtiot.page` — only the bare
`sonarqube.devopstashtiot.page` resolves (confirmed via `dig @1.1.1.1`). Live-checked directly:
`POST /api/devops/v1/sonarqube/` with `consumer_name: "netanel"` (the test's own fixture value)
returns `500 Internal Server Error` — the DNS lookup fails inside the SonarQube client's first
HTTP call, which isn't an `HTTPException` so it isn't caught and formatted by the route's
`except HTTPException` handler, surfacing as a bare 500 instead.

This is the same root cause documented in `app/v1/argocd/CLAUDE.md` (`_build_argocd` has the
identical hostname pattern and the identical gap) — a wildcard DNS record (and possibly a
matching Ingress rule) for per-consumer subdomains was never provisioned for either
"-as-a-service" feature. Not a devops-api code bug; `test_sonarqube_group_e2e.py` is correct and
will pass once the DNS gap is fixed.

## SonarQube REST API calls

### Create group — `POST /api/user_groups/create`

```
POST /api/user_groups/create?name={name}
→ 200, JSON body with group details
```

### Delete group — `POST /api/user_groups/delete`

```
POST /api/user_groups/delete?name={name}
→ 204
```

Note: SonarQube uses `POST` for delete, not `DELETE`.

### Assign global permissions — `POST /api/permissions/add_group`

Called once per permission in `SONARQUBE_GLOBAL_PERMISSIONS`:

```
POST /api/permissions/add_group?groupName={name}&permission={permission}
→ 204
```

Default permissions granted: `admin`, `gateadmin`, `profileadmin`, `provisioning`, `scan`.

### Assign template permissions — `POST /api/permissions/add_group_to_template`

Called once per permission in `SONARQUBE_TEMPLATE_PERMISSIONS`:

```
POST /api/permissions/add_group_to_template?groupName={name}&templateName={template}&permission={permission}
→ 204
```

Default template: `Default template` (set via `SONARQUBE_ADMIN_TEMPLATE_NAME`).  
Default permissions granted: `user`, `codeviewer`, `issueadmin`, `securityhotspotadmin`, `admin`, `scan`.

## Create flow (POST /)

```
create_group → assign_global_permissions (×5) → assign_template_permissions (×6)
```

Total: **12 POST calls** to SonarQube per group creation.  
On any failure: automatic rollback via `delete_group`.

## Sizes — `GET /sizes`

Returns the allowed `size` enum values for consumer configs, sourced live from
`SONARQUBE_ALLOWED_SIZES` (`global_conf.py`): `["default", "medium", "big"]`. Confirmed live —
`GET /api/devops/v1/sonarqube/sizes` returns `200 ["default","medium","big"]`. No external calls.

## Consumer config (GitOps) — `POST/PUT/DELETE /consumer/*`

Each of these writes/updates/deletes `consumers/{name}/config.yaml` in a dedicated Bitbucket
repo via the injected `Git` connector (see `operations.py`: `create_sonarqube_consumer`,
`update_sonarqube_consumer`, `delete_sonarqube_consumer`). Unlike the group routes, `main.py`
constructs this `Git` client once at startup (`GIT_PROJECT_KEY` / `SONARQUBE_AAS_REPO_SLUG` /
`SONARQUBE_GITOPS_DEFAULT_BRANCH`), not per-request.

| Route | Git call | Path |
|---|---|---|
| `POST /consumer/` | `git.add_file` | `consumers/{name}/config.yaml` |
| `PUT /consumer/{name}` | `git.update_file` | `consumers/{name}/config.yaml` |
| `DELETE /consumer/{name}` | `git.delete_file` | `consumers/{name}/config.yaml` |

`config.yaml` always includes `name`; `plugins_list` (comma-joined) and `size` are only written
when non-default (`size` omits the key entirely when `default`).

### Fixed bug — `DELETE /consumer/{name}` was unreachable (route-shadowing)

`DELETE /{consumer_name}/{name}` (group delete) and `DELETE /consumer/{name}` (consumer-config
delete) are both two-segment paths under the same HTTP method. FastAPI/Starlette matches routes
in **registration order**, and the group-delete route was registered first — so every call to
`DELETE /consumer/{name}` was actually being routed to group-delete with
`consumer_name="consumer"`, silently trying to delete a SonarQube group on a tenant literally
named `consumer` instead of deleting the GitOps config file. Caught via a unit test asserting
`mock_git.delete_file` was called and finding it never was. **Fixed** by registering the
`/consumer/*` routes before the generic `/{consumer_name}/{name}` wildcard in `routes.py`.

**Residual constraint**: a real SonarQube tenant/consumer literally named `consumer` still can't
have its group deleted via `DELETE /{consumer_name}/{name}` — that request will always match
`DELETE /consumer/{name}` (consumer-config delete) instead, since the literal segment wins.
Considered out of scope to redesign the URL scheme for; treat `consumer` as a reserved
`consumer_name`.

### Fixed bug — missing `openssh-client` in the Docker image broke every Git-connector route

Live-checked after fixing the route-shadowing bug above: all three `/consumer/*` routes still
failed with `ssh: not found` — `GitClient` shells out to `git clone ssh://...` (not the REST
content API), and the devops-api `Dockerfile` only installed `git` via apt, never
`openssh-client`. This affected every module using the `Git` connector over SSH (also
`argocd`), not just SonarQube. **Fixed** by adding `openssh-client` to the Dockerfile's
`apt-get install` line.

### Live environment note — GitOps repo did not exist

Live-checked directly against the real Bitbucket instance (2026-07-13): the configured
`GIT_PROJECT_KEY` (`ARGO`) and `SONARQUBE_AAS_REPO_SLUG` (`sonarqube-as-a-service`) repo did
**not** exist yet — only Bitbucket project `NATI` existed, and no repo named
`sonarqube-as-a-service` existed anywhere. This meant all three consumer routes were previously
non-functional against the real cluster (not a code bug — the GitOps prerequisite was simply
never provisioned). `tests/v1/sonarqube/test_sonarqube_consumer_e2e.py`'s module-scoped setup
fixture now creates the project/repo idempotently if missing (and leaves them in place — they
are shared platform infrastructure, not disposable test fixtures) as a side effect of adding e2e
coverage.

### Known live blockers — NOT fixed, out of scope for this module (2026-07-13)

Even after the route-shadowing fix and the `openssh-client` Dockerfile fix above, all three
`/consumer/*` routes **still fail live** for two further reasons, both outside `devops-api`'s
own repo:

1. **No SSH key is mounted in the pod at all.** `GIT_SSH_KEY_PATH=/root/.ssh/id_ed25519`
   (`devtools-definition/devtools/devops-api/values.yaml`) points at a path with no backing
   Secret/volumeMount anywhere in the chart — confirmed live: `Identity file
   /root/.ssh/id_ed25519 not accessible: No such file or directory`. A real SSH keypair needs
   generating, the public key registered against the `sonarqube-as-a-service` repo (or the
   `svc-devops-tashtiot` account) in Bitbucket, the private key mounted as a k8s Secret (this
   platform uses external-secrets-operator for this pattern elsewhere), and a volumeMount added
   to the devops-api chart.
2. **The pinned `tashtiot-apis-library` wheel is stale relative to its own source.** The
   library's `GitClient.__init__` (`connectors/git/client.py:104-110`, local checkout at
   `~/devops/tashtiot-apis/apis-library`) already has a comment describing and fixing exactly
   this bug — stripping `http://` before deriving `ssh_host` so it doesn't become the literal
   string `"http"` — but `devops-api/requirements.txt` pins
   `tashtiot-apis-library @ https://github.com/Platform-Infra-Org/apis-library/releases/download/0.1.0/...whl`,
   an **immutable GitHub release asset** for tag `0.1.0` that predates this fix (same version
   number was never bumped after the fix was written, so the fixed source and the published
   wheel share a tag but not content). Confirmed live: `ssh://git@http::7995/...` — literal
   `"http"` as hostname. Fixing this needs a new tagged release of `apis-library` with a real
   wheel upload, then bumping `devops-api/requirements.txt` to that new tag.

Both are real, multi-repo infrastructure/release gaps, not bugs in this module's own code — left
undone pending an explicit decision on scope. `test_sonarqube_consumer_e2e.py` is written
correctly against the intended behavior and will pass once both are resolved; today it fails
live at the `POST`/`PUT`/`DELETE /consumer/*` steps for the reasons above.

## Config fields (`conf.py`)

| Field | Default | Description |
|---|---|---|
| `SONARQUBE_ENDPOINT` | `/api` | SonarQube Web API base path |
| `SONARQUBE_ADMIN_TEMPLATE_NAME` | `Default template` | Permission template name |
| `SONARQUBE_GLOBAL_PERMISSIONS` | see above | Overridable via `.env` |
| `SONARQUBE_TEMPLATE_PERMISSIONS` | see above | Overridable via `.env` |

Global credentials (`SONARQUBE_USERNAME`, `SONARQUBE_PASSWORD`) and `DOMAIN_SUFFIX` live in `global_conf.py`.

`SONARQUBE_SCHEME`/`SONARQUBE_PORT` fields existed here at one point but were removed
(2026-07-14) — `_build_client()` (`routes.py`) hardcodes `https://{consumer_name}.sonarqube.
{DOMAIN_SUFFIX}` and never read either field, so they had no effect regardless of what they were
set to. Same dead-config pattern as `ARGOCD_SCHEME`/`ARGOCD_PORT` in
`app/v1/argocd/conf.py` (also removed). If per-scheme/port overrides are ever actually needed
(e.g. for local dev against `docker-compose.sonarqube.yaml`), they'd need to be wired into
`_build_client()` itself, not just declared in `conf.py`.

## Local dev

```bash
docker compose -f ../docker-compose.sonarqube.yaml up -d
# SonarQube at http://localhost:9000  user: admin  pass: SonarqubeDevops1!
```

## Testing

Tests mock `BaseAPI` via an autouse fixture in `conftest.py` — `patch_base_api` patches `app.v1.sonarqube.routes.BaseAPI` so `_build_client()` returns the shared mock without making real HTTP calls. `mock_git` (also in `conftest.py`) covers the consumer-config routes the same way.

- `test_sonarqube_routes.py` — unit tests (mocked) for all 6 routes: group create/delete, `GET /sizes`, `POST/PUT/DELETE /consumer/*`.
- `test_sonarqube_schema.py` — pydantic validation edge cases.
- `test_sonarqube_group_e2e.py` — real e2e: group create/delete against a live SonarQube instance.
- `test_sonarqube_consumer_e2e.py` — real e2e: consumer config create/update/delete against a live Bitbucket GitOps repo, plus `GET /sizes`. Its module-scoped setup fixture creates the `ARGO` project / `sonarqube-as-a-service` repo if missing (see "Live environment note" above) and never tears them down.
