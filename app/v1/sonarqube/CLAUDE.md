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
"-as-a-service" feature. Not a devops-api code bug.

**Correction (2026-07-14) — `test_sonarqube_group_e2e.py` was not actually correct as-is.**
The statement above ("will pass once the DNS gap is fixed") was wrong: the test's `POST /`
call sent a flat `{"consumer_name": ..., "name": ...}` body, but the route's
`payload: SonarQubeGroupRequest` is an `OperationRequest` subclass — every mutating route in
this whole app (`bitbucket`, `confluence`, `jira`, `artifactory`, `argocd`, `sonarqube`, `dns`,
`haproxy`, `chat`) requires the `{"metadata": {...}, "spec": {...}}` wrapper, not a flat body.
The flat payload 422s on Pydantic validation *before* the route body (and therefore the
DNS-dependent `_build_client` call) ever executes — confirmed live:
`{"detail":[{"type":"missing","loc":["body","metadata"],...},{"type":"missing","loc":["body","spec"],...}]}`.
Fixed the test to send `{"metadata": {...}, "spec": {"consumer_name": ..., "name": ...}}` (same
shape `test_sonarqube_consumer_e2e.py` already uses). Confirmed live: the corrected payload
clears validation and now reaches the DNS-dependent code, surfacing the *other*, still-open
gap above (`500 Internal Server Error`) — so both issues are real and independent; fixing the
DNS gap alone would not have been sufficient, and this test would have kept 422ing forever.

## Fixed (2026-07-20) — per-consumer wildcard DNS/Ingress gap closed for group routes

The gap described just above (`POST /`, `DELETE /{consumer_name}/{name}` 500ing because no
DNS record existed for `*.sonarqube.devopstashtiot.page`) is now closed, mirroring the same
workaround already in place for ArgoCD's per-consumer wildcard:

1. **Cloudflare**: a wildcard DNS record `*.sonarqube.devopstashtiot.page` (proxied) was added.
2. **In-cluster CoreDNS** (`kube-system/coredns` ConfigMap, `kubectl`-applied, not GitOps-tracked
   — same as the other 7 rewrite rules): `rewrite name regex (.*)\.sonarqube\.devopstashtiot\.page
   ingress-nginx-controller.ingress-nginx.svc.cluster.local answer auto`. Routed through
   `ingress-nginx-controller` (not straight to the backend Service, which is plain HTTP only on
   `9000/TCP`) to keep the real Cloudflare Origin Cert — same reasoning as every other tool's
   rewrite rule in this file's ArgoCD counterpart.
3. **`devtools-provision/devtools/sonarqube/values.yaml`**: added a second `ingress.hosts` entry,
   `"*.sonarqube.devopstashtiot.page"`, so ingress-nginx actually has a rule to route the wildcard
   host to (a CoreDNS rewrite alone doesn't create routing — nginx 404s on any host it has no
   `Ingress` rule for).

**Real bug hit and fixed along the way**: adding the wildcard host value broke Helm templating.
The vendored chart's `charts/sonarqube/templates/ingress.yaml` rendered `host: {{ printf "%s"
.name }}` unquoted — for the existing plain hostname this was harmless, but
`*.sonarqube.devopstashtiot.page` rendered as `host: *.sonarqube.devopstashtiot.page`, and a bare
leading `*` in YAml is an alias-reference token, not a literal string, so Helm's own YAML→JSON
conversion failed: `error converting YAML to JSON: yaml: line 25: did not find expected
alphabetic or numeric character`. Confirmed live: ArgoCD's `sonarqube` Application went to a
permanent `ComparisonError` and silently kept serving the old, unsynced Ingress. Fixed by
quoting the templated value (`{{ printf "%s" .name | quote }}`) — verified locally with `helm
template` before re-pushing, then confirmed live: `ArgoCD` synced cleanly and the Ingress now
lists both hosts.

**Verified live end-to-end**: `python3 -c "import socket; socket.gethostbyname(...)"` from
inside the `devops-api` pod resolves `netanel.sonarqube.devopstashtiot.page` to
`ingress-nginx-controller`'s ClusterIP, and a direct HTTPS request to it returns a real `200
{"status":"UP"}` from the one shared SonarQube instance. Re-ran
`test_create_and_delete_group_full_flow` (previously blocked by this gap) against the live
cluster: **passes** — group create, both permission sets, and delete all confirmed against the
real SonarQube API directly, not just devops-api's response.

Same caveat as ArgoCD's equivalent wildcard: this is **one shared instance behind the wildcard**,
not real per-consumer isolation — good enough to exercise `_build_client()`'s live code path
end-to-end, nothing more.

## Fixed (2026-07-21) — rollback never fired for permission-assignment failures

`POST /`'s rollback logic previously read the wrong exception type for the failure it's most
likely to actually see. `routes.py`'s `create_new_group` had one `try` wrapping
`create_group` → `assign_global_permissions` → `assign_template_permissions`, with `except
HTTPException` returning an error response and a separate bare `except:` doing the rollback
(`delete_group`). But `_handle_response` (`operations.py:15-22`) turns *any* non-2xx SonarQube
response into an `HTTPException` — so a failure in either permission-assignment step (the far
more likely real-world failure than `create_group` itself failing) landed in the `except
HTTPException` branch, which never rolled back. Net effect: a group could be created on
SonarQube's side with 0-4 of 5 global permissions and no template permissions, reported to the
caller as `"Failed"`, with no cleanup — an orphaned, partially-configured group.

Fixed with a `created` flag set immediately after `create_group()` succeeds: the `except
HTTPException` branch now rolls back only when `created` is `True` (i.e. the failure happened
in a permission step, not in `create_group` itself — an HTTPException from `create_group` itself,
e.g. "group already exists", still correctly skips rollback since nothing new was created). The
bare `except:` branch (unexpected/non-HTTPException errors, e.g. a raw network exception) is
unchanged — it already rolled back unconditionally regardless of which step failed, which was
correct and is covered by the pre-existing `test_create_group_unexpected_error_triggers_rollback`.

New regression test: `test_create_group_permission_failure_triggers_rollback`
(`tests/v1/sonarqube/test_sonarqube_routes.py`) — create succeeds, the first global-permission
call 500s, asserts the rollback delete call fires.

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
| `PUT /consumer/{name}` | `git.modify_file` | `consumers/{name}/config.yaml` |
| `DELETE /consumer/{name}` | `git.delete_file` | `consumers/{name}/config.yaml` |

`config.yaml` always includes `name`; `plugins_list` (comma-joined) and `size` are only written
when non-default (`size` omits the key entirely when `default`).

### Fixed bug (2026-07-14) — `PUT /consumer/{name}` called a method that doesn't exist

`update_sonarqube_consumer()` called `git.update_file(...)` — **`update_file` is not a real
method on `tashtiot_apis_library`'s `Git` class** (the real name is `modify_file`; confirmed by
reading `connectors/git/service.py`'s method list directly, both at `0.1.0` and `v1.1.2`). This
raised a bare `AttributeError` on every call, caught by the generic `except Exception: raise` and
surfacing to the caller as an undecorated `500 Internal Server Error` with no detail — confirmed
live (2026-07-14) hitting the real deployed API. The bug was invisible to the existing unit test
suite because `tests/v1/sonarqube/conftest.py`'s `mock_git` fixture also mocked
`git.update_file` — the mock matched the bug instead of the real library's interface, so
`test_update_consumer_calls_update_file_with_expected_path_and_content` passed regardless of
whether the real method existed. Fixed both the operation (`git.modify_file`) and the mock/test
name to match. This class of bug — a mock that silently matches a wrong method name — can only be
caught by testing against the real library/service, not by a more careful mock; worth keeping in
mind for any other operation using `git.*` that's never been live-tested.

### Live-confirmed (2026-07-14) — `DELETE /consumer/{name}` times out

Same underlying issue as the argocd module's `DELETE /{env}/{name}` (see
`app/v1/argocd/CLAUDE.md`, which has the full root-cause) — `delete_sonarqube_consumer()` calls
`git.delete_file(...)`, which internally does a full `git clone` over SSH rather than the
Bearer-token HTTP path `add_file`/`modify_file` use. Confirmed live: the request hangs and the
test client's 30s timeout is hit (`httpx.ReadTimeout`).

Root-caused the same day (see `app/v1/argocd/CLAUDE.md` for the full writeup): two stacked bugs —
the library hardcodes SSH port `7995`, which isn't Bitbucket's real SSH port here (`7999`), *and*
that hostname resolves in-cluster to `ingress-nginx-controller`, which has no listener on any SSH
port at all (HTTP(S)-only router), so the connection silently hangs rather than failing fast.
Fixed both ways: an immediate `ingress-nginx` TCP-passthrough workaround (`7995` → real `7999`,
see `clusters-provision/clusters/ingress-nginx/values.yaml`, marked temporary) and a real upstream
fix, [`Platform-Infra-Org/apis-library#12`](https://github.com/Platform-Infra-Org/apis-library/pull/12),
adding an `ssh_port` override to the library itself.

**Update, same day:** with the TCP-passthrough workaround live, this route's error shape changed
from a hang to an immediate `Permission denied (publickey)` — no SSH key was ever actually mounted
into the pod (`GIT_SSH_KEY_PATH` was configured but pointed at nothing). Fixed by generating a
keypair, registering it with Bitbucket, and mounting it via `devtools-definition`'s
`extraSecretMounts` — full details in `app/v1/argocd/CLAUDE.md`'s matching entry (including a
second bug found along the way: the private key was stored in SSM missing its trailing newline,
which OpenSSH's parser requires — `error in libcrypto` until that was fixed too), since it's the
exact same key/mount serving both modules.

**Re-verified live — `DELETE /consumer/{name}` (via `test_create_consumer_config_default_size_omits_size_key`)
passes.** Fully fixed, confirmed.

### Root-caused (2026-07-14) — `PUT /consumer/{name}` 406s: `apis-library`'s raw-content fetch hits the wrong Bitbucket endpoint

`test_create_update_delete_consumer_config_full_flow` fails on `PUT /consumer/{name}` — not
DELETE, not SSH-related, not the `git.update_file`→`git.modify_file` typo (already fixed) — with
`406 Not Acceptable` from Bitbucket itself (`"Exception in SonarQube. Bitbucket error: 406"`).
CREATE and the raw-Bitbucket content verification both pass fine in the same test.

Root cause is entirely inside `tashtiot_apis_library`, not this module's code.
`GitClient.get_file()` fetches raw file content via
`GET .../browse/{path}?raw=1` with an `Accept: application/octet-stream` header. Confirmed live
against the real Bitbucket Server instance, independent of devops-api's own code/auth/ingress
(reproduced hitting `bitbucket-0`'s pod directly):

```
GET .../browse/{path}?at=master&raw=1   Accept: application/octet-stream   ->  406 Not Acceptable
GET .../browse/{path}?at=master&raw=1   Accept: application/json           ->  200, but {"lines":[...]} JSON, not raw bytes
GET .../raw/{path}?at=master            Accept: application/octet-stream   ->  200, literal raw bytes
```

Bitbucket Server's `browse` endpoint **ignores `raw=1` entirely** (always returns its normal
JSON-wrapped-lines representation) and does real content negotiation there, so a non-JSON
`Accept` header 406s. The dedicated `raw/{path}` endpoint is the correct way to fetch literal
bytes and has no such quirk.

This only breaks the **update** path, not create: both `add_file()` and `modify_file()` call
`get_file()` as a precondition check first. For create, the file doesn't exist yet, so the
*metadata* GET (the first of `get_file()`'s two calls) already 404s — execution never reaches
the broken raw-content call. For update, the file already exists, so the metadata GET succeeds
and execution *does* reach the broken raw-content call, which 406s.

**Real fix (upstream)**: opened
[`Platform-Infra-Org/apis-library#13`](https://github.com/Platform-Infra-Org/apis-library/pull/13)
— changes `get_file()` to fetch content from `raw/{path}` instead of `browse/{path}?raw=1`. All
196 pre-existing tests + 2 new regression tests pass, `ruff` clean.
**STATUS: PR OPEN, NOT YET MERGED.**

**No workaround exists on devops-api's side** — `Git`/`GitClient` internals are off-limits per
this repo's connector-usage rule, so `PUT /consumer/{name}` remains genuinely broken live until
the library fix is merged, released, and `devops-api/requirements.txt` is bumped to it. Tracked
in [`devops-api#6`](https://github.com/devops-tashtiot/devops-api/issues/6).

**2026-07-19 — fix pulled in, `requirements.txt` bumped to `v1.2.1`.** `apis-library#13` merged
and shipped in `v1.1.3`, well before `v1.2.1`, so this bump includes it. This closes the
code-level gap only — `devops-api#6` is being left **open** until `PUT /consumer/{name}` is
actually re-tested live against the real Bitbucket instance (this bump was not pushed/deployed
as part of making this note); don't close that issue on the strength of a version bump alone.

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
`app/v1/argocd/conf.py` (also removed). If per-scheme/port overrides are ever actually needed,
they'd need to be wired into `_build_client()` itself, not just declared in `conf.py`.

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
  mid-test can't leave a real leftover group behind — same fix as Bitbucket's
  E2ETEST/E2EREPOTEST leftover-project bug, see `app/v1/bitbucket/CLAUDE.md`.
- `test_sonarqube_consumer_e2e.py` — real e2e: consumer config create/update/delete against a live Bitbucket GitOps repo, plus `GET /sizes`. Its module-scoped setup fixture creates the `ARGO` project / `sonarqube-as-a-service` repo if missing (see "Live environment note" above) and never tears them down. Per-test cleanup uses the same `yield`-based `clean_consumer_config` fixture pattern as `test_sonarqube_group_e2e.py`.
