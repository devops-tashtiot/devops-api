import os

import httpx
import pytest
import yaml

# All overridable via env vars so this file can run against either a local stack or a real
# deployed environment — e.g. against this platform's cluster via
# `kubectl port-forward`:
#   kubectl -n bitbucket port-forward svc/bitbucket 17990:80
#   kubectl -n devops-api port-forward svc/devops-api 15000:5000
#   BITBUCKET_URL=http://localhost:17990 API_URL=http://localhost:15000 \
#   BITBUCKET_USER=svc-devops-tashtiot BITBUCKET_PASS=<password> \
#   pytest tests/v1/argocd/test_argocd_e2e.py -v -m integration
BITBUCKET_URL = os.environ.get("BITBUCKET_URL", "http://localhost:7990")
API_URL = os.environ.get("API_URL", "http://localhost:5001")
PREFIX = "/api/devops/v1/argocd"
BITBUCKET_USER = os.environ.get("BITBUCKET_USER", "nati")
BITBUCKET_PASS = os.environ.get("BITBUCKET_PASS", "12345678")

# GIT_PROJECT_KEY / ARGOCD_AAS_REPO_SLUG that devops-api is actually configured with.
# NOTE: on the real cluster (checked live, 2026-07-13), the "argocd" repo does not exist yet
# under the ARGO project (same project used by the sonarqube module — see
# app/v1/sonarqube/CLAUDE.md) — shared GitOps infrastructure this feature depends on, not a
# disposable test fixture. _ensure_gitops_project_and_repo() below creates it if missing and
# never tears it down; only the throwaway consumer name/file created inside it per test run is
# cleaned up.
GIT_PROJECT_KEY = os.environ.get("E2E_GIT_PROJECT_KEY", "ARGO")
ARGOCD_REPO_SLUG = os.environ.get("E2E_ARGOCD_REPO_SLUG", "argocd")

CONSUMER_NAME = os.environ.get("E2E_CONSUMER_NAME", "e2e-test-consumer")
ENV = os.environ.get("E2E_ARGOCD_ENV", "int")

REQUEST_METADATA = {
    "project": "devops-api-e2e",
    "network": "test",
    "region": "test",
    "space": "test",
    "environment": "test",
}


@pytest.fixture(scope="module")
def bb():
    with httpx.Client(base_url=BITBUCKET_URL, auth=(BITBUCKET_USER, BITBUCKET_PASS), timeout=30.0) as client:
        yield client


# devops-api itself now requires a Bearer token (tashtiot-apis-library's inbound auth,
# AUTH_ENABLED=true in the live deployment) — mint one via client_credentials against the
# durable devops-api-e2e-tests Keycloak client (clusters-provision/clusters/rhbk). Falls back
# to no Authorization header if the secret isn't set (e.g. a local AUTH_ENABLED=false stack).
E2E_TOKEN_URL = os.environ.get("E2E_KEYCLOAK_TOKEN_URL", "https://rhbk.devopstashtiot.page/realms/devtools/protocol/openid-connect/token")
E2E_CLIENT_ID = os.environ.get("E2E_KEYCLOAK_CLIENT_ID", "devops-api-e2e-tests")
E2E_CLIENT_SECRET = os.environ.get("E2E_KEYCLOAK_CLIENT_SECRET", "")


def _api_auth_headers() -> dict:
    if not E2E_CLIENT_SECRET:
        return {}
    resp = httpx.post(
        E2E_TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": E2E_CLIENT_ID,
            "client_secret": E2E_CLIENT_SECRET,
            "scope": "devops-api-audience",
        },
        timeout=10.0,
    )
    resp.raise_for_status()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture(scope="module")
def api():
    with httpx.Client(base_url=API_URL, timeout=30.0, headers=_api_auth_headers()) as client:
        yield client


@pytest.fixture(scope="module", autouse=True)
def _ensure_gitops_project_and_repo(bb: httpx.Client):
    """Idempotent setup only — creates the shared GitOps project/repo if absent, never deletes
    them. Mirrors tests/v1/sonarqube/test_sonarqube_consumer_e2e.py's fixture; the ARGO project
    is shared across both modules' consumer-config repos."""
    project = bb.get(f"/rest/api/latest/projects/{GIT_PROJECT_KEY}")
    if project.status_code == 404:
        r = bb.post("/rest/api/latest/projects", json={"key": GIT_PROJECT_KEY, "name": GIT_PROJECT_KEY.lower()})
        assert r.status_code == 201, r.text
    else:
        assert project.status_code == 200, project.text

    repo = bb.get(f"/rest/api/latest/projects/{GIT_PROJECT_KEY}/repos/{ARGOCD_REPO_SLUG}")
    if repo.status_code == 404:
        r = bb.post(
            f"/rest/api/latest/projects/{GIT_PROJECT_KEY}/repos",
            json={"name": ARGOCD_REPO_SLUG, "scmId": "git"},
        )
        assert r.status_code == 201, r.text
    else:
        assert repo.status_code == 200, repo.text


def _consumer_path(env: str, name: str) -> str:
    return f"{env}/consumers/{name}/config.yaml"


def _get_config_yaml(bb: httpx.Client, env: str, name: str) -> dict | None:
    r = bb.get(
        f"/rest/api/latest/projects/{GIT_PROJECT_KEY}/repos/{ARGOCD_REPO_SLUG}/raw/{_consumer_path(env, name)}"
    )
    if r.status_code == 404:
        return None
    assert r.status_code == 200, r.text
    return yaml.safe_load(r.text)


def _delete_config_if_exists(bb: httpx.Client, api: httpx.Client, env: str, name: str):
    if _get_config_yaml(bb, env, name) is not None:
        r = api.delete(f"{PREFIX}/{env}/{name}")
        assert r.status_code == 200, r.text
    assert _get_config_yaml(bb, env, name) is None


@pytest.mark.integration
def test_create_delete_consumer_config_full_flow(bb, api):
    # --- clean state ---
    _delete_config_if_exists(bb, api, ENV, CONSUMER_NAME)

    # --- create consumer config via our API ---
    r = api.post(
        f"{PREFIX}/",
        json={
            "metadata": REQUEST_METADATA,
            "spec": {
                "name": CONSUMER_NAME,
                "environment": ENV,
                "size": "small",
                "include_resources": ["ConfigMap", "Deployment"],
                "ad_admin_group": "my_group",
            },
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "successful"

    # --- verify content committed to Bitbucket directly ---
    config = _get_config_yaml(bb, ENV, CONSUMER_NAME)
    assert config is not None, "config.yaml was not committed"
    assert config["name"] == CONSUMER_NAME
    assert config["size"] == "small"
    assert set(config["include_resources"]) == {"ConfigMap", "Deployment"}
    assert config["ad_admin_group"] == "my_group"
    assert "extra_roles" not in config

    # --- delete consumer config via our API ---
    r = api.delete(f"{PREFIX}/{ENV}/{CONSUMER_NAME}")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "successful"

    # --- verify file is actually gone from Bitbucket directly ---
    assert _get_config_yaml(bb, ENV, CONSUMER_NAME) is None


@pytest.mark.integration
def test_create_consumer_config_with_rbac_lines(bb, api):
    _delete_config_if_exists(bb, api, ENV, CONSUMER_NAME)

    r = api.post(
        f"{PREFIX}/",
        json={
            "metadata": REQUEST_METADATA,
            "spec": {
                "name": CONSUMER_NAME,
                "environment": ENV,
                "size": "small",
                "include_resources": ["ConfigMap"],
                "ad_admin_group": "my_group",
                "g_lines": [{"ad_group": "DEV_MyTeam", "role": "myteam"}],
                "p_lines": [{"role": "myteam", "resource": "applications", "action": "get", "object": "myteam/*"}],
                "extra_roles": ["p, role:extra, projects, get, myproj, allow"],
            },
        },
    )
    assert r.status_code == 200, r.text

    config = _get_config_yaml(bb, ENV, CONSUMER_NAME)
    assert config is not None
    assert config["extra_roles"] == [
        'g, "DEV_MyTeam", role:myteam',
        "p, role:myteam, applications, get, myteam/*, allow",
        "p, role:extra, projects, get, myproj, allow",
    ]

    _delete_config_if_exists(bb, api, ENV, CONSUMER_NAME)


@pytest.mark.integration
def test_get_sizes_returns_allowed_values(api):
    r = api.get(f"{PREFIX}/sizes")
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"extraLarge", "large", "medium", "small"}


@pytest.mark.integration
def test_get_include_resources_returns_allowed_values(api):
    r = api.get(f"{PREFIX}/include-resources")
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"ExternalSecret", "ConfigMap", "Deployment"}


@pytest.mark.integration
def test_get_rbac_resources_returns_allowed_values(api):
    r = api.get(f"{PREFIX}/rbac-resources")
    assert r.status_code == 200, r.text
    assert "applications" in r.json()
    assert "*" in r.json()


@pytest.mark.integration
def test_get_rbac_actions_returns_allowed_values(api):
    r = api.get(f"{PREFIX}/rbac-actions")
    assert r.status_code == 200, r.text
    assert "get" in r.json()
    assert "*" in r.json()


@pytest.mark.integration
def test_get_environments_returns_allowed_values(api):
    r = api.get(f"{PREFIX}/environments")
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"prod", "dr", "int"}


# --- cluster-secret routes ---
#
# NOTE (2026-07-14, confirmed live — see app/v1/argocd/CLAUDE.md "Cluster-secret routes"):
# _build_argocd() targets https://{app_name}.argocd.{DOMAIN_SUFFIX} — a *per-consumer* ArgoCD
# instance. The wildcard DNS record for *.argocd.devopstashtiot.page now exists, but there is
# no actual per-consumer ArgoCD backend behind it: the platform's Ingress only serves the bare
# argocd.devopstashtiot.page hostname (one real instance, one real Ingress rule), and Cloudflare
# Access sits in front of the whole domain and would block any programmatic token-auth request
# regardless. ARGOCD_TOKEN below authenticates fine against the real, in-cluster ArgoCD instance
# (see /devtools/argocd/api-token in SSM) but app_name can never actually route to it — this
# test is written against the intended per-consumer-instance behavior and will keep failing at
# the network layer until that provisioning gap is closed; it is not a code bug in this module.
ARGOCD_TOKEN = os.environ.get("E2E_ARGOCD_TOKEN", "")
ARGOCD_APP_NAME = os.environ.get("E2E_ARGOCD_APP_NAME", "netanel")
ARGOCD_CHOSEN_NAME = os.environ.get("E2E_ARGOCD_CHOSEN_NAME", "e2e-test")
ARGOCD_CLUSTER_TOKEN = os.environ.get("E2E_ARGOCD_CLUSTER_TOKEN", "")
ARGOCD_CLUSTER_ADDRESS = os.environ.get("E2E_ARGOCD_CLUSTER_ADDRESS", "https://kubernetes.default.svc")

CLUSTER_SECRET_PAYLOAD = {
    "metadata": REQUEST_METADATA,
    "spec": {
        "token": ARGOCD_TOKEN,
        "chosen_name": ARGOCD_CHOSEN_NAME,
        "app_name": ARGOCD_APP_NAME,
        "application_clusters": [{
            "name": "openshift",
            "namespace": "default",
            "address": ARGOCD_CLUSTER_ADDRESS,
            "token": ARGOCD_CLUSTER_TOKEN,
        }],
    },
}


@pytest.mark.integration
@pytest.mark.skipif(not ARGOCD_CLUSTER_TOKEN, reason="set E2E_ARGOCD_CLUSTER_TOKEN to a live cluster-admin token to run")
def test_create_update_delete_cluster_secret_full_flow(api):
    # --- clean state (ignore failure — may not exist yet) ---
    api.delete(f"{PREFIX}/cluster-secret", params={
        "token": ARGOCD_TOKEN,
        "app_name": ARGOCD_APP_NAME, "chosen_name": ARGOCD_CHOSEN_NAME,
    })

    # --- create cluster secret via our API ---
    r = api.post(f"{PREFIX}/cluster-secret", json=CLUSTER_SECRET_PAYLOAD)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "successful"

    # --- update it ---
    update_payload = {
        "metadata": REQUEST_METADATA,
        "spec": {
            "token": ARGOCD_TOKEN,
            "application_clusters": [{
                "name": "openshift",
                "namespace": "default,kube-system",
                "address": ARGOCD_CLUSTER_ADDRESS,
                "token": ARGOCD_CLUSTER_TOKEN,
            }],
        },
    }
    r = api.put(f"{PREFIX}/cluster-secret/{ARGOCD_APP_NAME}/{ARGOCD_CHOSEN_NAME}", json=update_payload)
    assert r.status_code == 200, r.text

    # --- delete it ---
    r = api.delete(f"{PREFIX}/cluster-secret", params={
        "token": ARGOCD_TOKEN,
        "app_name": ARGOCD_APP_NAME, "chosen_name": ARGOCD_CHOSEN_NAME,
    })
    assert r.status_code == 200, r.text
