import pytest
from pydantic import ValidationError

from app.v1.sonarqube.schemas import GroupSpec


def test_valid_group_name():
    spec = GroupSpec(name="check")
    assert spec.name == "check"


def test_valid_group_name_with_hyphens_and_underscores():
    spec = GroupSpec(name="my-group_1")
    assert spec.name == "my-group_1"


def test_empty_name_raises():
    with pytest.raises(ValidationError):
        GroupSpec(name="")


def test_name_with_spaces_raises():
    with pytest.raises(ValidationError):
        GroupSpec(name="invalid name")


def test_name_with_special_chars_raises():
    with pytest.raises(ValidationError):
        GroupSpec(name="group@domain")


def test_name_too_long_raises():
    with pytest.raises(ValidationError):
        GroupSpec(name="a" * 256)
