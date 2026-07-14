import pytest
from pydantic import ValidationError

from app.v1.argocd.schemas import (
    ApplicationCluster,
    ClusterSecretIdentifier,
    ClusterSecretSpec,
    ClusterSecretUpdateSpec,
    ConsumerConfigSpec,
)
from app.v1.argocd.conf import config
from app.global_conf import global_config

VALID_ENV = global_config.ARGOCD_ALLOWED_ENVS[0]
VALID_SIZE = global_config.ARGOCD_ALLOWED_SIZES[0]
VALID_RESOURCE = global_config.ARGOCD_ALLOWED_RESOURCES[0]

VALID_CLUSTER_DATA = {
    "name": "openshift",
    "namespace": "default",
    "address": "https://127.0.0.1:6443",
    "token": "some-token",
}


class TestConsumerConfigSpec:
    def test_valid_payload(self):
        spec = ConsumerConfigSpec(
            name="valid-consumer",
            environment=VALID_ENV,
            size=VALID_SIZE,
            include_resources=[VALID_RESOURCE],
            ad_admin_group="my-group",
        )
        assert spec.name == "valid-consumer"

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError):
            ConsumerConfigSpec(name="", environment=VALID_ENV, size=VALID_SIZE,
                               include_resources=[VALID_RESOURCE], ad_admin_group="g")

    def test_name_with_spaces_raises(self):
        with pytest.raises(ValidationError):
            ConsumerConfigSpec(name="bad name", environment=VALID_ENV, size=VALID_SIZE,
                               include_resources=[VALID_RESOURCE], ad_admin_group="g")

    def test_name_with_special_chars_raises(self):
        with pytest.raises(ValidationError):
            ConsumerConfigSpec(name="bad!name", environment=VALID_ENV, size=VALID_SIZE,
                               include_resources=[VALID_RESOURCE], ad_admin_group="g")

    def test_invalid_environment_raises(self):
        with pytest.raises(ValidationError):
            ConsumerConfigSpec(name="c", environment="nonexistent", size=VALID_SIZE,
                               include_resources=[VALID_RESOURCE], ad_admin_group="g")

    def test_invalid_size_raises(self):
        with pytest.raises(ValidationError):
            ConsumerConfigSpec(name="c", environment=VALID_ENV, size="supersize",
                               include_resources=[VALID_RESOURCE], ad_admin_group="g")

    def test_empty_include_resources_raises(self):
        with pytest.raises(ValidationError):
            ConsumerConfigSpec(name="c", environment=VALID_ENV, size=VALID_SIZE,
                               include_resources=[], ad_admin_group="g")

    def test_invalid_include_resource_raises(self):
        with pytest.raises(ValidationError):
            ConsumerConfigSpec(name="c", environment=VALID_ENV, size=VALID_SIZE,
                               include_resources=["Pod"], ad_admin_group="g")

    def test_name_with_hyphens_and_underscores_valid(self):
        spec = ConsumerConfigSpec(name="my_consumer-1", environment=VALID_ENV, size=VALID_SIZE,
                                  include_resources=[VALID_RESOURCE], ad_admin_group="g")
        assert spec.name == "my_consumer-1"


class TestApplicationCluster:
    def test_valid_cluster(self):
        c = ApplicationCluster(**VALID_CLUSTER_DATA)
        assert c.name == "openshift"

    def test_name_defaults_to_openshift(self):
        c = ApplicationCluster(namespace="default", address="https://127.0.0.1:6443", token="tok")
        assert c.name == "openshift"

    def test_empty_namespace_raises(self):
        with pytest.raises(ValidationError):
            ApplicationCluster(namespace="", address="https://127.0.0.1:6443", token="tok")

    def test_empty_address_raises(self):
        with pytest.raises(ValidationError):
            ApplicationCluster(namespace="default", address="", token="tok")

    def test_empty_token_raises(self):
        with pytest.raises(ValidationError):
            ApplicationCluster(namespace="default", address="https://127.0.0.1:6443", token="")

    def test_comma_separated_namespaces_valid(self):
        c = ApplicationCluster(namespace="ns1,ns2,ns3", address="https://127.0.0.1:6443", token="tok")
        assert c.namespace == "ns1,ns2,ns3"


class TestClusterSecretSpec:
    def _base(self):
        return {
            "token": "some-argocd-token",
            "chosen_name": "nati",
            "app_name": "netanel",
            "application_clusters": [VALID_CLUSTER_DATA],
        }

    def test_valid_payload(self):
        spec = ClusterSecretSpec(**self._base())
        assert spec.app_name == "netanel"

    def test_empty_token_raises(self):
        with pytest.raises(ValidationError):
            ClusterSecretSpec(**{**self._base(), "token": ""})

    def test_empty_application_clusters_raises(self):
        with pytest.raises(ValidationError):
            ClusterSecretSpec(**{**self._base(), "application_clusters": []})

    def test_invalid_chosen_name_pattern_raises(self):
        with pytest.raises(ValidationError):
            ClusterSecretSpec(**{**self._base(), "chosen_name": "bad name!"})

    def test_invalid_app_name_pattern_raises(self):
        with pytest.raises(ValidationError):
            ClusterSecretSpec(**{**self._base(), "app_name": "bad name!"})

    def test_multiple_clusters_valid(self):
        spec = ClusterSecretSpec(**{**self._base(), "application_clusters": [VALID_CLUSTER_DATA, VALID_CLUSTER_DATA]})
        assert len(spec.application_clusters) == 2


class TestClusterSecretUpdateSpec:
    def test_valid_payload(self):
        spec = ClusterSecretUpdateSpec(
            token="some-argocd-token",
            application_clusters=[VALID_CLUSTER_DATA],
        )
        assert spec.token == "some-argocd-token"

    def test_empty_clusters_raises(self):
        with pytest.raises(ValidationError):
            ClusterSecretUpdateSpec(token="some-argocd-token", application_clusters=[])

    def test_empty_token_raises(self):
        with pytest.raises(ValidationError):
            ClusterSecretUpdateSpec(token="", application_clusters=[VALID_CLUSTER_DATA])


class TestClusterSecretIdentifier:
    def test_valid(self):
        spec = ClusterSecretIdentifier(token="some-argocd-token", app_name="app", chosen_name="nati")
        assert spec.app_name == "app"

    def test_invalid_app_name_pattern_raises(self):
        with pytest.raises(ValidationError):
            ClusterSecretIdentifier(token="some-argocd-token", app_name="bad name!", chosen_name="nati")

    def test_invalid_chosen_name_pattern_raises(self):
        with pytest.raises(ValidationError):
            ClusterSecretIdentifier(token="some-argocd-token", app_name="app", chosen_name="bad!")

    def test_empty_app_name_raises(self):
        with pytest.raises(ValidationError):
            ClusterSecretIdentifier(token="some-argocd-token", app_name="", chosen_name="nati")
