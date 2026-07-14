import os

import httpx
import pytest
import yaml

# All overridable via env vars so this file can run against either the local docker-compose
# stack or a real deployed environment — e.g. against this platform's cluster via
# `kubectl port-forward`:
#   kubectl -n bitbucket port-forward svc/bitbucket 17990:80
#   kubectl -n devops-api port-forward svc/devops-api 15000:5000
#   BITBUCKET_URL=http://localhost:17990 API_URL=http://localhost:15000 \
#   BITBUCKET_USER=svc-devops-tashtiot BITBUCKET_PASS=<password> \
#   pytest tests/v1/sonarqube/test_sonarqube_consumer_e2e.py -v -m integration
BITBUCKET_URL = os.environ.get("BITBUCKET_URL", "http://localhost:7990")
API_URL = os.environ.get("API_URL", "http://localhost:5001")
PREFIX = "/api/devops/v1/sonarqube"
BITBUCKET_USER = os.environ.get("BITBUCKET_USER", "nati")
BITBUCKET_PASS = os.environ.get("BITBUCKET_PASS", "12345678")

# GIT_PROJECT_KEY / SONARQUBE_AAS_REPO_SLUG that devops-api is actually configured with.
# NOTE: on the real cluster (checked live), neither the project nor the repo exists yet —
# this is genuine shared GitOps infrastructure the whole consumer-config feature depends on,
# not a disposable test fixture. _ensure_gitops_project_and_repo() below creates it if
# missing and never tears it down; only the throwaway consumer name/file created inside it
# per test run is cleaned up.
GIT_PROJECT_KEY = os.environ.get("E2E_GIT_PROJECT_KEY", "ARGO")
SONARQUBE_REPO_SLUG = os.environ.get("E2E_SONARQUBE_REPO_SLUG", "sonarqube-as-a-service")

CONSUMER_NAME = os.environ.get("E2E_CONSUMER_NAME", "e2e-test-consumer")

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
    them. Confirmed live that neither exists yet on the real cluster; devops-api's Git connector
    has no create-project/create-repo route of its own (mirrors test_bitbucket_e2e.py's pattern
    of creating prerequisite Bitbucket state directly when the API under test has no route for
    it)."""
    project = bb.get(f"/rest/api/latest/projects/{GIT_PROJECT_KEY}")
    if project.status_code == 404:
        r = bb.post("/rest/api/latest/projects", json={"key": GIT_PROJECT_KEY, "name": GIT_PROJECT_KEY.lower()})
        assert r.status_code == 201, r.text
    else:
        assert project.status_code == 200, project.text

    repo = bb.get(f"/rest/api/latest/projects/{GIT_PROJECT_KEY}/repos/{SONARQUBE_REPO_SLUG}")
    if repo.status_code == 404:
        r = bb.post(
            f"/rest/api/latest/projects/{GIT_PROJECT_KEY}/repos",
            json={"name": SONARQUBE_REPO_SLUG, "scmId": "git"},
        )
        assert r.status_code == 201, r.text
    else:
        assert repo.status_code == 200, repo.text


def _consumer_path(name: str) -> str:
    return f"consumers/{name}/config.yaml"


def _get_config_yaml(bb: httpx.Client, name: str) -> dict | None:
    r = bb.get(
        f"/rest/api/latest/projects/{GIT_PROJECT_KEY}/repos/{SONARQUBE_REPO_SLUG}/raw/{_consumer_path(name)}"
    )
    if r.status_code == 404:
        return None
    assert r.status_code == 200, r.text
    return yaml.safe_load(r.text)


def _delete_config_if_exists(bb: httpx.Client, api: httpx.Client, name: str):
    if _get_config_yaml(bb, name) is not None:
        r = api.delete(f"{PREFIX}/consumer/{name}")
        assert r.status_code == 200, r.text
    assert _get_config_yaml(bb, name) is None


@pytest.mark.integration
def test_create_update_delete_consumer_config_full_flow(bb, api):
    # --- clean state ---
    _delete_config_if_exists(bb, api, CONSUMER_NAME)

    # --- create consumer config via our API ---
    r = api.post(
        f"{PREFIX}/consumer/",
        json={
            "metadata": REQUEST_METADATA,
            "spec": {
                "name": CONSUMER_NAME,
                "plugins_list": ["https://s3/sonar-plugins/plugin-a.jar", "https://s3/sonar-plugins/plugin-b.jar"],
                "size": "medium",
            },
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "successful"

    # --- verify content committed to Bitbucket directly ---
    config = _get_config_yaml(bb, CONSUMER_NAME)
    assert config is not None, "config.yaml was not committed"
    assert config["name"] == CONSUMER_NAME
    assert config["plugins_list"] == "https://s3/sonar-plugins/plugin-a.jar, https://s3/sonar-plugins/plugin-b.jar"
    assert config["size"] == "medium"

    # --- update consumer config via our API ---
    r = api.put(
        f"{PREFIX}/consumer/{CONSUMER_NAME}",
        json={
            "metadata": REQUEST_METADATA,
            "spec": {
                "plugins_list": ["https://s3/sonar-plugins/plugin-c.jar"],
                "size": "big",
            },
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "successful"

    # --- verify updated content ---
    config = _get_config_yaml(bb, CONSUMER_NAME)
    assert config is not None
    assert config["plugins_list"] == "https://s3/sonar-plugins/plugin-c.jar"
    assert config["size"] == "big"

    # --- delete consumer config via our API ---
    r = api.delete(f"{PREFIX}/consumer/{CONSUMER_NAME}")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "successful"

    # --- verify file is actually gone from Bitbucket directly ---
    assert _get_config_yaml(bb, CONSUMER_NAME) is None


@pytest.mark.integration
def test_create_consumer_config_default_size_omits_size_key(bb, api):
    _delete_config_if_exists(bb, api, CONSUMER_NAME)

    r = api.post(
        f"{PREFIX}/consumer/",
        json={"metadata": REQUEST_METADATA, "spec": {"name": CONSUMER_NAME}},
    )
    assert r.status_code == 200, r.text

    config = _get_config_yaml(bb, CONSUMER_NAME)
    assert config is not None
    assert "size" not in config
    assert "plugins_list" not in config

    _delete_config_if_exists(bb, api, CONSUMER_NAME)


@pytest.mark.integration
def test_get_sizes_returns_allowed_values(api):
    r = api.get(f"{PREFIX}/sizes")
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"default", "medium", "big"}
