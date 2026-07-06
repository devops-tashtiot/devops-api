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

## Token validation behaviour in local dev

`_check_cluster_permissions` in `operations.py` validates each cluster token by running `kubectl auth can-i "*" "*"` against the target cluster. It raises a 401 only when kubectl writes to **stderr** (unreachable server, TLS failure, or auth rejection).

On a local dev cluster (kind/minikube), the API server is typically permissive — it accepts any token, including completely invalid strings like `"this-is-a-broken-token"`, and returns `"yes"` to stdout with exit 0. This means broken-token tests will appear to succeed locally.

On a real cluster with proper RBAC and token validation, an invalid token causes kubectl to write an auth error to stderr, which the check catches and rejects with a 401. Broken-token validation only works correctly against a properly secured cluster.
