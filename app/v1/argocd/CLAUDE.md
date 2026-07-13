# ArgoCD module — dev defaults

When calling cluster-secret endpoints locally, use these values:

| Field | Value |
|---|---|
| `username` | `admin` |
| `password` | `123456` |
| `app_name` | `netanel` |
| `chosen_name` | `nati` |
| `applicationClusters[0].name` | `openshift` |
| `applicationClusters[0].address` | `https://127.0.0.1:45537` |
| `applicationClusters[0].namespace` | `default` |
| `applicationClusters[0].token` | `eyJhbGciOiJSUzI1NiIsImtpZCI6IjY0aGN1V2E1LTFsLV9YMXlCX1h6em9ZelNGN1lJdkJHNEZLSk5vb3FOdkEifQ.eyJhdWQiOlsiaHR0cHM6Ly9rdWJlcm5ldGVzLmRlZmF1bHQuc3ZjLmNsdXN0ZXIubG9jYWwiXSwiZXhwIjoxNzgxMjEwNDMxLCJpYXQiOjE3ODEyMDY4MzEsImlzcyI6Imh0dHBzOi8va3ViZXJuZXRlcy5kZWZhdWx0LnN2Yy5jbHVzdGVyLmxvY2FsIiwianRpIjoiMjA1MWMyZjUtYTg3OC00MWNlLWE2M2QtMTE3MzY5OTVjMTcxIiwia3ViZXJuZXRlcy5pbyI6eyJuYW1lc3BhY2UiOiJkZWZhdWx0Iiwic2VydmljZWFjY291bnQiOnsibmFtZSI6ImFyZ29jZC1jbHVzdGVyLXNhIiwidWlkIjoiYzJmMTczN2EtNjI0OS00MDZmLTg5ZGEtZTIyNmFmNjIzMTYwIn19LCJuYmYiOjE3ODEyMDY4MzEsInN1YiI6InN5c3RlbTpzZXJ2aWNlYWNjb3VudDpkZWZhdWx0OmFyZ29jZC1jbHVzdGVyLXNhIn0.QLwwRsI23cznJ1TI1z5PpEqPThoDbvBrACAU9fTqtqjUJPav652tEkshx9ZJVAPwr8TOBbNRCm3qudv0il6HVaeouxZ3PbngdkmO3sbzYqvezhsHts81-euwnzcqRvzqGirGwztuheZCn3hPDbqJd7CXkW7FUWFFSNelDycoG3rlUOgXeqHrHVerqjBk9VkQSuU5xK7SDHxl008RXVtzBiHisXRGgn2_S5SsDzXgcMYbnCA0RhWC78Jpc406RMAOSsntuV1K1eMh0mkKQ3qjbM7Jy2dG4lV7cORZ5BA8kZKR7OLejJCB6HNwUwP4S7keRzYO_YUo2rJKrrybtJxTNg` |

> The token is a short-lived (1h) service account token for `argocd-cluster-sa` in the `default` namespace.
> Regenerate with: `kubectl create token argocd-cluster-sa -n default`

## ConsumerConfigSpec — `extra_roles` field

`extra_roles` is an optional `list[str]` added to `POST /`. When provided, each string is a raw ArgoCD RBAC policy line written verbatim under the `extra_roles` key in the consumer's `config.yaml`.

Example:
```json
{
  "extra_roles": [
    "g, \"DEV_Mahan_Tmunat_Shamayim\", role:bluetorch",
    "p, role:bluetorch, applications, *, bluetorch/*, allow",
    "p, role:bluetorch, projects, get, bluetorch, allow"
  ]
}
```

Each item is validated against an alternation that enforces exact field counts per type:

- `g` lines — exactly 3 fields (2 commas): `g, <subject>, <role>`
- `p` lines — exactly 6 fields (5 commas): `p, <subject>, <resource>, <action>, <object>, <allow|deny>`

Each field is either a quoted string (`"..."`) or a non-whitespace token (`role:name`, `*`, `allow`, a URL, etc.).

Omit the field (or pass `null`) to create a consumer without extra roles.

## Live-check findings (2026-07-13)

Followed the same "check all APIs live against the cluster" procedure used for Bitbucket, Jira,
and SonarQube. Full route inventory (10 routes) — `GET /sizes`, `/include-resources`,
`/rbac-resources`, `/rbac-actions`, `/environments` all confirmed working live (pure enum
lookups, no external calls). The other 5 have real live issues, none of which are devops-api
code bugs in this module itself:

### Fixed — entire unit test suite was never collectible

`tests/v1/argocd/test_argocd_routes.py` and `test_argocd_schema.py` both referenced
`config.ARGOCD_ALLOWED_SIZES` / `config.ARGOCD_ALLOWED_RESOURCES` (the module's own
`ArgocdConfig`), but those two fields actually live on `global_config` (`app/global_conf.py`),
not `app/v1/argocd/conf.py`. This raised `AttributeError` at collection time — the **entire**
argocd test suite (56 tests) has never actually run, in CI or otherwise. Confirmed via
`git stash` that this predates any change made here. Fixed by changing both references to
`global_config.ARGOCD_ALLOWED_SIZES` / `global_config.ARGOCD_ALLOWED_RESOURCES` (matching how
`VALID_ENV = global_config.ARGOCD_ALLOWED_ENVS[0]` already did it correctly in both files).

### Consumer-config routes (`POST /`, `DELETE /{env}/{name}`)

**2026-07-13 findings (now stale, kept for history):** repo slug missing under `ARGO`, no SSH
key mounted, and a hostname-parsing bug in the pinned `tashtiot-apis-library` wheel (`ssh://git@
http::7995/...`).

**2026-07-14 update:** (1) is fixed — the `ARGO/argocd` repo now exists, seeded by mirroring
`github.com/devops-tashtiot/argocd` directly via Bitbucket's in-cluster ClusterIP/`bitbucket-0`
pod (bypassing Cloudflare Access, which was interfering with git smart-HTTP through the public
hostname). Its default branch was converted from `main` to `master` to match
`ARGOCD_GITOPS_DEFAULT_BRANCH`.

With the repo in place, live-testing `POST /` now hits a **different, previously-unseen error**
that supersedes (2)/(3) above — the Git connector isn't attempting SSH at all in the live
deployment, it's using Bearer-token HTTP auth, and `GIT_TOKEN` is deployed as `""` (see
`devtools-definition/devtools/devops-api/values.yaml`'s `GIT_TOKEN: "" # set out-of-band, not
committed to git`). This produces `httpx.InvalidHeader: Illegal header value b'Bearer '` — the
empty string is passed straight into the `Authorization` header. **Still blocked** — needs a
real `GIT_TOKEN` provisioned out-of-band (the (2)/(3) SSH-path findings above are moot until/
unless the connector is reconfigured to use SSH instead of the token path).

### Cluster-secret routes (`POST/DELETE/PUT /cluster-secret*`)

**2026-07-13 findings (now stale, kept for history):** no wildcard DNS for
`*.argocd.devopstashtiot.page`, and `ARGOCD_CLUSTER_SECRET_REPO_URL` pointed at a Gitea
deployment that doesn't exist in this cluster.

**2026-07-14 update:** both fixed — wildcard DNS now resolves, and
`ARGOCD_CLUSTER_SECRET_REPO_URL` now points at the `ARGO/argocd` Bitbucket repo (in-cluster DNS:
`http://bitbucket.bitbucket.svc.cluster.local/scm/argo/argocd.git`). The repo was also made
genuinely public (`-Dfeature.public.access=true` JVM arg on the Bitbucket deployment — public
access is globally disabled by default since Bitbucket DC 8.18, confirmed via
https://confluence.atlassian.com/bitbucketserver/allowing-public-access-to-code; no REST
endpoint exists to toggle it, `/admin/permissions/anonymous` and `/admin/settings` both 404 even
against a `SYS_ADMIN` token), so ArgoCD needs no registered repository-credential Secret at all
for this repo.

Live-testing `POST /cluster-secret` with those fixes in place surfaced a **new, previously
unreached blocker**: `_check_cluster_permissions()` (`operations.py:12`) shells out to `kubectl
auth can-i ...` as a subprocess, but **the `devops-api` container image does not have `kubectl`
installed** — fails with `[Errno 2] No such file or directory: 'kubectl'`. This runs before
`_build_argocd()`, so it's earlier in the call chain than the DNS/repo issues — meaning those
were never actually reached in any prior live test (the cluster-secret e2e test has always been
skipped by default, `E2E_ARGOCD_CLUSTER_TOKEN` unset). **Still blocked** — needs `kubectl`
added to the devops-api Docker image, or `_check_cluster_permissions` reimplemented without
shelling out to a binary that isn't guaranteed to be present.

Neither blocker above is fixable from within `test_argocd_e2e.py` itself — both need
out-of-cluster provisioning (`GIT_TOKEN` secret; Docker image change) rather than test/gitops
changes.

## Token validation behaviour in local dev

`_check_cluster_permissions` in `operations.py` validates each cluster token by running `kubectl auth can-i "*" "*"` against the target cluster. It raises a 401 only when kubectl writes to **stderr** (unreachable server, TLS failure, or auth rejection).

On a local dev cluster (kind/minikube), the API server is typically permissive — it accepts any token, including completely invalid strings like `"this-is-a-broken-token"`, and returns `"yes"` to stdout with exit 0. This means broken-token tests will appear to succeed locally.

On a real cluster with proper RBAC and token validation, an invalid token causes kubectl to write an auth error to stderr, which the check catches and rejects with a 401. Broken-token validation only works correctly against a properly secured cluster.
