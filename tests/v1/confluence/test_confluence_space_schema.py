import pytest
from pydantic import ValidationError

from app.v1.confluence.schemas import SpaceSpec


def test_valid_with_admin_user():
    spec = SpaceSpec(
        key="MYSP", name="My Space", description="desc", admin_user="admin"
    )
    assert spec.admin_user == "admin"
    assert spec.admin_group is None


def test_valid_with_admin_group():
    spec = SpaceSpec(
        key="MYSP", name="My Space", description="desc", admin_group="dev-team"
    )
    assert spec.admin_group == "dev-team"
    assert spec.admin_user is None


def test_valid_with_both():
    spec = SpaceSpec(
        key="MYSP",
        name="My Space",
        description="desc",
        admin_user="admin",
        admin_group="dev-team",
    )
    assert spec.admin_user == "admin"
    assert spec.admin_group == "dev-team"


def test_neither_admin_raises():
    with pytest.raises(ValidationError, match="at least one"):
        SpaceSpec(key="MYSP", name="My Space", description="desc")


def test_key_lowercase_is_valid():
    # key pattern is ^[A-Za-z0-9]+$ — no longer requires uppercase
    spec = SpaceSpec(
        key="mysp", name="My Space", description="desc", admin_user="admin"
    )
    assert spec.key == "mysp"


def test_key_mixed_case_is_valid():
    spec = SpaceSpec(
        key="MySpace", name="My Space", description="desc", admin_user="admin"
    )
    assert spec.key == "MySpace"


def test_key_with_special_chars_raises():
    with pytest.raises(ValidationError):
        SpaceSpec(key="MY-SP", name="My Space", description="desc", admin_user="admin")


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
        SpaceSpec(
            key="MYSP", name="My Space", description="desc", admin_user="Admin User"
        )


def test_admin_group_valid_with_hyphens():
    spec = SpaceSpec(
        key="MYSP", name="My Space", description="desc", admin_group="my-group-01"
    )
    assert spec.admin_group == "my-group-01"


def test_admin_group_with_spaces_is_valid():
    # admin_group has no pattern anymore — AD/LDAP group names commonly contain spaces
    spec = SpaceSpec(
        key="MYSP", name="My Space", description="desc", admin_group="Domain Users"
    )
    assert spec.admin_group == "Domain Users"


def test_admin_user_at_max_length_20_is_valid():
    spec = SpaceSpec(
        key="MYSP", name="My Space", description="desc", admin_user="a" * 20
    )
    assert spec.admin_user == "a" * 20


def test_admin_user_over_max_length_21_raises():
    with pytest.raises(ValidationError):
        SpaceSpec(key="MYSP", name="My Space", description="desc", admin_user="a" * 21)


def test_admin_user_starting_with_digit_raises():
    # pattern is ^[a-z][a-z0-9\-]*$ — must start with a lowercase letter
    with pytest.raises(ValidationError):
        SpaceSpec(key="MYSP", name="My Space", description="desc", admin_user="1admin")
