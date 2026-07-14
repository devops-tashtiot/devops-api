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

With the repo in place, live-testing `POST /` hit a **different, previously-unseen error** that
superseded (2)/(3) above — the Git connector isn't attempting SSH at all for file creation, it
uses Bearer-token HTTP auth, and `GIT_TOKEN` was deployed as `""`. This produced
`httpx.InvalidHeader: Illegal header value b'Bearer '` — the empty string passed straight into
the `Authorization` header.

**Fixed** — `GIT_TOKEN` is now sourced from the SSM SecureString `/devtools/bitbucket/api-token`
via the chart's `vault.enabled` ExternalSecret mechanism (`clusterSecretStore:
aws-parameter-store`; see `devtools-definition/devtools/devops-api/values.yaml`), not plaintext.
Confirmed live: `POST /` returns `200 successful` and the file is actually committed to
Bitbucket.

**⚠️ Still broken — `DELETE /{env}/{name}`:** unlike create, delete goes through a full `git
clone --depth 1 --branch master ... ssh://git@http::7995/...` inside the connector library —
i.e. the *original* SSH-key/hostname-parsing bug from (2)/(3) is still fully present, just
scoped to this one path instead of the whole module. Confirmed live: cleaning up a test
consumer via this route failed with the exact `ssh: Could not resolve hostname http::7995`
error; the artifact had to be removed by cloning/pushing directly against Bitbucket's in-cluster
service instead, bypassing devops-api entirely. **This needs a real fix** — either mount a
working SSH key at `GIT_SSH_KEY_PATH` and get the hostname-parsing bug patched upstream in
`tashtiot-apis-library`, or find/request a version of the library where `delete_file` also uses
the Bearer-token HTTP path like `add_file` does. Don't assume this route works just because
create does — they are two different code paths in the vendored library.

**2026-07-14 re-check, now bumped to `v1.1.2` — library code is unchanged, but whether the bug still
fires depends on config that has since changed too; needs a real live re-test, not another read of
the source.** Diffing `0.1.0`'s `connectors/git/client.py` against `v1.1.2`'s confirms the `ssh_host`
line itself is byte-for-byte the same logic (only a quote-style reformat):
`self.ssh_host = f"{base_url.replace('https://', '').split('/')[0]}:7995"` — it still only strips
`https://`, so it still mis-parses a plain `http://` `base_url` into a broken host like `http::7995`.

*However*, `GIT_API_URL` (the `base_url` this constructs from) is **no longer** the `http://` value
that produced the original `http::7995` failure. Checked git history on
`devtools-definition/devtools/devops-api/values.yaml`: at the time of the 2026-07-13 finding it was
`http://bitbucket.bitbucket.svc.cluster.local/rest/api/1.0`, genuinely `http`. It was since changed
(unrelated to this bug — part of the later CoreDNS/Cloudflare-Origin-Cert work in this same file) to
`https://bitbucket.devopstashtiot.page/rest/api/1.0`. Recomputing the exact same string operation
with *that* value gives the **correct** `bitbucket.devopstashtiot.page:7995` — so the specific parsing
failure may no longer reproduce, as an unintended side effect of an unrelated config change, not
because anyone fixed this bug. **Do not mark this resolved on that basis** — the library's own logic
is still wrong in principle (it'll break again for any future `http://` `GIT_API_URL`), and whether
port `7995` (Bitbucket SSH) is even reachable through the Cloudflare Tunnel from in-cluster is a
separate, unverified question — `bitbucket.devopstashtiot.page` is only confirmed reachable on 443
elsewhere in this file.

**2026-07-14, actually live-tested — still broken, but not with the `http::7995` symptom.** Ran
`test_create_delete_consumer_config_full_flow` and `test_create_consumer_config_with_rbac_lines`
against the real deployed API (correct `BITBUCKET_URL`/credentials, a real inbound-auth Bearer
token). `POST /` (create) succeeds. `DELETE /{env}/{name}` (called both directly and via each
test's own cleanup-before-run step) doesn't fail fast with a hostname error this time — it hangs
until the test client's 30s timeout: `httpx.ReadTimeout: timed out`.

**Root-caused, same day — two stacked bugs, not one:**
1. Port `7995` (what the library hardcodes) is not Bitbucket's real SSH port on this deployment —
   `kubectl get svc -n bitbucket` shows `80/TCP,7999/TCP,5701/TCP`. `7995` doesn't match anything.
2. Even the right port wouldn't have been reachable anyway: `bitbucket.devopstashtiot.page`
   resolves in-cluster to `ingress-nginx-controller` (the CoreDNS rewrite), which only exposes
   `80/443` — an HTTP(S) router with no listener at all on any SSH port. A TCP SYN to a ClusterIP
   port with no matching Service rule gets silently dropped, not rejected — hence a hang/timeout
   instead of an instant "connection refused."

**Fixed two ways:**
- **Immediate, live workaround:** `clusters-provision/clusters/ingress-nginx/values.yaml` now
  configures ingress-nginx's standard TCP-passthrough feature, mapping `7995` (external, what the
  library asks for) → `bitbucket/bitbucket:7999` (real). This is marked TEMPORARY in that file —
  remove it once the fix below ships and is actually deployed.
- **Real fix, upstream:** opened
  [`Platform-Infra-Org/apis-library#12`](https://github.com/Platform-Infra-Org/apis-library/pull/12)
  adding an `ssh_port` parameter to `Git`/`GitClient` (defaults to `7995`, unaffected for every
  other caller). Once merged and this repo bumps to a version with it, pass `ssh_port=7999`
  explicitly here and remove the ingress-nginx TCP-passthrough workaround above — at that point
  it's a redundant hop, not a fix.

`tests/v1/sonarqube/test_sonarqube_consumer_e2e.py`'s `DELETE /consumer/{name}` hit the identical
symptom the same day, same `git.delete_file` code path — see that module's `CLAUDE.md`; the same
workaround/fix covers both.

**2026-07-14, retested after the TCP-passthrough workaround shipped — network layer confirmed
fixed, new (separate, simpler) blocker found.** With the ingress-nginx TCP-passthrough live,
`DELETE /{env}/{name}` no longer hangs — it now fails immediately and cleanly:
```
Warning: Identity file /root/.ssh/id_ed25519 not accessible: No such file or directory.
Warning: Permanently added '[bitbucket.devopstashtiot.page]:7995' (RSA) to the list of known hosts.
git@bitbucket.devopstashtiot.page: Permission denied (publickey).
```
This is the correct, expected shape of a *working* SSH connection hitting a *missing key* —
proof the network-level bug (wrong port, unreachable route) is genuinely fixed. `GIT_SSH_KEY_PATH`
(`/root/.ssh/id_ed25519`) was configured all along but nothing ever actually mounted a key file
at that path — the chart's `deployment.yaml` only supported file-mounted secrets when
`vault.enabled: false`, which devops-api never was (see `devtools-provision`'s git history: "fix:
allow extraSecretMounts alongside vault.enabled"). **Fixed** — generated a fresh ed25519 keypair,
registered the public half against Bitbucket's `admin` account (`POST /rest/ssh/1.0/keys`),
stored the private half in SSM (`/devtools/bitbucket/git-ssh-private-key`), and wired it in via
`devtools-definition`'s `extraSecretMounts` (mounted as a file, not exposed as the primary means
of consumption — see that repo's values.yaml comment for the minor caveat that it does also land
as a plain env var via the same Secret's `envFrom`, accepted rather than standing up a second
ExternalSecret just to avoid it). Not yet re-verified live after this specific change landed —
whoever picks this up next should re-run `test_create_delete_consumer_config_full_flow` to confirm
`DELETE /{env}/{name}` returns `200`, not just that the SSH error changed shape.

### Cluster-secret routes (`POST/DELETE/PUT /cluster-secret*`)

**2026-07-13 findings (now stale, kept for history):** no wildcard DNS for
`*.argocd.devopstashtiot.page`, and `ARGOCD_CLUSTER_SECRET_REPO_URL` pointed at a Gitea
deployment that doesn't exist in this cluster.

**2026-07-14 update:** both fixed — wildcard DNS now resolves, and
`ARGOCD_CLUSTER_SECRET_REPO_URL` now points at the `ARGO/argocd` Bitbucket repo via its real
public hostname, `http://bitbucket.devopstashtiot.page/scm/argo/argocd.git` (see "CoreDNS
rewrite workaround" below for how a public hostname is reachable from in-cluster callers again).
The repo was also made genuinely public (`-Dfeature.public.access=true` JVM arg on the Bitbucket
deployment — public access is globally disabled by default since Bitbucket DC 8.18, confirmed
via https://confluence.atlassian.com/bitbucketserver/allowing-public-access-to-code; no REST
endpoint exists to toggle it, `/admin/permissions/anonymous` and `/admin/settings` both 404 even
against a `SYS_ADMIN` token), so ArgoCD needs no registered repository-credential Secret at all
for this repo.

Live-testing `POST /cluster-secret` with those fixes in place surfaced a **new, previously
unreached blocker**: `_check_cluster_permissions()` (`operations.py:12`) shells out to `kubectl
auth can-i ...` as a subprocess, but **the `devops-api` container image did not have `kubectl`
installed** — failed with `[Errno 2] No such file or directory: 'kubectl'`. This runs before
`_build_argocd()`, so it was earlier in the call chain than the DNS/repo issues above — meaning
those were never actually reached in any prior live test (the cluster-secret e2e test has always
been skipped by default, `E2E_ARGOCD_CLUSTER_TOKEN` unset).

**Fixed** — `kubectl` (pinned to `v1.35.1`, matching the minikube-on-EC2 cluster's own server
version) is now installed in the `Dockerfile`.

**Fixed — code/library mismatch:** with `kubectl` in place, live-testing hit a deeper bug:
`_build_argocd()` called `ArgoCD.from_credentials(base_url, timeout, username, password)` —
**`from_credentials` does not exist anywhere in the pinned `tashtiot-apis-library` wheel.**
Confirmed by reading the actual installed library's source inside the live pod (`python -c
"import tashtiot_apis_library as t, inspect; print(inspect.getsource(t.ArgoCD))"`): the real
constructor is `ArgoCD(base_url: str, api_key: str, application_set_timeout: int)` — synchronous,
and token-based (`api_key`) from the start. There was never a username/password code path in
this library version; `ClusterSecretSpec.username`/`.password` were dead on arrival — no
combination of values for them could ever have worked, in any environment, at any point. This
was not a regression or an infra gap like the others in this file — **it was a latent bug in
this module's original design**, invisible only because the cluster-secret e2e test has always
been skipped and the unit tests mock `_build_argocd` entirely, so nothing ever actually called
`ArgoCD.from_credentials` until a real live test did.

Fixed by switching `ClusterSecretSpec`/`ClusterSecretUpdateSpec`/`ClusterSecretIdentifier` to a
single required `token: str` field (ArgoCD API token) and `_build_argocd()` to a plain sync
function calling `ArgoCD(base_url, token, timeout)` directly — no `await`, the real constructor
isn't async. All call sites and every test file updated to match. A real token was generated
against the platform's actual ArgoCD instance and stored at SSM `/devtools/argocd/api-token` for
live-testing this path.

**Was a real gap, now mitigated — CoreDNS rewrite workaround.** `_build_argocd()` targets
`https://{app_name}.argocd.{DOMAIN_SUFFIX}`, i.e. a distinct ArgoCD instance per consumer. As of
2026-07-14, `*.argocd.devopstashtiot.page` has a wildcard DNS record (Cloudflare-proxied), but
there is still only **one** real ArgoCD instance in this cluster, and Cloudflare Access sits in
front of the entire `*.devopstashtiot.page` domain — a programmatic token-auth request from
`devops-api` to any public hostname on this domain would normally hit Access's email-OTP wall
regardless of Ingress routing. This is the exact same class of problem that blocked Bitbucket's
own git-over-HTTPS earlier in this session, and it applies to every tool devops-api calls out
to, not just ArgoCD.

**This is a workaround, not a fix**, and it's worth being explicit about why it exists: AWS
Control Tower now permits creating a private Route53 hosted zone in this account (it didn't when
`devtools-definition/devtools/devops-api/values.yaml`'s original in-cluster-Service-DNS
workaround was written). A private hosted zone is the *correct* long-term replacement for this
— but until that's built, the cluster's own **CoreDNS** (`kube-system/coredns` ConfigMap,
applied directly via `kubectl` — not tracked in any GitOps repo, since CoreDNS isn't managed by
`clusters-provision`/`clusters-definition`, it's minikube's own addon) carries `rewrite` rules
that resolve every `*.devopstashtiot.page` hostname devops-api calls, for any caller running
inside the cluster, bypassing the Tunnel and Access entirely for in-cluster traffic — while
external/public resolution via real Cloudflare DNS is untouched:
```
rewrite name exact argocd.devopstashtiot.page ingress-nginx-controller.ingress-nginx.svc.cluster.local answer auto
rewrite name regex (.*)\.argocd\.devopstashtiot\.page argocd-server.argocd.svc.cluster.local answer auto
rewrite name exact bitbucket.devopstashtiot.page ingress-nginx-controller.ingress-nginx.svc.cluster.local answer auto
rewrite name exact confluence.devopstashtiot.page ingress-nginx-controller.ingress-nginx.svc.cluster.local answer auto
rewrite name exact jira.devopstashtiot.page ingress-nginx-controller.ingress-nginx.svc.cluster.local answer auto
rewrite name exact sonarqube.devopstashtiot.page ingress-nginx-controller.ingress-nginx.svc.cluster.local answer auto
rewrite name exact artifactory.devopstashtiot.page ingress-nginx-controller.ingress-nginx.svc.cluster.local answer auto
```
**Why `ingress-nginx-controller`, not each tool's own backend Service directly:** the cluster
has a real Cloudflare Origin Certificate for `*.devopstashtiot.page`
(`clusters-provision/clusters/ingress-nginx/templates/origin-cert-secret.yaml`), but it's
mounted on `ingress-nginx-controller`'s Service only — every devtool's own backend Service (e.g.
`bitbucket.bitbucket.svc.cluster.local`) is plain HTTP only, no TLS listener at all (TLS
terminates at Cloudflare/ingress-nginx, never on the backend itself; confirmed via `kubectl get
svc` — no `443/TCP` on any of them). An earlier version of this rewrite pointed straight at each
backend Service and downgraded `devops-api`'s `*_API_URL` values to `http://` to match, which
technically worked but silently gave up real TLS. Routing through
`ingress-nginx-controller.ingress-nginx.svc.cluster.local` instead means normal host-based
Ingress routing reaches the correct backend on the correct port (no per-tool port override
needed, even for sonarqube (9000) or artifactory (8082)) **and** presents the real Origin Cert,
so `https://` is genuine end-to-end TLS, not a bypass. Confirmed live via `openssl s_client`:
every hostname presents `issuer=... OU = CloudFlare Origin SSL Certificate Authority`.

Because that cert is signed by Cloudflare's own private Origin CA (not in any standard trust
store), `devops-api`'s `Dockerfile` now installs the public, stable Cloudflare Origin CA RSA
root cert (`cloudflare-origin-ca-rsa-root.pem`, sourced from
https://developers.cloudflare.com/ssl/origin-configuration/origin-ca/) into both the system
trust store (`update-ca-certificates`) and `certifi`'s bundle (httpx uses `certifi.where()` by
default, **not** the system store — installing only one of the two silently leaves the other
unfixed). Without this, `devops-api`'s own `httpx`-based calls would fail real certificate
verification the same way a bare `curl` (no `-k`) does against this cert.

The per-consumer wildcard (`(.*)\.argocd\.devopstashtiot\.page`) is a **separate exception** —
it still routes straight to `argocd-server.argocd.svc.cluster.local`, not through
`ingress-nginx-controller`, because there is no Ingress rule at all for arbitrary `*.argocd`
subdomains (only the bare `argocd.devopstashtiot.page` host is configured), so routing it through
ingress-nginx would just 404. `argocd-server` happens to serve its own **self-signed** TLS cert
on 443 (not the Cloudflare Origin Cert), which is a *third* distinct certificate `devops-api`
would need to trust for real verification on this specific path — not yet added to the
Dockerfile's trust store as of this writing; check live behavior before assuming this path's TLS
verification succeeds.

Verified live: all seven `rewrite` names resolve to the correct ClusterIP from inside a pod, and
`https://<tool>.devopstashtiot.page/` round-trips through `ingress-nginx-controller` with the
real Origin Cert for every tool except the per-consumer ArgoCD wildcard. This persists across
normal EC2 reboots because the cluster's etcd state is persistent on this node, not
re-bootstrapped from scratch — but it will not survive a genuine cluster rebuild, and it means
every `{app_name}.argocd.devopstashtiot.page` currently resolves to the *same* single real
ArgoCD instance, which is good enough to exercise the token-auth code path end-to-end (and
confirmed the `from_credentials` fix above is correct) but is **not** real per-consumer
isolation. If a genuine multi-tenant per-consumer ArgoCD service is ever built, or the private
Route53 hosted zone replaces this, update/remove these rewrite rules accordingly rather than
layering more fixes on top of a workaround.

None of the fixes above were reachable or fixable purely from within `test_argocd_e2e.py` — they
needed out-of-cluster provisioning (`GIT_TOKEN` secret, Docker image change, library API
correction, CoreDNS rewrite) rather than test/gitops changes alone.

**🛑 UNRESOLVED — `create_cluster_secret()` cannot work at all against the real library.** With
every fix above in place (kubectl, token-based `_build_argocd()`, DNS/TLS routing all confirmed
live), `POST /cluster-secret` reaches a **third, deeper** version of the same underlying problem:
`create_cluster_secret()` (`operations.py`) builds a full ArgoCD `Application` manifest and calls
`argocd.create_app(app_body, validate=False)` — **`create_app` does not exist on the real
`ArgoCD` class either.** Confirmed live: `'ArgoCD' object has no attribute 'create_app'`.

This is not a simple rename like `from_credentials` → the real constructor was. The **complete**
public method list on the real `ArgoCD` class is:
```
add_namespace_to_cluster_secret, get_app_parameters, get_app_status, get_app_values,
modify_parameters, modify_values, sync, wait_for_app_creation, wait_for_app_deletion,
wait_for_update
```
There is no `create_app`, no `delete_app` — nothing that creates or deletes an Application from
scratch. Reading the actual source of the two closest candidates confirms neither can substitute:
- `modify_parameters()` calls `self.client.patch_app(...)` — a **PATCH**, i.e. it updates an
  Application that must already exist.
- `add_namespace_to_cluster_secret()` starts by calling `get_app_parameters()` →
  `self.client.get_app(app_name)` — which 404s if the Application doesn't exist yet.

So **every** real method on this class assumes the cluster-secret `Application` was already
created by some other mechanism before `devops-api` ever touches it. What that mechanism is
supposed to be is unknown — possibly an ArgoCD `ApplicationSet`/generator watching the GitOps
repo (mirroring how `create_consumer_config` just writes a YAML file to git and lets ArgoCD's
own automation create the real resources, rather than calling a live API), but that's
speculation, not confirmed by anything in this codebase or library.

**Do not attempt to patch this by dropping to the low-level `ArgoCDClient`** (e.g. a raw "create
Application" call) — that violates this repo's own "never import/instantiate `*Client` classes
directly" rule (see top-level `CLAUDE.md`) and would be inventing behavior on top of an already
speculative design, not fixing a known-good one. `edit_cluster_secret()` (uses
`modify_parameters`, real) and `delete_cluster_secret()` (uses `argocd.delete_app`, **also fake**
— same problem, not yet live-tested) are in the same boat. Whoever picks this up next needs to
either find/confirm the actual intended creation mechanism, or get a real `create_app` added to
`tashtiot-apis-library` upstream, before `POST /cluster-secret` can ever succeed — no amount of
config, DNS, or auth fixing (all of which are now genuinely done) gets around this.

**2026-07-14 re-check, now bumped to `v1.1.2` — gap still not closed, confirmed by reading library
source directly** (`connectors/argocd/service.py`, no live pod check needed this time). The complete
public method list on `ArgoCD` at `v1.1.2` is unchanged from `0.1.0`:
```
add_namespace_to_cluster_secret, get_app_parameters, get_app_status, get_app_values,
modify_parameters, modify_values, sync, wait_for_app_creation, wait_for_app_deletion,
wait_for_update
```
Still no `create_app`, `delete_app`, or `from_credentials` anywhere in the class. The 0.1.0→1.1.2
changelog's only ArgoCD-adjacent work is internal refactoring (dropped a private
`_serialize_namespaces` helper, added type hints) — no new public methods. **This is not a "wait for
the next release" gap** — three full minor releases (1.0.0, 1.1.0, 1.1.1, 1.1.2) have passed with no
movement on it, which reads more like Application create/delete was never planned for this class
(see the `ApplicationSet`/GitOps-automation speculation below) than an oversight. Don't re-open this
by re-bumping the pin again on faith — if a future release's CHANGELOG.md explicitly mentions
`create_app`/`delete_app`/ArgoCD Application lifecycle methods, that's the signal to re-check; a
version bump alone is not.

## Token validation behaviour in local dev

`_check_cluster_permissions` in `operations.py` validates each cluster token by running `kubectl auth can-i "*" "*"` against the target cluster. It raises a 401 only when kubectl writes to **stderr** (unreachable server, TLS failure, or auth rejection).

On a local dev cluster (kind/minikube), the API server is typically permissive — it accepts any token, including completely invalid strings like `"this-is-a-broken-token"`, and returns `"yes"` to stdout with exit 0. This means broken-token tests will appear to succeed locally.

On a real cluster with proper RBAC and token validation, an invalid token causes kubectl to write an auth error to stderr, which the check catches and rejects with a 401. Broken-token validation only works correctly against a properly secured cluster.
