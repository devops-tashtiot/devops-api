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

**Where the valid resource/action lists come from (`schemas.py:13-45`).** The `p` line's
`<resource>`/`<action>` fields are constrained twice, in two different ways, from the same
underlying list: `_RESOURCE`/`_ACTION` (regex alternations used inside `RoleLine`'s pattern, for
raw `extra_roles` strings) and `RbacResourceEnum`/`RbacActionEnum` (real Python enums used by the
structured `PLine` model's `resource`/`action` fields, and also exposed live via `GET
/rbac-resources`/`GET /rbac-actions` so callers can discover valid values at runtime instead of
guessing). Both are **hardcoded**, transcribed by hand from
[ArgoCD's RBAC spec](https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/) — the same
situation as the `config` field's namespace lists below (no live ArgoCD API returns "the current
valid RBAC resource/action list", so there's nothing to fetch instead).

**⚠️ Check this again on the next ArgoCD version upgrade.** If a future ArgoCD version adds a new
RBAC resource type or action (the way `applicationsets` was presumably added when ArgoCD
introduced ApplicationSets as a feature), both `_RESOURCE`/`_ACTION` and
`RbacResourceEnum`/`RbacActionEnum` would need updating by hand to match — until then, a
perfectly valid new RBAC line would be rejected as invalid by this API. Whoever bumps the ArgoCD
chart/image version on this platform next should re-read the RBAC spec link above against
whatever version is being upgraded to and update all four of these (the two regex alternations
and the two enum classes need to stay in sync with each other, not just with ArgoCD).

## ConsumerConfigSpec — `config` field (`ConsumerExtraConfig`)

`config` is an optional field on `POST /` letting a caller pass extra key/value overrides for
ArgoCD's own `argocd-cm` and `argocd-cmd-params-cm` config files, via two optional dicts:
`extra_argocd_cm_args` and `extra_argocd_params`. These get written verbatim into the consumer's
`config.yaml` under a `config:` key (`operations.py:171-178`) — something downstream (the ArgoCD
GitOps chart, in a different repo) is what actually turns that key into real ConfigMap entries.

**2026-07-20 — removed the namespace-prefix whitelist.** `validate_keys_and_yaml` (renamed
`validate_yaml`) used to reject any key whose first dot-segment wasn't in one of two hardcoded
frozensets (`_ARGOCD_CM_NAMESPACES`/`_ARGOCD_PARAMS_NAMESPACES`), transcribed by hand from
ArgoCD's own docs for these two files. Removed because there's no live API to keep that list in
sync with ArgoCD's actual, evolving config schema (unlike, say, Jira/Artifactory roles, which
this repo's own convention says to fetch live rather than hardcode) — a future ArgoCD version
adding a new top-level config namespace would have been silently rejected as "unknown" until
someone remembered to update the two frozensets by hand. Any key/prefix is accepted now; only the
YAML-validity check for multi-line values (a value containing `\n` must parse as valid YAML) was
kept — that's a genuinely independent safety check, unrelated to whether ArgoCD's schema itself
has changed.

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
ExternalSecret just to avoid it).

**2026-07-14, re-verified live end-to-end — `DELETE /{env}/{name}` genuinely works now.** First
retest after mounting the key still failed, differently: `Load key "/root/.ssh/id_ed25519": error
in libcrypto`. Root cause: the private key was stored in SSM via `aws ssm put-parameter --value
"$(cat id_ed25519)"` — bash's `$(...)` command substitution strips trailing newlines, silently
dropping the newline `ssh-keygen` writes after `-----END OPENSSH PRIVATE KEY-----`, which OpenSSH's
key parser requires. Confirmed via `aws ssm get-parameter --output json` (the only output mode that
doesn't itself re-add a trailing newline, unlike `--output text`) that the stored value was missing
it. Fixed by rewriting the SSM parameter with the newline restored, forcing the `ExternalSecret`'s
refresh (`kubectl annotate externalsecret ... force-sync=$(date +%s)` — it doesn't re-poll SSM
otherwise until its `refreshInterval: 1h` elapses), and restarting the deployment. Reran
`test_create_delete_consumer_config_full_flow` against the live API: **passes.** `DELETE /{env}/{name}`
is fixed, fully, confirmed live — not just "the error changed shape" this time.

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

**2026-07-19 — gap closed, `requirements.txt` bumped to `v1.2.1`.**
[`apis-library#15`](https://github.com/Platform-Infra-Org/apis-library/pull/15) ("Add
create_app/delete_app for Application lifecycle") merged and shipped in `v1.2.0`. Confirmed by
reading the real `v1.2.1` source (`connectors/argocd/service.py` at that tag): `ArgoCD` now has
```python
async def create_app(self, app_definition, validate: bool = True, upsert: bool = False, wait: bool = False) -> ArgoApplication
async def delete_app(self, app_name: str, app_namespace: Optional[str] = None, cascade: bool = True, wait: bool = False) -> None
```
Both signatures already match how this module calls them —
`argocd.create_app(app_body, validate=False, wait=True)` (`operations.py:108`) and
`argocd.delete_app(argo_app_name, config.ARGOCD_APP_NAMESPACE)` (`operations.py:119`) — so no
call-site changes were needed, only the version bump. **This closes the code-level gap only.**
The actual live behavior of `POST/DELETE /cluster-secret*` against the real cluster (does
`create_app` really create a working Application, does the RBAC/SSO wiring from the "Outbound
auth" section above actually work end-to-end) has **not** been re-verified as of this note —
that's the next thing to do, not something to assume passes because the method now exists.

**`ssh_port` tracking, resolved the same day:** [`apis-library#12`](https://github.com/Platform-Infra-Org/apis-library/pull/12)
also merged (shipped in `v1.2.1`). `app/main.py`'s two `Git(...)` instantiations (sonarqube and
this module) now pass `ssh_port=global_config.GIT_SSH_PORT` (new field in `global_conf.py`,
default `7999`). At the time this was written, `devtools-definition/devtools/devops-api/values.yaml`
had **not** actually set `GIT_SSH_PORT` — this note incorrectly assumed it had. See the
2026-07-20 entry below for what actually shipped and was confirmed live.

**2026-07-20 — live-tested for the first time since the `ssh_port`/`v1.2.1` bump, found and fixed
a real regression.** Running the argocd e2e suite live (unit: 53/53 passed; e2e: 5/7 passed, 2
failed) showed `POST /` (create) succeeding every time but `DELETE /{env}/{name}` hanging until
the client's 30s timeout. Root-caused: `GIT_SSH_PORT` was never actually set in
`devtools-definition`, so `global_conf.py`'s code default of `7999` (Bitbucket's real SSH port)
was what got used — but the `clusters-provision/clusters/ingress-nginx` TCP-passthrough
ConfigMap only had a listener on `7995` (the old hardcoded value), forwarding to
`bitbucket/bitbucket:7999` internally. A direct socket/SSH test from inside the devops-api pod
confirmed it precisely: port `7999` on `bitbucket.devopstashtiot.page` timed out (nothing
listens there externally), port `7995` accepted a real SSH connection and authenticated
successfully. So the "ships and is actually deployed" condition the note above was waiting for
had technically shipped (the `ssh_port` param exists and defaults to the real port), but nobody
had updated the two sides of this pairing to agree.

Two ways to fix this were considered: change the ingress-nginx passthrough's key from `7995` to
`7999` (tried first, reverted), or set `GIT_SSH_PORT` explicitly to `7995` to match the existing
passthrough (**the one actually kept**). Fixed by:
- `devtools-definition/devtools/devops-api/values.yaml`: added `GIT_SSH_PORT: "7995"` explicitly
  under `env:` — no longer relies on the library/code default (which is `7999` and does **not**
  work through the current passthrough).
- `clusters-provision/clusters/ingress-nginx/values.yaml`: `tcp:` block **left at `"7995":
  "bitbucket/bitbucket:7999"`** (unchanged from its original form) — this pairing (ingress key
  `7995` + `GIT_SSH_PORT=7995`) is the one in effect, not real-port-everywhere. If this is ever
  revisited, **both** sides must change together — updating one without the other reproduces this
  exact hang.
- Required a `kubectl rollout restart deployment/devops-api -n devops-api` to actually pick up
  the new ConfigMap value — confirmed live that even after ArgoCD showed the app `Synced`, a pod
  restarted immediately afterward still read the old value once (a real observed race between
  ArgoCD's ConfigMap update and the restart), and only a second restart picked up `GIT_SSH_PORT=
  7995` correctly. Don't assume "ArgoCD says Synced" + one restart is sufficient without
  actually checking `env | grep GIT_SSH_PORT` (or the parsed `global_config.GIT_SSH_PORT`) inside
  the new pod.

Re-ran the full e2e suite after the fix: **7 passed, 1 skipped** (cluster-secret flow still
skipped, no live token) — `test_create_delete_consumer_config_full_flow` and
`test_create_consumer_config_with_rbac_lines` both pass now, confirmed against real Bitbucket.

## Outbound auth — migrated from a caller-supplied static token to SSO (2026-07-14)

`_build_argocd()` previously took a `token: str` argument sourced straight from the request
body (`ClusterSecretSpec.token`/`ClusterSecretUpdateSpec.token`/`ClusterSecretIdentifier.token`)
— every caller of `POST/PUT/DELETE /cluster-secret*` had to supply a real, long-lived ArgoCD API
token (generated once against the platform's actual ArgoCD instance, stored at
`/devtools/argocd/api-token` in SSM for live-testing). Migrated to
`tashtiot_apis_library.fastapi_template.security`'s outbound-SSO helpers instead —
`_build_argocd()` is now `async` and mints its own short-lived `client_credentials` token via
`get_sso_token_client(SSOConfig(...))`, so callers no longer supply any ArgoCD credential at
all. The `token` field was removed from all three cluster-secret schemas.

**Why not just enable service accounts on the existing `argocd` Keycloak client** (the one real
human logins already use) **and reuse it:** tested this live first before building anything.
Two separate problems, confirmed one at a time:

1. **Audience.** A plain `client_credentials` grant against the `argocd` client (with
   `serviceAccountsEnabled` temporarily flipped on for the test, then reverted) mints a token
   with `aud: account` (Keycloak's built-in default) — not `aud: argocd`. ArgoCD's `oidc.config`
   (`clientID: argocd`) validates the token's audience against exactly that, and the real API
   call 401'd with `"invalid session: failed to verify the token"` even though `azp` correctly
   read `argocd`. Confirmed by testing directly against `argocd-server`'s ClusterIP with a
   minted token before building anything further.
2. **RBAC.** ArgoCD's `policy.csv` is entirely group-based (`g, devops-tashtiot, role:admin`,
   sourced from a real AD group's `groups` claim). A service-account token has no AD group
   membership at all (`groups: null`) — even with the audience fixed, RBAC would still have
   nothing to match and deny with a 403, not grant anything.

**The fix — a dedicated client, not the shared browser-login one:**
- `clusters-provision/clusters/rhbk`: new `argocdServiceClient` (`devops-api-argocd`,
  confidential, `serviceAccountsEnabled: true`), sharing the same platform-wide OIDC client
  secret as every other client (`sharedClientSecretSsmParameter`) — same convention as
  `e2eTestClient`. Requests a new client scope, `devops-api-argocd-audience`, carrying two
  protocol mappers: an Audience mapper (`aud: argocd`) and a **hardcoded** `groups` claim
  (`["devops-api-argocd-svc"]`) — hardcoded, not the real `oidc-group-membership-mapper` the
  `groups` scope uses elsewhere, since a service account has no real AD group membership for
  that mapper to read.
- `devtools-definition/devtools/argocd/values.yaml`'s `policy.csv`: a scoped-down RBAC role
  bound to that synthetic group (`g, devops-api-argocd-svc, role:devops-api-argocd-svc`) —
  deliberately **not** `role:admin`. Only `get`/`create`/`update`/`delete`/`sync` on
  `applications` in the `default` project (the only project `create_cluster_secret()` ever
  targets — its `app_body` hardcodes `"project": "default"`), matching exactly what this
  module's code calls and nothing more.
- `app/v1/argocd/conf.py`: new `ARGOCD_SSO_TOKEN_URL`/`ARGOCD_SSO_CLIENT_ID`/
  `ARGOCD_SSO_CLIENT_SECRET`/`ARGOCD_SSO_SCOPE` fields. `_build_argocd()` builds one
  module-level `SSOConfig` (reused across calls so `get_sso_token_client()`'s token cache —
  memoized by object identity — is actually shared, not rebuilt fresh every request) and
  fetches a token from it per call.
- `devtools-definition/devtools/devops-api/values.yaml`: `ARGOCD_SSO_CLIENT_SECRET` sourced
  from the same `/devtools/rhbk/oidc-client-secret` SSM parameter via the existing `vault:`
  mechanism — one more consumer of that shared value, not a new secret.

**2026-07-21 — live-verified end-to-end for the first time, found a real bug: ArgoCD server
cannot verify Keycloak's TLS certificate.** Ran `test_create_update_delete_cluster_secret_full_flow`
against the real cluster with a real `argocd-cluster-sa` Kubernetes token
(`kubectl create token argocd-cluster-sa -n default`). `POST /cluster-secret` failed:

```
{"status":"Failed","status_code":401,"stdout":"Exception in ArgoCD. ArgoCD status code: 401. ArgoCD message: invalid session: failed to verify the token"}
```

Confirmed the *devops-api* side of the SSO flow is correct — minted a token directly against
`https://rhbk.devopstashtiot.page/realms/devtools/protocol/openid-connect/token` with
`client_id=devops-api-argocd`/the real client secret/`scope=devops-api-argocd-audience` and
decoded it: `aud: ["argocd", "account"]`, `groups: ["devops-api-argocd-svc"]` — exactly the
audience + RBAC-group shape the "Outbound auth" design above intended. The bug is entirely on
ArgoCD's side. `kubectl logs -n argocd deployment/argocd-server` showed the real error:

```
level=warning msg="Failed to verify session token: failed to verify provider token: token verification failed for all audiences: error for aud \"argocd\": failed to query provider \"https://rhbk.devopstashtiot.page/realms/devtools\": Get \"https://rhbk.devopstashtiot.page/realms/devtools/.well-known/openid-configuration\": tls: failed to verify certificate: x509: certificate signed by unknown authority"
```

**Root cause:** `argocd-server` has to make its own outbound HTTPS call to
`rhbk.devopstashtiot.page`'s OIDC discovery endpoint to verify any OIDC-issued Bearer token
(this happens per-verification, not just at startup — same "JWKS fetch is a live per-request
dependency, not a one-time startup check" gotcha this repo's own `CLAUDE.md` already documents
for devops-api's *inbound* auth). That hostname resolves in-cluster via the same CoreDNS
`rewrite` workaround documented above, routing through `ingress-nginx-controller` and
presenting the real Cloudflare Origin Certificate.

**Actual root cause, found and fixed same day — `oidc.config.rootCA` had the wrong certificate,
not a missing one.** `devtools-definition/devtools/argocd/values.yaml` already had an
`oidc.config.rootCA` field with a Cloudflare-related cert inlined (commit `8fe4244`, 2026-07-15,
an *earlier* session — not added as part of this finding), and `kubectl get cm argocd-cm -n
argocd` confirmed it was genuinely deployed, byte-for-byte matching the repo. Restarting
`argocd-server` (`kubectl rollout restart deployment/argocd-server -n argocd` — safe, it's the
API/UI component, separate from `argocd-application-controller` which does actual GitOps
reconciliation) to rule out a stale-pod-cache theory still reproduced the identical failure
against a pod that had just freshly re-read that ConfigMap — proving the deployed value itself
was wrong, not stale.

Decoded the actual cert with `openssl x509 -noout -subject -issuer -ext basicConstraints`:

```
subject=O=CloudFlare, Inc., OU=CloudFlare Origin CA, CN=CloudFlare Origin Certificate
issuer=C=US, O=CloudFlare, Inc., OU=CloudFlare Origin SSL Certificate Authority, ...
X509v3 Basic Constraints: critical
    CA:FALSE
```

This is `*.devopstashtiot.page`'s own **leaf** origin certificate (`CA:FALSE`) — the exact same
PEM ingress-nginx uses as its own TLS serving cert (SSM `/devtools/cloudflare/origin-cert-crt`)
— not the **CA** that signs it. A non-CA leaf certificate can never be a valid trust anchor for
verifying a *different* host's leaf certificate (rhbk's), no matter how "Cloudflare" the name on
it sounds, which is exactly why every Bearer-token verification failed with
`x509: certificate signed by unknown authority` regardless of how correct the SSO token itself
was.

**Fixed** — swapped `oidc.config.rootCA` for Cloudflare's own published, static Origin CA root
certificate (public, identical for every Cloudflare customer, not domain-specific; source:
https://developers.cloudflare.com/ssl/origin-configuration/origin-ca/ — the same file
`devops-api`'s own Dockerfile already installs as `cloudflare-origin-ca-rsa-root.pem` for the
identical reason). Verified `openssl verify -CAfile <new-cert> <old-leaf-cert>` → `OK` *before*
applying the change, confirming this is genuinely the certificate that signs what's on the wire.
Committed + pushed to `devtools-definition` (`c02ed81`), forced an ArgoCD hard refresh
(`kubectl patch application argocd -n argocd --type merge -p
'{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'`) rather than waiting for
the next poll cycle, and confirmed live the `argocd-cm` ConfigMap picked up the new cert content.

**Confirmed fixed live:** re-ran the test with a fresh token — `POST /cluster-secret` (create)
now returns `200`, no 401, for the first time ever. Manually called `DELETE /cluster-secret` via
devops-api directly (not bypassing it with `kubectl` this time) — also `200`, and confirmed via
`kubectl get application` that the Application was genuinely gone (`NotFound`). Both
`create_cluster_secret` and `delete_cluster_secret`'s ArgoCD-auth path are now proven working
end-to-end against the real cluster.

**Follow-on race, found in the same run and fixed immediately after — "another operation is
already in progress."** `PUT /cluster-secret/{app_name}/{chosen_name}` (update), called
immediately after create succeeds, failed with:

```
{"status":"Failed","status_code":400,"stdout":"Exception in ArgoCD. ArgoCD status code: 400. ArgoCD message: another operation is already in progress"}
```

Root cause: `argocd.sync(app_name)` (library `service.py`) only calls `client.sync_app(app_name)`
and returns immediately — it does not wait for the triggered sync *operation* to actually finish.
`create_cluster_secret()` called `create_app(wait=True)` (which does wait, via
`wait_for_app_creation`) then `sync()` (which doesn't), so `POST /cluster-secret` could return
`200` while ArgoCD was still mid-sync — an immediate follow-up `PUT`'s own `sync()` call then hit
ArgoCD's one-operation-at-a-time limit.

**Fixed, not by adding a fixed sleep** (which would be a guess — too short under load, wasted
time otherwise) **but by using the library's own real-completion primitive,
`ArgoCD.wait_for_update(app_name)`** — it polls `get_app` until the Application's status
fingerprint (revision/reconciled_at/op_finished_at/history length) actually changes, bounded by
`ARGOCD_APPLICATION_SET_TIMEOUT` (same 300s default already used elsewhere), the exact same
"wait for the real signal, not a duration" pattern the 2026-07-18 entry above already established
for `create_app`'s `wait=True` → `wait_for_app_creation`. Added:

- `create_cluster_secret()` (`operations.py`): `await argocd.wait_for_update(argo_app_name)`
  after `sync()`, so `POST /cluster-secret` doesn't return until the sync it triggered has
  genuinely finished.
- `edit_cluster_secret()` (`operations.py`): same addition after its own `sync()`, for symmetry —
  an immediate second update or a delete right after an update could hit the identical race
  otherwise.
- `delete_cluster_secret()` (`operations.py`): added `wait=True` to the `delete_app()` call
  (`argocd.delete_app(argo_app_name, config.ARGOCD_APP_NAMESPACE, wait=True)`) — the library's
  own docstring says this is "required before recreating an Application under the same name,"
  which is exactly what this test's own "clean state" step does (delete, then immediately
  create).

Unit tests updated to match (`tests/v1/argocd/test_argocd_routes.py`): the shared
`_mock_argocd_for_create()` fixture and the edit-route mocks now also stub `wait_for_update`
(a `MagicMock()` has no async-aware default, so an unstubbed `await
argocd.wait_for_update(...)` would raise `TypeError: object MagicMock can't be used in 'await'
expression` — this broke every mocked create/edit test the moment the real code started calling
it), plus new assertions locking in `wait_for_update.call_count == 1` and
`delete_app.call_args.kwargs["wait"] is True`.

**Confirmed live, full flow, first time ever passing:** re-ran
`test_create_update_delete_cluster_secret_full_flow` end-to-end (create → update → delete) — all
three steps passed in 3.55s, no race, no leftover Application afterward.

Also worth noting, unrelated to either bug above but visible in the same logs: `argocd-server`
logs `"config referenced '$argocd-secret:oidc.keycloak.clientSecret', but key does not exist in
secret"` on a ~10s repeating timer — the `clientSecret` substitution in `oidc.config` may not be
resolving. Not investigated since it didn't affect the Bearer-token path this session tests, but
flagging in case it turns out related or breaks the interactive browser login flow.

Left the leftover `e2e-test-cluster-secret` Application (a stuck artifact from an earlier
attempt at this same test, confirmed via its `spec` showing the *update* step's
`namespace: default,kube-system` — meaning create+update had worked before, but delete/cleanup
never completed) deleted via `kubectl delete application e2e-test-cluster-secret -n argocd`
directly (bypassing the still-broken auth path at that point in the investigation). The *second*
leftover, created by this session's own successful post-fix `POST /cluster-secret` call, was
cleaned up properly through devops-api's own `DELETE /cluster-secret` route instead — the first
real proof that route works end-to-end, not just a kubectl-level workaround.

**Both the trust-store bug and the operation-in-progress race are fixed and confirmed live** —
the full create → update → delete cluster-secret flow passes end-to-end against the real
cluster for the first time ever. Nothing known remaining on this path as of 2026-07-21.

**Status before this finding, kept for context:** code + config written and unit-tested
(mocked); the token-mint + audience + RBAC design was validated piece-by-piece live during the
original investigation (see the "Outbound auth" section above), but the actual deployed
`_build_argocd()` flow had never been exercised end-to-end against the live cluster until now.

## `create_cluster_secret` now waits for app visibility before syncing (2026-07-18)

`create_cluster_secret()` (`operations.py:108`) calls `argocd.create_app(app_body, validate=False, wait=True)`,
immediately followed by `argocd.sync(argo_app_name)`. `wait=True` was added to close a real
eventual-consistency race: `sync()` targets the just-created Application by name right after
`create_app` returns, but Argo CD's own API can still 403 on a `get_app` for a few seconds after
creation before it becomes visible — the exact condition `ArgoCD.wait_for_app_creation` (library
`service.py:261-274`) polls for. Without `wait=True`, `sync()` could occasionally race that window
and fail even though creation itself succeeded.

The library's own `create_app` default stays `wait=False` (this is the only call site that needs
it) — the wait is bounded by `ARGOCD_APPLICATION_SET_TIMEOUT` (`conf.py:39`, default `300`s): if the
app still isn't visible after that long, `wait_for_app_creation` raises `TimeoutError`, which
propagates out of this function as a failure (not proof creation itself failed — just that this
call gave up waiting for it to become visible).

**Known risk, not yet verified live:** this endpoint sits behind ingress-nginx and Cloudflare
Tunnel, both of which have proxy-level read timeouts shorter than 300s (ingress-nginx default
`proxy-read-timeout` ~60s; Cloudflare free-plan edge timeout ~100s). In a degraded scenario where
Argo CD is slow to make the app gettable, the proxy layer could time out and return an error to
the caller before `wait_for_app_creation` itself gives up — while `create_cluster_secret` keeps
running server-side regardless. Not hit in practice yet; flagging so it isn't a surprise if a
future live check for this route sees a `502`/`504` that isn't actually a devops-api bug.

## Token validation behaviour in local dev

`_check_cluster_permissions` in `operations.py` validates each cluster token by running `kubectl auth can-i "*" "*"` against the target cluster. It raises a 401 only when kubectl writes to **stderr** (unreachable server, TLS failure, or auth rejection).

On a local dev cluster (kind/minikube), the API server is typically permissive — it accepts any token, including completely invalid strings like `"this-is-a-broken-token"`, and returns `"yes"` to stdout with exit 0. This means broken-token tests will appear to succeed locally.

On a real cluster with proper RBAC and token validation, an invalid token causes kubectl to write an auth error to stderr, which the check catches and rejects with a 401. Broken-token validation only works correctly against a properly secured cluster.
