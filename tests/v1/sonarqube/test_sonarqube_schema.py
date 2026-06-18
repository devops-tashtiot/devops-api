import pytest
from pydantic import ValidationError

from app.v1.sonarqube.schemas import GroupSpec


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


# ── consumer_name validation ──────────────────────────────────────────────────

def test_consumer_name_with_special_chars_raises():
    with pytest.raises(ValidationError):
        GroupSpec(consumer_name="invalid@consumer", name="check")


def test_consumer_name_too_long_raises():
    with pytest.raises(ValidationError):
        GroupSpec(consumer_name="a" * 256, name="check")

