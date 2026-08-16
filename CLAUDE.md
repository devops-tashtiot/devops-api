# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Dev bootstrap (first time on a machine)

Package management is `uv`-based (Python 3.10; see `.python-version`). `pyproject.toml`
pins `tashtiot-apis-library` directly to a GitHub-release wheel URL — no separate library
install step is needed.

```bash
# 1. Install all deps (runtime + dev/test group) into .venv
uv sync --group dev

# 2. Edit .env directly (do NOT copy .env.example — .env is the live config file)
# Minimum for local dev — disable ArgoCD if you have no SSH key:
#   ARGOCD_ENABLE_API=false
# Confluence local stack: CONFLUENCE_API_URL=http://localhost:8090, user admin, pass 12345678
# Bitbucket  local stack: BITBUCKET_API_URL=http://localhost:7990,   user admin, pass 12345678
# SonarQube  local stack: SONARQUBE_API_URL=http://localhost:9000,   user admin, pass SonarqubeDevops1!
# ArgoCD allowed envs: ARGOCD_ALLOWED_ENVS=["prod"] for network A, ["prod","dr","int"] for network B

# 3. Start the server (from this directory)
uv run uvicorn app.main:create_app --factory --port 5000
```

To develop against a local checkout of the library instead of the pinned wheel URL, add a
`[tool.uv.sources]` override pointing at it (same pattern as `example-api`'s
`pyproject.toml`):
```toml
[tool.uv.sources]
tashtiot-apis-library = { path = "../apis-library", editable = true }
```

**Also one-time**: `git config core.hooksPath .githooks` — activates a `pre-push` hook that
refuses any push whose remote URL contains `github.com` (Bitbucket is the source of truth; see
"Bitbucket is the source of truth for this repo" below). This is a local convenience check only,
bypassable with `--no-verify` or by skipping this step — the real enforcement is GitHub branch
protection.

## Commands

```bash
# Install dependencies (runtime + dev/test group)
uv sync --group dev

# Run the dev server
uv run uvicorn app.main:create_app --factory --reload --port 5000

# Run all tests
uv run pytest

# Run a specific test suite
uv run pytest tests/v1/dns -v
uv run pytest tests/v1/sonarqube -v
uv run pytest tests/v2/dns -v

# Run a single test file
uv run pytest tests/v1/sonarqube/test_sonarqube_routes.py -v

# Run with coverage
uv run pytest --cov=app --cov-report=term-missing
```

## Architecture

The app is a FastAPI service that orchestrates DNS records, HAProxy load-balancer configs, and chat messages by delegating to external platforms (AWX, ArgoCD, Vault, Bitbucket/Git). All external client objects are constructed once in `app/main.py:create_app()` and passed into router factories as arguments — there is no global state or DI framework.

**Entry point:** `app/main.py` — `create_app()` builds the FastAPI app via `tashtiot_apis_library.general_create_app()`, instantiates external service clients, and mounts routers.

**Module layout** — every feature under `app/v1/<feature>/` follows this four-file convention:
- `conf.py` — `pydantic-settings` class, reads `.env`; instantiated as `config` at module level
- `schemas.py` — Pydantic request/response models
- `routes.py` — router factory `get_<feature>_router(...)` that closes over injected clients
- `operations.py` / `operation_*.py` — async business logic called by the router

**Configuration** — each module (`global_conf.py`, `v1/dns/conf.py`, `v1/haproxy/conf.py`, `v1/chat/conf.py`) has its own `pydantic-settings` class. All read from `.env` (see `.env.example`). Required fields without defaults must be in `.env` before the app starts (notably `HAPROXY_*`, `ARGOCD_*`, `VAULT_*`).

**Internal library** — `tashtiot-apis-library` (version-pinned in `requirements.txt`) provides `general_create_app`, `BaseAPI`, `Git`, `ArgoCD`, `Vault`, `AWX` connectors, and shared response types like `ArgoOperationResponse` / `ExternalServiceError`. Treat it as a black-box SDK.

**Connector usage rule** — always import and use the high-level service classes (`ArgoCD`, `Git`, `Vault`, `AWX`) from `tashtiot_apis_library`. Never import or instantiate the low-level `*Client` classes (e.g. `ArgoCDClient`, `GitClient`) directly — those are internal implementation details of the library. Each service class is instantiated once in `app/main.py:create_app()` and passed into router factories. See `app/v1/haproxy/operations.py` as the reference pattern for ArgoCD.

### Inbound auth

`app/main.py` builds the app with `general_create_app(enable_auth=True)`. That flag alone
changes nothing: the library's `AuthMiddleware` (protects every route except `/health`,
`/metrics`, `/docs`, `/redoc`, `/openapi.json`, `/static`, `/.well-known`, and probes) only
actually activates when the env var `AUTH_ENABLED=true` **and** exactly one verification-material
source (`AUTH_HS256_SECRET`, `AUTH_PUBLIC_KEY_PEM`/`AUTH_PUBLIC_KEY_PATH`, or
`AUTH_JWKS_URL`/`AUTH_OIDC_ISSUER`) is also set — zero or more than one raises `AuthConfigError`
at startup. These `AUTH_*` vars are read directly by the library's own internal settings object,
not by this app's `global_conf.py`. See `.env.example`'s "Inbound auth" block for the full
variable list and a local-dev token recipe (`gen-auth-material`, a console script the library
installs).

The real identity provider is Keycloak (`rhbk`, deployed via `clusters-provision`/
`clusters-definition` — issuer `https://rhbk.devopstashtiot.page/realms/devtools`). A
`devops-api` client + `devops-api-audience` client scope (audience mapper) exist in that realm
for this purpose — see `clusters-provision/clusters/rhbk/CLAUDE.md` (or `values.yaml`/
`realm-import.yaml`/`provision-oidc-clients-job.yaml`) for how it's provisioned, and
`devtools-definition/devtools/devops-api/values.yaml` for the live `AUTH_*` values actually
deployed.

**Currently disabled** — `AUTH_ENABLED` is `"false"` in the live deployment: every route is open,
no Bearer token required. No confirmed real caller of devops-api ever needed it (only ad-hoc test
tokens exercised it), and it added friction to every e2e suite without a concrete threat it
mitigated. `AUTH_OIDC_ISSUER`/`AUTH_AUDIENCE` are left populated in `devtools-definition` (inert
while disabled) so re-enabling later is just flipping `AUTH_ENABLED` back to `"true"`. The e2e
suites' token-minting helper (`_api_auth_headers()`, previously in
`tests/v1/{argocd,jira,bitbucket,sonarqube}/*_e2e.py`) was removed when auth was disabled; re-add
it (see git history around 2026-07-15 for the pattern) if it's ever turned back on.

**Gotchas worth knowing if re-enabling:**
1. **`AUTH_OIDC_ISSUER` must be the real public hostname**
   (`https://rhbk.devopstashtiot.page/realms/devtools`), not Keycloak's ClusterIP. A token fetched
   by bypassing ingress (hitting the ClusterIP directly) carries `iss:
   http://rhbk.devopstashtiot.page:8080/...` — Keycloak's own fallback with no
   `X-Forwarded-Proto` to trust — and fails verification. Fetch through the real public hostname
   to get the correct `https://` issuer.
2. **Every `*.devopstashtiot.page` hostname devops-api calls out to needs a CoreDNS rewrite
   rule** (see `app/v1/argocd/CLAUDE.md`'s CoreDNS section for the full mechanism). Without one,
   an outbound call — e.g. the JWKS fetch needed on every request to verify a token's signature,
   not just at startup — goes out through real Cloudflare DNS and hits Access's email-OTP wall,
   surfacing as every request 401ing with "Unable to verify token" even with a valid token.
3. **ConfigMap changes don't restart pods.** devops-api's env vars are injected via
   `envFrom: configMapRef` (`devops-api-env`), and Kubernetes does not restart pods when a
   referenced ConfigMap's contents change. After any `devtools-definition` env-value change
   (including `AUTH_*`), either wait for the next `image.tag` bump (forces a new pod) or run
   `kubectl rollout restart deployment/devops-api -n devops-api` manually — ArgoCD showing
   `Synced` is not sufficient by itself; confirm with `env | grep <VAR>` inside the new pod.

**Tests** — `tests/v1/` and `tests/v2/` mirror the app structure. Fixtures (client, mock clients, sample payloads) live in `conftest.py` files at each level. `pytest.ini` sets `pythonpath = .` so imports start from the repo root.

**CI is effectively off on the GitHub side.** `.github/workflows/docker-publish.yml` is fully
**commented out** — Bitbucket is the source of truth for this repo now, GitHub is a read-only
mirror, and running a build/release pipeline against a read-only mirror didn't make sense. Also
still present but dead/vestigial: `.woodpecker/build.yaml` (targets a different registry,
`artifactory.app.com`, and its one step only runs `when: event: tag` with no tag-push in normal
workflow — never trust it). The only *active* pipeline touching this repo's git history at all is
`.woodpecker/mirror-to-github.yml` (see "Bitbucket is the source of truth" below).

**What `docker-publish.yml` used to do**, before being disabled (kept commented out in the file
for reference, not deleted) — on every push to `master` not containing `chore(release):` in the
commit message:
1. Bumped the version via `git-cliff` and wrote `CHANGELOG.md`
2. Committed `chore(release): vX.Y.Z [skip ci]` and created+pushed a matching git tag
3. Built and pushed `ghcr.io/devops-tashtiot/devops-api:vX.Y.Z` (and `:latest`)
4. Cloned `devtools-definition`, `sed`'d the new tag into `devtools/devops-api/values.yaml`,
   committed, and pushed to its `main`

None of that happens automatically anymore — **there is currently no CI path that builds/pushes a
new `devops-api` image or bumps `devtools-definition`'s tag.** If that automation is still
needed, it has to be rebuilt as a Woodpecker pipeline triggered by a Bitbucket push (matching the
pattern `a-woodpecker-plugins` already uses), not re-enabled as a GitHub Actions workflow — a
GitHub Actions push (`secrets.RELEASE_PAT`, an org-level secret on `devops-tashtiot` set up for
this, owner `netanelzucaim`) would work against the current branch protection, but there's no
reason to run CI against the mirror instead of the source of truth.

**Bitbucket is the source of truth for this repo** — push directly into it over HTTPS at
`bitbucket.devopstashtiot.page` (see the top-level `devops/CLAUDE.md`'s "Bitbucket push access"
section for the Cloudflare Access service-token headers needed). `.woodpecker/mirror-to-github.yml`
mirrors every push onward to GitHub with `git push --mirror`. GitHub's `master` branch has push
restrictions enabled (GitHub branch protection API, `restrictions.users: ["netanelzucaim"]`,
`enforce_admins: false`, no required PR/status checks) — only that GitHub account can push to it
directly; every other collaborator is rejected outright. This is a **known-imperfect**
enforcement: it's identity-based, and the same account is used both for the human's own manual
pushes and (once wired up) the mirror pipeline's `github_token` secret, so it can't distinguish
"pushed by automation" from "pushed by hand" — genuine bot-only enforcement would need a
dedicated GitHub App or machine user, deliberately not set up (tried, decided against for now).

**`github-actions[bot]` can't be branch-protection-allowlisted at all**, for the record — confirmed
empirically: GitHub's API silently drops any attempt to add `"github-actions"` (or similar) to a
branch protection rule's `restrictions.apps`; that field is for real installed GitHub Apps, not
the native Actions bot backing the default `secrets.GITHUB_TOKEN`. This is moot while
`docker-publish.yml` is disabled, but matters again if it's ever re-enabled or rebuilt.

---

## Writing tests for a service module

Reference implementation: `tests/v1/sonarqube/` (unit/schema), `tests/v1/bitbucket/` (also has
the e2e file). Every service test suite has four files.

**`conftest.py`** — mock the httpx client, build a throw-away FastAPI app with just that router:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.v1.<service>.routes import get_v1_<service>_router

@pytest.fixture
def mock_<service>_client():
    client = MagicMock()
    ok = MagicMock()
    ok.status_code = 200
    ok.text = ""
    client.post = AsyncMock(return_value=ok)   # also mock .put / .delete if used
    return client

@pytest.fixture
def client(mock_<service>_client):
    app = FastAPI()
    app.include_router(get_v1_<service>_router(mock_<service>_client))
    return TestClient(app)
```

**`test_<service>_routes.py`** — assert status codes, call counts, and exact params:

```python
from app.v1.<service>.conf import config
PREFIX = config.API_PREFIX

def test_create_returns_200(client, mock_<service>_client):
    response = client.post(f"{PREFIX}/", json={"name": "check"})
    assert response.status_code == 200
    assert response.json()["status"] == "successful"

def test_create_calls_all_operations(client, mock_<service>_client):
    client.post(f"{PREFIX}/", json={"name": "check"})
    assert mock_<service>_client.post.call_count == <N>   # one per operation
    endpoints = [c.args[0] for c in mock_<service>_client.post.call_args_list]
    assert any("<expected_endpoint>" in ep for ep in endpoints)
```

**`test_<service>_schema.py`** — pydantic validation edge cases: required fields, empty values,
pattern violations, and **length boundaries at both ends** (e.g. a field with `max_length=15`
gets a test at exactly 15 — valid — and 16 — invalid; don't just test "some long string raises").

**`test_<service>_e2e.py`** (`@pytest.mark.integration`) — the fourth file, hits a **real**
service and a **real** running devops-api, never mocks. Module-scoped fixtures for both clients,
env-var overrides so the same file runs locally or against the cluster:

```python
import os
import httpx
import pytest

SERVICE_URL = os.environ.get("<SERVICE>_URL", "http://localhost:<port>")
API_URL = os.environ.get("API_URL", "http://localhost:5002")
PREFIX = "/api/v1/devops/<service>"


@pytest.fixture(scope="module")
def svc():
    with httpx.Client(base_url=SERVICE_URL, auth=(..., ...), timeout=30.0) as client:
        yield client


@pytest.fixture(scope="module")
def api():
    with httpx.Client(base_url=API_URL, timeout=30.0) as client:
        yield client


@pytest.fixture
def clean_resource(svc):
    # Cleanup via `yield` (not a plain call at the top of each test) so teardown still runs
    # if the test fails partway through — a plain pre-test-only cleanup call once left real
    # E2ETEST/E2EREPOTEST projects stuck in Bitbucket after an unrelated auth failure
    # (see app/v1/bitbucket/CLAUDE.md).
    _delete_if_exists(svc, RESOURCE_KEY)
    yield RESOURCE_KEY
    _delete_if_exists(svc, RESOURCE_KEY)


@pytest.mark.integration
def test_create_and_delete(svc, api, clean_resource):
    r = api.post(f"{PREFIX}/", json={...})
    assert r.status_code == 200, r.text
    # cross-check against the real service directly — never just trust devops-api's response
    ...
```

See "Checking all devtool APIs live against the cluster" below for how to actually *run* this
file against the real cluster (SSM, `kubectl cp`, credentials) — this section is about
structure, that one's about the live-verification workflow.

Never use a real HTTP client in the unit test files (`routes`/`schema`) — always `AsyncMock`,
asserting `call_count` (no operation silently skipped) and exact params via `call_args_list`.

---

## Verifying an API against a real instance

Read credentials from `.env`, then call each endpoint with curl. Confirm the full operation chain and verify final state.

**SonarQube — create group + assign permissions:**

```bash
# 1. Create group
curl -s -u admin:<pass> -X POST "http://localhost:9000/api/user_groups/create?name=<name>" | python3 -m json.tool

# 2. Assign global admin permission (204 = success)
curl -s -u admin:<pass> -X POST "http://localhost:9000/api/permissions/add_group?groupName=<name>&permission=admin" -w "\nHTTP %{http_code}"

# 3. Assign to Default template (204 = success)
curl -s -u admin:<pass> -X POST "http://localhost:9000/api/permissions/add_group_to_template?groupName=<name>&templateName=Default+template&permission=admin" -w "\nHTTP %{http_code}"

# 4. Verify state
curl -s -u admin:<pass> "http://localhost:9000/api/permissions/groups?permission=admin" | python3 -m json.tool
```

Expected: group appears in the `permissions/groups` response with `"permissions": ["admin"]`.

---

## Checking all devtool APIs live against the cluster

When asked to "check all tools" / "check all APIs work" / "check <service> APIs work", this
means verifying the deployed devops-api against the **real** Minikube cluster (not local
docker-compose), for every route in that module — not just spot-checking one endpoint. Follow
this sequence:

1. **Confirm AWS creds are live**: `aws sts get-caller-identity` (profile
   `342831714456_Workload-Admin-PS`, region `il-central-1`). If expired (`RequestExpired`),
   ask the user to refresh — you cannot do this yourself (browser SSO).
2. **Confirm the Minikube EC2 instance and `devtools-rds` are running**
   (`aws ec2 describe-instances` / `aws rds describe-db-instances` on instance
   `i-0a9e2bbdd44475741` / db `devtools-rds`). If either is `stopped`, ask before starting them
   — `devtools-rds` in particular takes several minutes and DB-dependent pods (Bitbucket,
   Confluence, Jira, etc.) will show `Error`/`CrashLoopBackOff` until it's back; they recover
   on their own once RDS is available again, no manual pod restart needed.
3. **SSM into the instance** for every subsequent command: `aws ssm send-command
   --instance-ids i-0a9e2bbdd44475741 --document-name AWS-RunShellScript --parameters
   'commands=["export KUBECONFIG=/root/.kube/config; <cmd>"]'`, then
   `aws ssm get-command-invocation` to read the result. The kubeconfig lives at
   `/root/.kube/config` (SSM runs as root) — plain `kubectl` with no `KUBECONFIG` set fails
   with a `localhost:8080` connection-refused error.
4. **Confirm devops-api's actual deployed image tag** (`kubectl get pods -n devops-api -o
   jsonpath={.items[0].spec.containers[0].image}`) so you know whether you're verifying
   already-pushed code or need to push first.
5. **Exercise every route** via `kubectl exec` into a pod that already has `curl`/`python3`
   (the target service's own pod, e.g. `bitbucket-0`/`jira-0`, works well) hitting devops-api's
   ClusterIP directly (`kubectl get svc -n devops-api` for the IP) — this tests the real code
   path end-to-end, not a mocked unit test. For anything destructive (create/delete), always
   clean up the test artifact afterward and confirm it's actually gone with a raw call to the
   upstream service directly (not just trusting devops-api's response).
6. **Cross-check against the upstream service directly** where relevant — don't just trust
   devops-api's response; verify state changed (or didn't) on the real service. This is how
   several real bugs documented in the module `CLAUDE.md`s were originally found.
7. **Document any bug found** in that module's `CLAUDE.md` per the maintenance rule below,
   as a statement of current behavior, not an investigation transcript.
8. **Write or update a real e2e test** at `tests/v1/<service>/test_<service>_e2e.py` (naming:
   `test_bitbucket_e2e.py`, `test_jira_e2e.py` — no `_project_` in the name) mirroring the
   existing pattern: module-scoped `httpx.Client` fixtures for both the raw service and
   devops-api, env-var overrides so the same file works locally or via
   `kubectl port-forward` + `pytest -m integration`, one test per route/behavior, and cleanup
   of anything created. These hit real services — never mock in this file (unit tests with
   mocks belong in `test_<service>_routes.py` / `test_<service>_schema.py` instead, per
   "Writing tests for a service module" above).
9. **When asked to "run all tests," run them on the EC2 instance** (via the SSM pattern above,
   or a script copied onto the instance/pod), not as a local `pytest` invocation tunneled
   through SSM port-forwarding — that tunnel is unreliable in this environment (works
   intermittently, then fails with a client-side "Plugin with name Port not found" error on
   retries). A local `pytest --collect-only` or `python -m py_compile` for a quick
   syntax/sanity check is fine; actually exercising the live assertions should happen on the
   instance.

### Getting test files (and code changes) onto a live pod

`tests/` is **not** baked into the production image — only `/app` is (confirmed via `COPY
/app /app` in the Dockerfile). This means:

- A fresh/newly-rolled pod has no `/tests` directory at all. `kubectl cp` into a path that
  doesn't exist yet fails (`tar: /tests/v1/<service>: Cannot open: No such file or directory`)
  — always `kubectl exec <pod> -- mkdir -p /tests/v1/<service>` first, then `kubectl cp`.
- There's no `scp`/direct file transfer to the EC2 instance itself in this setup — get local
  files onto the instance by `base64 -w0`-encoding them, `split -b 6000`-ing into chunks (SSM's
  `send-command` parameters have a size limit well under a raw multi-KB payload), appending each
  chunk to a file on the instance across several `send-command` calls (`echo -n "<chunk>" >>
  /tmp/x.b64`), then `base64 -d | tar xzf` to reconstruct, then `kubectl cp` from the instance
  into the pod as normal.

### Testing route/operation changes that haven't been released yet

Editing `app/v1/<service>/*.py` locally and `kubectl cp`-ing it into a running pod does **not**
make the already-running `uvicorn` process pick it up — it already has the old module loaded in
memory, and there's no `--reload` in production. Don't restart the pod/container to force a
reload either — that reverts the filesystem to whatever's baked into the (not-yet-released)
image, throwing away the very files you just copied in.

Instead, launch a **second, temporary `uvicorn` process on an alternate port** (e.g. `5001`)
inside the same container, against the already-`kubectl cp`'d files, and point the e2e test run
at that port instead of the real serving port (`5000`) — this exercises the new code for real,
against real dependencies (real Bitbucket/Jira/etc., real network), without touching or
restarting the pod's actual serving process:

```bash
kubectl exec -n devops-api <pod> -- bash -c \
  'cd / && nohup python3 -c "import uvicorn; from app.main import create_app; \
   uvicorn.run(create_app(), host=\"0.0.0.0\", port=5001)" > /tmp/temp_server.log 2>&1 &'
# ... run tests with API_URL=http://localhost:5001 ...
```

The `devops-api` container has **no `ps`, `pkill`, or `curl`** (do not assume they exist).
Work around this:
- **HTTP checks**: use `python3 -c "import httpx; print(httpx.get('http://localhost:5001').status_code)"`
  instead of `curl`.
- **Finding/killing the temp process**: scan `/proc/[pid]/cmdline` directly for the port number
  and `os.kill(pid, 9)` — write this as a small script and `kubectl cp` it in rather than trying
  to nest `$()`/quoting through `bash -c` inside an SSM `send-command` JSON payload inside a
  shell command (multiple quoting layers reliably break heredocs and command substitution; a
  plain script file avoids all of it).
- Always confirm the **real** serving port (`5000`) is unaffected afterward — the whole point of
  this pattern is isolation from it.

---

## README maintenance rule

Every module under `app/v1/` has a `README.md`. **Any time you add, remove, or change an endpoint, a request field, or a config-driven behaviour in a module, you must update that module's `README.md` to reflect the change.** The README must always stay in sync with the actual routes and schemas.

---

## Module CLAUDE.md maintenance rule

Every module under `app/v1/` has a `CLAUDE.md` (e.g. `app/v1/sonarqube/CLAUDE.md`, `app/v1/confluence/CLAUDE.md`). **Any time you make a change to a module — routes, operations, schemas, conf, or any API call details — you must update that module's `CLAUDE.md` to reflect the change.** This includes:

- Adding or removing endpoints → update the Routes table
- Changing request/response fields → update the Schemas section
- Changing the sequence or number of API calls in an operation flow → update the flow description and call counts
- Adding or removing config fields → update the Config fields table
- Discovering quirks about the target service's API (e.g. a non-standard status code, a required header, a known broken endpoint) → add a note in the relevant section

The module `CLAUDE.md` is the authoritative developer reference for that service — it documents
*how the system works today*, in present tense, not a log of how it got there. It must stay in
sync with the actual code at all times.

---

## Workaround tracking rule

Any time you introduce a workaround — a temporary fix that unblocks something now but has a
known "real" fix pending elsewhere (an upstream library change, a Terraform/DNS change, a config
fix in another repo) — file a GitHub issue in this repo (`gh issue create --repo
devops-tashtiot/devops-api --label bug`) describing: what's broken, the workaround applied and
where, and what the real fix would be (link the blocking PR/issue if one already exists, and
cross-link back from that PR/issue with a comment if it's in a different repo). Do this
immediately, not just as a note in a module's `CLAUDE.md` — the `CLAUDE.md` documents *how the
system works today*, the issue tracks *that it still needs to be undone*.

Ordinary bug fixes (wrong method name, missing binary, route-shadowing, a hardcoded value that
should be looked up, etc.) don't need an issue — only fixes that are explicitly
temporary/hacky and leave a "real fix" undone elsewhere.

---

## Prefer live API lookups over hardcoded values

**Never hardcode enumerable values that the target service can return via its own API.** Examples: project roles, permission types, user groups, repository categories. Instead:

1. Add an operation that fetches the list from the service (e.g. `GET /projects/{key}/roles`)
2. Expose it as a `GET` route so callers can discover valid values at runtime
3. Accept the value as a plain `str` (or `list[str]`) in request schemas — do not gate with a Python `Enum`

**Concrete examples:**
- Artifactory project roles — `GET /access/api/v1/projects/{project_key}/roles` returns `[{"name": "Developer"}, ...]`; do NOT define a `ProjectRole` enum, use `list[str]` and expose `GET /permissions/roles/{project_key}`
- Jira project roles — `GET /rest/api/latest/role` returns all global roles with IDs; resolve the admin role by name at call time instead of hardcoding the numeric ID

The rule: if the service has an API for it, fetch it. Only hardcode a value when no such API exists.

---

## Extending existing modules vs. creating new ones

**Bitbucket** and **Confluence** are umbrella modules — any new Bitbucket or Confluence feature goes inside `app/v1/bitbucket/` or `app/v1/confluence/` respectively. Do **not** create a separate module (e.g. `bitbucket_userdirs/`, `confluence_groups/`) for each new operation. Instead:
- Add endpoint fields to the existing `conf.py`
- Add operation functions to `operations.py`
- Add route handlers to `routes.py`
- Add schemas to `schemas.py` if new request/response shapes are needed

Only create a new `app/v1/<service>/` directory for an entirely new external service (e.g. a new platform like SonarQube or Artifactory).

---

## How to add a new API module

Use Bitbucket (`app/v1/bitbucket/`) and Confluence (`app/v1/confluence/`) as reference
implementations. Six steps, in order:

**1. `app/v1/<service>/conf.py`** — a `<Service>Config(BaseSettings)` with always exactly three
fields, and a module-level singleton:

```python
from pydantic_settings import BaseSettings
from pydantic import Field

class <Service>Config(BaseSettings):
    API_PREFIX: str = Field(default="/api/v1/devops/<service>", description="API prefix for api exposure")
    <SERVICE>_ENDPOINT: str = Field(default="/rest/api/latest", description="API endpoint for <service>")  # adjust base path
    API_TAGS: list[str] = Field(default=["v1 - <Service> Operations"], description="OpenAPI tag")

config = <Service>Config()   # no model_config needed — global .env loading lives in global_conf.py
```

**2. `app/v1/<service>/schemas.py`** — one Pydantic model per resource (`ProjectSpec`,
`SpaceSpec`, ...). Always add `min_length`/`max_length` and `pattern` on string fields that go
into URLs or payloads:

```python
from pydantic import BaseModel, Field

class <Resource>Spec(BaseModel):
    key: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9_\-]+$")
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1, max_length=1000)
    admin_user: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z0-9_\-]+$")
    # add other fields as needed (e.g. public: bool = Field(False, ...))
```

**3. `app/v1/<service>/operations.py`** — always define `_handle_response()` raising
`HTTPException` on status > 299; every operation function unpacks payload fields, builds the
endpoint, wraps the call in `try/except`, logs with `logger.error(...)`, and re-raises (never
swallow — the router handles rollback):

```python
from .schemas import <Resource>Spec
from typing import Any
from .conf import config
from loguru import logger
from fastapi import HTTPException

def _handle_response(response):
    if response.status_code > 299:
        raise HTTPException(status_code=response.status_code, detail=f"errors: {response.text}")

async def create_<resource>(<service>_client: Any, payload: <Resource>Spec):
    key, endpoint = payload.key, f"{config.<SERVICE>_ENDPOINT}/<resources>"
    try:
        response = await <service>_client.post(endpoint, json={"key": key, "name": payload.name})
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error creating <resource> {key}: {str(e)}")
        raise

async def delete_<resource>(<service>_client: Any, payload: <Resource>Spec):
    key, endpoint = payload.key, f"{config.<SERVICE>_ENDPOINT}/<resources>/{payload.key}"
    try:
        response = await <service>_client.delete(endpoint)
        _handle_response(response)
    except Exception as e:
        logger.error(f"Unexpected error deleting <resource> {key}: {str(e)}")
        raise
```

**4. `app/v1/<service>/routes.py`** — factory `get_v1_<service>_router(<service>_client)`, prefix
and tags from `config`. Create is always `POST /`; **every `POST /` create endpoint must have a
matching `DELETE /{identifier}`** — no create without a delete. Catch `HTTPException` → return
`ExceptionResponse`; bare `except` → call delete for rollback:

```python
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.v1.response_schemas import ExceptionResponse, SuccessResponse
from .schemas import <Resource>Spec
from typing import Any
from .conf import config
from .operations import create_<resource>, delete_<resource>, assign_admin_permission

def get_v1_<service>_router(<service>_client: Any):
    router = APIRouter(prefix=config.API_PREFIX, tags=config.API_TAGS)

    @router.post("/", name="create <resource>", status_code=200)
    async def create_new_<resource>(payload: <Resource>Spec) -> JSONResponse:
        try:
            await create_<resource>(<service>_client, payload)
            await assign_admin_permission(<service>_client, payload)
            return SuccessResponse(status="successful")
        except HTTPException as external_error:
            return JSONResponse(
                ExceptionResponse(
                    stdout=f"Exception in <Service>. {external_error.detail}",
                    status="Failed", status_code=external_error.status_code,
                ).dict(),
                status_code=external_error.status_code,
            )
        except:
            await delete_<resource>(<service>_client, payload)   # rollback

    return router
```

**5. `app/global_conf.py`** — add four fields per new service inside `DevopsStaticSettings`:
`ENABLE_<SERVICE>_API` (bool, default `True`), `<SERVICE>_API_URL`, `<SERVICE>_USERNAME`,
`<SERVICE>_PASSWORD`. Use `auth=` (basic auth) for services like Bitbucket/Confluence/Jira/
SonarQube; use `headers={"Authorization": f"Bearer {token}"}` for genuinely token-based
services instead (e.g. ArgoCD/Git connectors via the internal library, or Artifactory — its
Access API rejects Basic auth outright, see `app/v1/artifactory/CLAUDE.md`). Confirm which
auth method the target service's API actually accepts before assuming Basic auth works.

**6. `app/main.py`** — import the router factory, then wire it in `create_app()`:

```python
if global_config.ENABLE_<SERVICE>_API:
    <service>_client = BaseAPI(
        global_config.<SERVICE>_API_URL,
        auth=(global_config.<SERVICE>_USERNAME, global_config.<SERVICE>_PASSWORD)
    ).client
    app.include_router(get_v1_<service>_router(<service>_client))
```

---

## Existing modules reference

| Module        | Auth type  | Endpoint base            | Resource  | Operations                              |
|---------------|------------|--------------------------|-----------|------------------------------------------|
| `artifactory` | Bearer token (Identity/reference token — Access API rejects Basic auth) | `/access/api/v1` | project | create, assign admin, increase storage quota, permissions, Xray vuln update |
| `bitbucket`   | Basic auth | `/rest/api/latest`       | project   | create, delete, assign admin; sync user dirs (501) |
| `confluence`  | Basic auth | `/rest/api/latest`       | space     | create, delete, assign user/group admin; plugin install/uninstall; space import |
| `jira`        | Basic auth | `/rest/api/latest`       | project   | create (`POST /`), delete (`DELETE /{key}`), assign admin; sync user dirs (501) |
| `argocd`      | Git connector | `consumers/` (git path) | consumer config | create (`POST /`), delete (`DELETE /{name}`), get sizes, get include-resources |
| `sonarqube`   | Basic auth | `/api`                   | group     | create (`POST /`), delete (`DELETE /{name}`), global admin + template admin    |

---

## Schema pattern — mutually exclusive optional fields

When a resource can be administered by either a user OR a group (but not both), use this pattern in `schemas.py`:

```python
from pydantic import BaseModel, Field, model_validator
from typing import Optional


class ResourceSpec(BaseModel):
    # ... other fields ...

    admin_user: Optional[str] = Field(
        default=None,
        description="Username to receive ADMIN permission",
        min_length=1,
        max_length=50,
        pattern=r"^[a-z0-9_\-]+$",
    )
    admin_group: Optional[str] = Field(
        default=None,
        description="Group name to receive ADMIN permission",
        min_length=1,
        max_length=255,
        pattern=r"^[a-z0-9_\-]+$",
    )

    @model_validator(mode="after")
    def require_exactly_one_admin(self) -> "ResourceSpec":
        if not self.admin_user and not self.admin_group:
            raise ValueError("Provide either admin_user or admin_group")
        if self.admin_user and self.admin_group:
            raise ValueError("Provide only one of admin_user or admin_group, not both")
        return self
```

In `routes.py`, branch on which field is set:
```python
if payload.admin_user:
    await assign_space_admin(client, payload)
else:
    await assign_space_group_admin(client, payload)
```

(Jira departs from this pattern — `admin_user` is required there, not part of an
either/or validator. See `app/v1/jira/CLAUDE.md`.)

## Response schemas (`app/v1/response_schemas.py`)

- `SuccessResponse(status="successful")` — returned on happy path
- `ExceptionResponse(stdout=..., status="Failed", status_code=...)` — returned inside `JSONResponse` on `HTTPException`
