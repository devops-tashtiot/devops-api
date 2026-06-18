import pytest
from pydantic import ValidationError

from app.v1.confluence.schemas import SpaceSpec


def test_valid_with_admin_user():
    spec = SpaceSpec(key="MYSP", name="My Space", description="desc", admin_user="admin")
    assert spec.admin_user == "admin"
    assert spec.admin_group is None


def test_valid_with_admin_group():
    spec = SpaceSpec(key="MYSP", name="My Space", description="desc", admin_group="dev-team")
    assert spec.admin_group == "dev-team"
    assert spec.admin_user is None


def test_valid_with_both():
    spec = SpaceSpec(key="MYSP", name="My Space", description="desc", admin_user="admin", admin_group="dev-team")
    assert spec.admin_user == "admin"
    assert spec.admin_group == "dev-team"


def test_neither_admin_raises():
    with pytest.raises(ValidationError, match="at least one"):
        SpaceSpec(key="MYSP", name="My Space", description="desc")


def test_key_must_be_uppercase():
    with pytest.raises(ValidationError):
        SpaceSpec(key="mysp", name="My Space", description="desc", admin_user="admin")


def test_key_lowercase_mixed_raises():
    with pytest.raises(ValidationError):
        SpaceSpec(key="MySpace", name="My Space", description="desc", admin_user="admin")


def test_key_empty_raises():
    with pytest.raises(ValidationError):
        SpaceSpec(key="", name="My Space", description="desc", admin_user="admin")


def test_name_empty_raises():
    with pytest.raises(ValidationError):
        SpaceSpec(key="MYSP", name="", description="desc", admin_user="admin")


def test_description_empty_raises():
    with pytest.raises(ValidationError):
        SpaceSpec(key="MYSP", name="My Space", description="", admin_user="admin")


def test_admin_user_invalid_chars_raises():
    with pytest.raises(ValidationError):
        SpaceSpec(key="MYSP", name="My Space", description="desc", admin_user="Admin User")


def test_admin_group_valid_with_hyphens():
    spec = SpaceSpec(key="MYSP", name="My Space", description="desc", admin_group="my-group-01")
    assert spec.admin_group == "my-group-01"
