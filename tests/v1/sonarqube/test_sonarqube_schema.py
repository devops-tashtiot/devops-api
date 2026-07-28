import pytest
from pydantic import ValidationError

from app.v1.sonarqube.schemas import GroupSpec, SonarQubeConsumerSpec, SonarQubeConsumerUpdateSpec


def test_valid_group_name():
    spec = GroupSpec(consumer_name="test-consumer", name="check")
    assert spec.name == "check"


def test_valid_group_name_with_consumer_name():
    spec = GroupSpec(consumer_name="test-consumer", name="my-group_1")
    assert spec.name == "my-group_1"
    assert spec.consumer_name == "test-consumer"


def test_empty_name_raises():
    with pytest.raises(ValidationError):
        GroupSpec(consumer_name="test-consumer", name="")


def test_name_with_spaces_raises():
    with pytest.raises(ValidationError):
        GroupSpec(consumer_name="test-consumer", name="invalid name")


def test_name_with_special_chars_raises():
    with pytest.raises(ValidationError):
        GroupSpec(consumer_name="test-consumer", name="group@domain")


def test_name_too_long_raises():
    with pytest.raises(ValidationError):
        GroupSpec(consumer_name="test-consumer", name="a" * 256)


def test_name_at_max_length_valid():
    spec = GroupSpec(consumer_name="test-consumer", name="a" * 255)
    assert len(spec.name) == 255


# ── consumer_name validation ──────────────────────────────────────────────────

def test_consumer_name_with_special_chars_raises():
    with pytest.raises(ValidationError):
        GroupSpec(consumer_name="invalid@consumer", name="check")


def test_consumer_name_too_long_raises():
    with pytest.raises(ValidationError):
        GroupSpec(consumer_name="a" * 256, name="check")


def test_consumer_name_at_max_length_valid():
    spec = GroupSpec(consumer_name="a" * 255, name="check")
    assert len(spec.consumer_name) == 255


# ── SonarQubeConsumerSpec ──────────────────────────────────────────────────────

class TestSonarQubeConsumerSpec:
    def test_valid_minimal_payload(self):
        spec = SonarQubeConsumerSpec(name="my-consumer")
        assert spec.name == "my-consumer"
        assert spec.plugins_list is None
        assert spec.size == "default"

    def test_valid_with_plugins_and_size(self):
        spec = SonarQubeConsumerSpec(
            name="my-consumer",
            plugins_list=["https://s3/plugin-a.jar", "https://s3/plugin-b.jar"],
            size="medium",
        )
        assert spec.plugins_list == ["https://s3/plugin-a.jar", "https://s3/plugin-b.jar"]

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError):
            SonarQubeConsumerSpec(name="")

    def test_name_with_special_chars_raises(self):
        with pytest.raises(ValidationError):
            SonarQubeConsumerSpec(name="bad name!")

    def test_invalid_size_raises(self):
        with pytest.raises(ValidationError):
            SonarQubeConsumerSpec(name="my-consumer", size="supersize")

    def test_plugin_entry_with_comma_raises(self):
        with pytest.raises(ValidationError):
            SonarQubeConsumerSpec(name="my-consumer", plugins_list=["https://s3/a.jar,https://s3/b.jar"])

    def test_plugin_entry_with_quote_raises(self):
        with pytest.raises(ValidationError):
            SonarQubeConsumerSpec(name="my-consumer", plugins_list=['https://s3/plugin"a.jar'])

    def test_empty_plugins_list_valid(self):
        spec = SonarQubeConsumerSpec(name="my-consumer", plugins_list=[])
        assert spec.plugins_list == []


# ── SonarQubeConsumerUpdateSpec ────────────────────────────────────────────────

class TestSonarQubeConsumerUpdateSpec:
    def test_valid_minimal_payload(self):
        spec = SonarQubeConsumerUpdateSpec()
        assert spec.plugins_list is None
        assert spec.size == "default"

    def test_valid_with_plugins_and_size(self):
        spec = SonarQubeConsumerUpdateSpec(plugins_list=["https://s3/plugin-c.jar"], size="big")
        assert spec.plugins_list == ["https://s3/plugin-c.jar"]
        assert spec.size == "big"

    def test_invalid_size_raises(self):
        with pytest.raises(ValidationError):
            SonarQubeConsumerUpdateSpec(size="supersize")

    def test_plugin_entry_with_comma_raises(self):
        with pytest.raises(ValidationError):
            SonarQubeConsumerUpdateSpec(plugins_list=["https://s3/a.jar,https://s3/b.jar"])

    def test_plugin_entry_with_quote_raises(self):
        with pytest.raises(ValidationError):
            SonarQubeConsumerUpdateSpec(plugins_list=['https://s3/plugin"c.jar'])

