# SonarQube module — developer notes

## How the client is built

Unlike other modules that share a single pre-built httpx client, `routes.py:_build_client()` constructs a fresh client **per request** from the `consumer_name` field in the payload:

```
https://{consumer_name}.sonarqube.{DOMAIN_SUFFIX}
```

Auth always uses the global credentials from `.env` (`SONARQUBE_USERNAME` / `SONARQUBE_PASSWORD`).
`main.py` therefore calls `get_v1_sonarqube_router()` with no arguments.

Per-consumer routing works end-to-end via a wildcard DNS record + CoreDNS rewrite + Ingress rule
(same mechanism as ArgoCD's per-consumer wildcard — see `app/v1/argocd/CLAUDE.md`'s CoreDNS
section for the full explanation). As with ArgoCD, this is **one shared SonarQube instance behind
the wildcard**, not real per-consumer isolation — enough to exercise `_build_client()`'s live code
path end-to-end, nothing more.

**Gotcha if this Ingress config is ever touched again:** the vendored chart's
`charts/sonarqube/templates/ingress.yaml` template must **quote** the wildcard host value
(`{{ printf "%s" .name | quote }}`) — a bare leading `*` in YAML is an alias-reference token, not
a literal string, and unquoted it broke Helm's YAML→JSON conversion, sending the whole
`sonarqube` ArgoCD Application into a permanent `ComparisonError` while silently continuing to
serve the old Ingress.

## Schema — consumer-name fields use a DNS-label pattern

`SonarQubeConsumerSpec.name` and `GroupSpec.consumer_name` both become the DNS label in
`https://{consumer_name}.sonarqube.{DOMAIN_SUFFIX}`, so both are constrained by
`_DNS_LABEL_PATTERN` (`^[a-z0-9]([-a-z0-9]*[a-z0-9])?$` — RFC 1123 DNS label: lowercase
alphanumeric and hyphens, must start/end with an alphanumeric), max 63 chars (the real
Kubernetes/DNS label limit) — not the looser identifier pattern used elsewhere. `GroupSpec.name`
(the actual SonarQube group name, not a hostname) dropped its `pattern` entirely — group names
are left unconstrained, matching `.claude/skills/schema_update_best_practice.md`'s RBAC guidance.

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

Total: **12 POST calls** to SonarQube per group creation. On any failure: automatic rollback via
`delete_group`.

**Rollback covers permission-assignment failures too, not just `create_group` itself.**
`_handle_response` turns *any* non-2xx SonarQube response into an `HTTPException` — so a naive
`except HTTPException: no rollback` branch would skip cleanup for the far more likely real-world
failure (a permission call failing after the group was already created), leaving an orphaned,
partially-configured group. `routes.py` tracks a `created` flag set right after `create_group()`
succeeds: the `except HTTPException` branch now rolls back only when `created` is `True` (an
`HTTPException` from `create_group` itself, e.g. "group already exists", still correctly skips
rollback since nothing new was created). The bare `except:` branch (unexpected/non-HTTPException
errors) rolls back unconditionally regardless of which step failed, as before.

## Sizes — `GET /sizes`

Returns the allowed `size` enum values for consumer configs, sourced from `SONARQUBE_ALLOWED_SIZES`
(`global_conf.py`): `["default", "medium", "big"]`. No external calls.

## Consumer config (GitOps) — `POST/PUT/DELETE /consumer/*`

Each of these writes/updates/deletes `consumers/{name}/config.yaml` in a dedicated Bitbucket repo
via the injected `Git` connector (see `operations.py`: `create_sonarqube_consumer`,
`update_sonarqube_consumer`, `delete_sonarqube_consumer`). Unlike the group routes, `main.py`
constructs this `Git` client once at startup (`GIT_PROJECT_KEY` / `SONARQUBE_AAS_REPO_SLUG` /
`SONARQUBE_GITOPS_DEFAULT_BRANCH`), not per-request. `GIT_PROJECT_KEY` is shared with the argocd
module's own Git client — see `app/v1/argocd/CLAUDE.md` for its current value and history (the
Bitbucket project/repo layout was consolidated at one point; both modules' repos must stay under
the same project key since there's no per-module override).

| Route | Git call | Path |
|---|---|---|
| `POST /consumer/` | `git.add_file` | `consumers/{name}/config.yaml` |
| `PUT /consumer/{name}` | `git.modify_file` | `consumers/{name}/config.yaml` |
| `DELETE /consumer/{name}` | `git.delete_file` | `consumers/{name}/config.yaml` |

`config.yaml` always includes `name`; `plugins_list` (comma-joined) and `size` are only written
when non-default (`size` omits the key entirely when `default`).

`git.delete_file` goes through the connector's SSH `git clone` path rather than the Bearer-token
HTTP path `add_file`/`modify_file` use — this needs the SSH port pairing (`GIT_SSH_PORT` +
ingress-nginx TCP passthrough) and mounted SSH key documented in `app/v1/argocd/CLAUDE.md`
(`DELETE /{env}/{name}` there hits the identical code path); both are fixed and confirmed working.
The Docker image also needs `openssh-client` installed (not just `git`) for any Git-connector
route over SSH — this affects both this module and argocd.

**Known issue (unresolved) — `PUT /consumer/{name}` not yet re-verified live since the library
fix.** The library's `get_file()` (called as a precondition check inside `add_file`/`modify_file`)
used to fetch raw file content via `GET .../browse/{path}?raw=1` with an `Accept:
application/octet-stream` header — Bitbucket Server's `browse` endpoint ignores `raw=1` entirely
and does real content negotiation, so a non-JSON `Accept` header 406s
(`.../raw/{path}` is the correct endpoint for literal bytes and has no such quirk). This only
breaks the **update** path: for create, the file doesn't exist yet so the precondition's metadata
GET already 404s before reaching the broken raw-content call; for update, the file exists so
execution reaches it. Fixed upstream in
[`Platform-Infra-Org/apis-library#13`](https://github.com/Platform-Infra-Org/apis-library/pull/13)
(changed to fetch from `raw/{path}`), shipped in `v1.1.3`, and `requirements.txt` is bumped past
that (`v1.2.1`) — but the fix has **not been re-tested live** against the real Bitbucket instance
since the bump. Don't close [`devops-api#6`](https://github.com/devops-tashtiot/devops-api/issues/6)
on the strength of the version bump alone — confirm `PUT /consumer/{name}` actually succeeds
live first.

### Route-shadowing — `consumer` is a reserved `consumer_name`

`DELETE /{consumer_name}/{name}` (group delete) and `DELETE /consumer/{name}` (consumer-config
delete) are both two-segment paths under the same HTTP method. FastAPI/Starlette matches routes
in **registration order** — `/consumer/*` routes are registered before the generic
`/{consumer_name}/{name}` wildcard in `routes.py` specifically so `DELETE /consumer/{name}`
resolves correctly. **Residual constraint:** a real SonarQube tenant/consumer literally named
`consumer` can never have its group deleted via `DELETE /{consumer_name}/{name}` — that request
will always match the consumer-config delete route instead, since the literal path segment wins.
Treat `consumer` as a reserved `consumer_name`; not worth redesigning the URL scheme for.

## Config fields (`conf.py`)

| Field | Default | Description |
|---|---|---|
| `SONARQUBE_ENDPOINT` | `/api` | SonarQube Web API base path |
| `SONARQUBE_ADMIN_TEMPLATE_NAME` | `Default template` | Permission template name |
| `SONARQUBE_GLOBAL_PERMISSIONS` | see above | Overridable via `.env` |
| `SONARQUBE_TEMPLATE_PERMISSIONS` | see above | Overridable via `.env` |

Global credentials (`SONARQUBE_USERNAME`, `SONARQUBE_PASSWORD`) and `DOMAIN_SUFFIX` live in `global_conf.py`.

`SONARQUBE_SCHEME`/`SONARQUBE_PORT` fields do not exist here (and shouldn't be re-added without
wiring): `_build_client()` hardcodes `https://{consumer_name}.sonarqube.{DOMAIN_SUFFIX}` — a
config field for scheme/port would need to actually be read inside `_build_client()` to have any
effect (same dead-config trap `ARGOCD_SCHEME`/`ARGOCD_PORT` fell into in
`app/v1/argocd/conf.py`).

## Testing

Tests mock `BaseAPI` via an autouse fixture in `conftest.py` — `patch_base_api` patches `app.v1.sonarqube.routes.BaseAPI` so `_build_client()` returns the shared mock without making real HTTP calls. `mock_git` (also in `conftest.py`) covers the consumer-config routes the same way.

- `test_sonarqube_routes.py` — unit tests (mocked) for all 6 routes: group create/delete
  (including the rollback-on-permission-failure regression test above and a hostname regression
  test on `_build_client`'s exact per-consumer URL), `GET /sizes`, `POST/PUT/DELETE /consumer/*`.
- `test_sonarqube_schema.py` — pydantic validation edge cases for `GroupSpec`,
  `SonarQubeConsumerSpec`, and `SonarQubeConsumerUpdateSpec` (including the plugin-entry
  comma/quote validator and exact `max_length` boundaries).
- `test_sonarqube_group_e2e.py` — real e2e: group create/delete against a live SonarQube instance.
  Uses a `yield`-based `clean_group` fixture (not a plain pre-test call) so a failed assertion
  mid-test can't leave a real leftover group behind — same pattern as Bitbucket's e2e cleanup, see
  `app/v1/bitbucket/CLAUDE.md`.
- `test_sonarqube_consumer_e2e.py` — real e2e: consumer config create/update/delete against a
  live Bitbucket GitOps repo, plus `GET /sizes`. Its module-scoped setup fixture creates the
  GitOps project/repo idempotently if missing and never tears them down (shared platform
  infrastructure, not disposable test fixtures). Per-test cleanup uses the same `yield`-based
  `clean_consumer_config` fixture pattern as `test_sonarqube_group_e2e.py`.

Note every mutating route in this app (`bitbucket`, `confluence`, `jira`, `artifactory`,
`argocd`, `sonarqube`, `dns`, `haproxy`, `chat`) requires the `{"metadata": {...}, "spec": {...}}`
request wrapper, not a flat body — a flat payload 422s on Pydantic validation before the route
body executes.
