# ArgoCD module — developer notes

## Dev defaults

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
| `applicationClusters[0].token` | short-lived (1h) SA token for `argocd-cluster-sa` in `default` |

Regenerate the token with: `kubectl create token argocd-cluster-sa -n default`

## ConsumerConfigSpec — `extra_roles` field

`extra_roles` is an optional `list[str]` on `POST /`. Each string is a raw ArgoCD RBAC policy
line written verbatim under the `extra_roles` key in the consumer's `config.yaml`:

```json
{
  "extra_roles": [
    "g, \"DEV_Mahan_Tmunat_Shamayim\", role:bluetorch",
    "p, role:bluetorch, applications, *, bluetorch/*, allow",
    "p, role:bluetorch, projects, get, bluetorch, allow"
  ]
}
```

Each item is validated against an alternation enforcing exact field counts per type:
- `g` lines — exactly 3 fields (2 commas): `g, <subject>, <role>`
- `p` lines — exactly 6 fields (5 commas): `p, <subject>, <resource>, <action>, <object>, <allow|deny>`

Each field is a quoted string (`"..."`) or a non-whitespace token (`role:name`, `*`, `allow`, a
URL, etc). Omit the field (or pass `null`) to create a consumer without extra roles.

**Where the valid resource/action lists come from (`schemas.py:13-45`).** The `p` line's
`<resource>`/`<action>` are constrained twice from the same underlying list: `_RESOURCE`/
`_ACTION` (regex alternations for raw `extra_roles` strings) and `RbacResourceEnum`/
`RbacActionEnum` (real enums used by the structured `PLine` model, also exposed live via `GET
/rbac-resources`/`GET /rbac-actions` for runtime discovery). Both are **hardcoded**, transcribed
by hand from [ArgoCD's RBAC spec](https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/)
— no live ArgoCD API returns "the current valid RBAC resource/action list", so there's nothing to
fetch instead.

**Check this again on the next ArgoCD version upgrade.** If a future version adds a new RBAC
resource/action, both the regex alternations and the enum classes need updating by hand to stay
in sync with each other and with ArgoCD — until then, a valid new RBAC line is rejected as
invalid.

## ConsumerConfigSpec — `config` field (`ConsumerExtraConfig`)

`config` is an optional field on `POST /` letting a caller pass extra key/value overrides for
ArgoCD's own `argocd-cm` and `argocd-cmd-params-cm` config files, via two optional dicts:
`extra_argocd_cm_args` and `extra_argocd_params`. These get written verbatim into the consumer's
`config.yaml` under a `config:` key (`operations.py:171-178`) — something downstream (the ArgoCD
GitOps chart, in a different repo) turns that key into real ConfigMap entries.

Any key/prefix is accepted (there used to be a hardcoded namespace-prefix whitelist here,
transcribed from ArgoCD's docs — removed because there's no live API to keep it in sync with
ArgoCD's evolving config schema, unlike e.g. Jira/Artifactory roles which this repo fetches
live). The only remaining check is that a multi-line value (containing `\n`) must parse as valid
YAML — a genuinely independent safety check, unrelated to whether ArgoCD's schema has changed.

## Consumer-config routes (`POST /`, `DELETE /{env}/{name}`)

Both routes work end-to-end against the real cluster. `POST /` (create) uses the `Git`
connector's Bearer-token HTTP path (`git.add_file`) against `GIT_TOKEN`, sourced from the SSM
SecureString `/devtools/bitbucket/api-token` via the chart's `vault.enabled` ExternalSecret
mechanism. `DELETE /{env}/{name}` (delete) uses `git.delete_file`, which internally does a full
`git clone` over **SSH** rather than the Bearer-token HTTP path — a different code path in the
vendored library, with its own set of requirements:

- **`GIT_SSH_PORT` must match ingress-nginx's TCP-passthrough listener, not necessarily
  Bitbucket's real SSH port.** The library hardcodes SSH port `7995` by default, which is not
  Bitbucket's real SSH port on this deployment (`7999` — see `kubectl get svc -n bitbucket`).
  `bitbucket.devopstashtiot.page` resolves in-cluster to `ingress-nginx-controller` (see CoreDNS
  section below), which is HTTP(S)-only — a TCP SYN to a port with no matching Service rule is
  silently dropped, causing a hang/timeout rather than a fast failure. The fix is
  `clusters-provision/clusters/ingress-nginx/values.yaml`'s TCP-passthrough config, mapping
  `7995` (external) → `bitbucket/bitbucket:7999` (real), paired with `GIT_SSH_PORT=7995`
  explicitly set in `devtools-definition/devtools/devops-api/values.yaml` (the library's own
  default of `7999` would *not* work through this passthrough). **If either side of this pairing
  changes, the other must change with it** — updating only one reproduces a silent hang. A
  `kubectl rollout restart deployment/devops-api` is required to pick up a `GIT_SSH_PORT` change
  (ConfigMap updates don't auto-restart pods — see root `CLAUDE.md`).
- **An SSH keypair must be mounted at `GIT_SSH_KEY_PATH`** (`/root/.ssh/id_ed25519`) via
  `devtools-definition`'s `extraSecretMounts`, with the public half registered against
  Bitbucket's `admin` account and the private half in SSM
  (`/devtools/bitbucket/git-ssh-private-key`).
- **The SSM private key must retain its trailing newline.** `aws ssm put-parameter --value
  "$(cat id_ed25519)"` silently strips the trailing newline after `-----END OPENSSH PRIVATE
  KEY-----` via bash command substitution, which OpenSSH's parser requires — without it you get
  `Load key ...: error in libcrypto`. Use `aws ssm get-parameter --output json` to confirm the
  stored value (the only output mode that doesn't itself re-add a newline).

`tests/v1/sonarqube/test_sonarqube_consumer_e2e.py`'s `DELETE /consumer/{name}` hits the same
Git-connector-over-SSH code path — see that module's `CLAUDE.md`; this same fix covers both.

## Cluster-secret routes (`POST/PUT/DELETE /cluster-secret*`)

`_build_argocd()` targets `https://{app_name}.argocd.{DOMAIN_SUFFIX}` — a distinct ArgoCD
instance per consumer, conceptually. In reality there is still only **one** ArgoCD instance in
this cluster; the per-consumer wildcard DNS just routes every `{app_name}.argocd...` hostname to
that same instance (see CoreDNS section below). This is enough to exercise the real API/auth code
path end-to-end but is **not** real per-consumer isolation.

### Outbound auth — SSO, not a caller-supplied token

`_build_argocd()` is `async` and mints its own short-lived `client_credentials` token via
`tashtiot_apis_library.fastapi_template.security`'s `get_sso_token_client(SSOConfig(...))` — no
ArgoCD credential is accepted from the caller (the `token` field was removed from all
cluster-secret schemas). Reusing the existing browser-login `argocd` Keycloak client for this
doesn't work: a plain `client_credentials` grant against it mints `aud: account` (Keycloak's
default), not `aud: argocd`, and even with audience fixed, ArgoCD's RBAC (`policy.csv`) is
entirely AD-group-based — a service-account token has no group membership to match. The fix is a
**dedicated** Keycloak client, `argocdServiceClient` (`devops-api-argocd`,
`serviceAccountsEnabled: true`, `clusters-provision/clusters/rhbk`), with its own client scope
(`devops-api-argocd-audience`) carrying an audience mapper (`aud: argocd`) and a **hardcoded**
`groups` claim mapper (`["devops-api-argocd-svc"]`, since a service account has no real AD group
membership for the normal group mapper to read). `devtools-definition/devtools/argocd/
values.yaml`'s `policy.csv` binds a scoped-down role to that synthetic group — only
`get`/`create`/`update`/`delete`/`sync` on `applications` in the `default` project (the only
project `create_cluster_secret()` targets), not `role:admin`.

### `argocd-server` must trust Cloudflare's Origin CA root, not a leaf cert

ArgoCD's own OIDC verification requires `argocd-server` to make an outbound HTTPS call to
Keycloak's discovery endpoint on every token verification (not just at startup). That hostname
resolves via the same CoreDNS rewrite as everything else, presenting the real Cloudflare Origin
Cert — so `argocd-cm`'s `oidc.config.rootCA` must be set to Cloudflare's own published **CA
root** certificate. A previous value here was `*.devopstashtiot.page`'s own **leaf** origin
cert (`CA:FALSE`) — a non-CA leaf certificate can never be a valid trust anchor for a *different*
host's leaf certificate, regardless of how "Cloudflare" the name on it looks. Verify any future
cert change with `openssl verify -CAfile <candidate> <leaf-cert-on-the-wire>` → `OK` before
applying.

### `sync()` doesn't wait for the operation to finish

`ArgoCD.sync(app_name)` (library) calls `sync_app` and returns immediately without waiting for
the triggered sync operation to complete. An immediate follow-up call (e.g. `PUT` right after a
successful `POST`) can then hit ArgoCD's one-operation-at-a-time limit: `400 another operation is
already in progress`. Fixed by using the library's real-completion primitive,
`ArgoCD.wait_for_update(app_name)` (polls `get_app` until the status fingerprint genuinely
changes, bounded by `ARGOCD_APPLICATION_SET_TIMEOUT`, default 300s) after every `sync()` call in
`create_cluster_secret()`/`edit_cluster_secret()`, and `wait=True` on `delete_app()` in
`delete_cluster_secret()` (the library's own docs say this is required before recreating an
Application under the same name). Don't paper over this class of race with a fixed `sleep` —
`wait_for_update`/`wait=True` wait for the real signal, not a guessed duration.

Similarly, `create_cluster_secret()` passes `wait=True` to `create_app()` before calling `sync()`
— ArgoCD's `get_app` can 403 for a few seconds after creation before the new Application is
visible, and `wait=True` (→ `wait_for_app_creation`) closes that window. **Known, not yet hit in
practice:** this endpoint sits behind ingress-nginx and Cloudflare Tunnel, both of which have
proxy-level read timeouts shorter than the 300s bound (~60s / ~100s) — in a degraded scenario
where ArgoCD is slow, the proxy could return a `502`/`504` to the caller while
`create_cluster_secret` keeps running server-side. Not a devops-api bug if seen.

## CoreDNS rewrite — how in-cluster calls reach `*.devopstashtiot.page` without hitting Cloudflare Access

Cloudflare Access sits in front of the entire `*.devopstashtiot.page` domain — any programmatic,
token-auth request from inside the cluster to a public hostname on this domain would normally
hit Access's email-OTP wall regardless of Ingress routing. This applies to every tool devops-api
(or any in-cluster caller, e.g. `argocd-server` verifying an OIDC token) calls out to via its
public hostname, not just ArgoCD.

This is a **workaround, not the intended fix** — AWS Control Tower now permits creating a private
Route53 hosted zone in this account (it didn't when this was first built), which is the correct
long-term replacement. Until that exists, the cluster's own **CoreDNS**
(`kube-system/coredns` ConfigMap, applied directly via `kubectl` — not tracked in any GitOps
repo, since CoreDNS is minikube's own addon, not managed by `clusters-provision`/
`clusters-definition`) carries `rewrite` rules resolving every `*.devopstashtiot.page` hostname,
for any in-cluster caller, straight to the internal Service — bypassing the Tunnel and Access
entirely for in-cluster traffic, while external/public resolution via real Cloudflare DNS is
untouched:

```
rewrite name exact argocd.devopstashtiot.page ingress-nginx-controller.ingress-nginx.svc.cluster.local answer auto
rewrite name regex (.*)\.argocd\.devopstashtiot\.page argocd-server.argocd.svc.cluster.local answer auto
rewrite name exact bitbucket.devopstashtiot.page ingress-nginx-controller.ingress-nginx.svc.cluster.local answer auto
rewrite name exact confluence.devopstashtiot.page ingress-nginx-controller.ingress-nginx.svc.cluster.local answer auto
rewrite name exact jira.devopstashtiot.page ingress-nginx-controller.ingress-nginx.svc.cluster.local answer auto
rewrite name exact sonarqube.devopstashtiot.page ingress-nginx-controller.ingress-nginx.svc.cluster.local answer auto
rewrite name regex (.*)\.sonarqube\.devopstashtiot\.page ingress-nginx-controller.ingress-nginx.svc.cluster.local answer auto
rewrite name exact artifactory.devopstashtiot.page ingress-nginx-controller.ingress-nginx.svc.cluster.local answer auto
rewrite name exact rhbk.devopstashtiot.page ingress-nginx-controller.ingress-nginx.svc.cluster.local answer auto
```

**Why route through `ingress-nginx-controller` rather than each tool's own backend Service
directly:** the cluster has a real Cloudflare Origin Certificate for `*.devopstashtiot.page`
(`clusters-provision/clusters/ingress-nginx/templates/origin-cert-secret.yaml`), but it's mounted
on `ingress-nginx-controller`'s Service only — every devtool's own backend Service is plain HTTP,
no TLS listener at all (confirmed via `kubectl get svc` — no `443/TCP` on any backend). Routing
through `ingress-nginx-controller` means normal host-based Ingress routing reaches the correct
backend on the correct port (no per-tool port override needed) **and** presents the real Origin
Cert, so `https://` is genuine end-to-end TLS, not a bypass.

Because that cert is signed by Cloudflare's own private Origin CA (not in any standard trust
store), `devops-api`'s `Dockerfile` installs the public Cloudflare Origin CA RSA root cert
(`cloudflare-origin-ca-rsa-root.pem`, from
https://developers.cloudflare.com/ssl/origin-configuration/origin-ca/) into **both** the system
trust store (`update-ca-certificates`) and `certifi`'s bundle — httpx uses `certifi.where()` by
default, **not** the system store, so installing only one silently leaves the other unfixed.

**The per-consumer ArgoCD wildcard (`(.*)\.argocd\.devopstashtiot\.page`) is an exception** — it
routes straight to `argocd-server.argocd.svc.cluster.local`, not through `ingress-nginx-
controller`, because there's no Ingress rule for arbitrary `*.argocd` subdomains (only the bare
`argocd.devopstashtiot.page` host is configured). `argocd-server` serves its own **self-signed**
TLS on 443 here (not the Origin Cert) — a third distinct certificate that devops-api would need
to trust for real verification on this specific path; not currently added to the Dockerfile's
trust store.

This persists across normal EC2 reboots (the cluster's etcd state is persistent on this node) but
will not survive a genuine cluster rebuild. If a real multi-tenant per-consumer ArgoCD service is
ever built, or the private Route53 zone replaces this, update/remove these rewrite rules
accordingly rather than layering more fixes on top.

## Token validation in local dev vs. a real cluster

`_check_cluster_permissions` (`operations.py`) validates each cluster token by running `kubectl
auth can-i "*" "*"` against the target cluster. It raises 401 only when kubectl writes to
**stderr** (unreachable server, TLS failure, auth rejection).

On a local dev cluster (kind/minikube), the API server is typically permissive — it accepts any
token, including invalid strings, returning `"yes"` on stdout with exit 0. Broken-token tests
will appear to pass locally. On a real cluster with proper RBAC, an invalid token causes kubectl
to write an auth error to stderr, which this check catches and rejects with 401 — broken-token
validation only actually works against a properly secured cluster.
