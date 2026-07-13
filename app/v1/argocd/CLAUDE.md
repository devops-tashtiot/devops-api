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

### Known live blocker — consumer-config routes (`POST /`, `DELETE /{env}/{name}`)

Same root causes as `app/v1/sonarqube/CLAUDE.md`'s "Known live blockers" section, since both
modules share the same `Git` connector pattern:
1. The `argocd` repo slug (`ARGOCD_AAS_REPO_SLUG`) did not exist under Bitbucket project `ARGO`
   — `tests/v1/argocd/test_argocd_e2e.py`'s setup fixture now creates it idempotently (never
   torn down), same pattern as the sonarqube consumer e2e test.
2. No SSH key is mounted in the devops-api pod at all (`GIT_SSH_KEY_PATH` points nowhere).
3. The pinned `tashtiot-apis-library` wheel predates a hostname-parsing fix already present in
   its own source (produces `ssh://git@http::7995/...` instead of the real Bitbucket host).

`test_argocd_e2e.py`'s consumer-config tests are written correctly and will pass once (2) and
(3) above are resolved — confirmed live today they fail with the identical `ssh: Could not
resolve hostname http::7995` error seen in the sonarqube module.

### Known live blocker — cluster-secret routes (`POST/DELETE/PUT /cluster-secret*`)

`_build_argocd()` (`operations.py:50-52`) targets `https://{app_name}.argocd.{DOMAIN_SUFFIX}` —
**no wildcard DNS record exists for `*.argocd.devopstashtiot.page`** (confirmed via
`dig @1.1.1.1`; only the bare `argocd.devopstashtiot.page`, the platform's own management-plane
ArgoCD, resolves). Unlike other modules (Bitbucket/Confluence/SonarQube/Jira — see
`devtools-definition/devtools/devops-api/values.yaml`'s comment on why they use in-cluster
Service DNS instead of the public hostname, to dodge Cloudflare Access), there is no equivalent
in-cluster fallback or env var override for the per-consumer ArgoCD URL — it's hardcoded to the
public hostname pattern with nothing else possible. No `app_name` value can resolve today.

Separately, `create_cluster_secret`/`edit_cluster_secret` also depend on
`ARGOCD_CLUSTER_SECRET_REPO_URL` (`http://gitea-http.gitea.svc.cluster.local:3000/...` per the
live env) as the Helm chart source for the ArgoCD `Application` they create — **no Gitea
deployment exists anywhere in the cluster** (`kubectl get pods -A | grep -i gitea` returns
nothing live).

Both are real, multi-system infra gaps (Cloudflare DNS + a missing Gitea devtool), not code bugs
in this module — `test_argocd_e2e.py`'s cluster-secret test is skipped by default
(`E2E_ARGOCD_CLUSTER_TOKEN` unset) since there's no way to self-provision either gap from within
a test.

## Token validation behaviour in local dev

`_check_cluster_permissions` in `operations.py` validates each cluster token by running `kubectl auth can-i "*" "*"` against the target cluster. It raises a 401 only when kubectl writes to **stderr** (unreachable server, TLS failure, or auth rejection).

On a local dev cluster (kind/minikube), the API server is typically permissive — it accepts any token, including completely invalid strings like `"this-is-a-broken-token"`, and returns `"yes"` to stdout with exit 0. This means broken-token tests will appear to succeed locally.

On a real cluster with proper RBAC and token validation, an invalid token causes kubectl to write an auth error to stderr, which the check catches and rejects with a 401. Broken-token validation only works correctly against a properly secured cluster.
