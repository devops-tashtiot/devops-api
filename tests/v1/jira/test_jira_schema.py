import pytest
from pydantic import ValidationError

from app.v1.jira.schemas import ProjectSpec


def test_valid_with_admin_user():
    spec = ProjectSpec(
        key="MYPROJ", name="My Project", description="desc", admin_user="admin"
    )
    assert spec.admin_user == "admin"
    assert spec.admin_group is None


def test_admin_group_alone_raises():
    # Jira's project-creation API unconditionally requires a lead (a user, never a group) —
    # confirmed live (see app/v1/jira/CLAUDE.md). admin_user is therefore required, unlike
    # Bitbucket/Confluence where "at least one of admin_user/admin_group" is enough.
    with pytest.raises(ValidationError, match="admin_user"):
        ProjectSpec(
            key="MYPROJ", name="My Project", description="desc", admin_group="dev-team"
        )


def test_valid_with_both():
    spec = ProjectSpec(
        key="MYPROJ",
        name="My Project",
        description="desc",
        admin_user="admin",
        admin_group="dev-team",
    )
    assert spec.admin_user == "admin"
    assert spec.admin_group == "dev-team"


def test_neither_admin_raises():
    with pytest.raises(ValidationError, match="admin_user"):
        ProjectSpec(key="MYPROJ", name="My Project", description="desc")


def test_key_lowercase_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(
            key="myproj", name="My Project", description="desc", admin_user="admin"
        )


def test_key_too_short_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(key="A", name="My Project", description="desc", admin_user="admin")


def test_key_two_chars_valid():
    # min_length=2 matches the true regex minimum (^[A-Z][A-Z0-9]+$ needs a leading letter
    # plus at least one more char) — this pins down the boundary that succeeds.
    spec = ProjectSpec(
        key="AB", name="My Project", description="desc", admin_user="admin"
    )
    assert spec.key == "AB"


def test_key_too_long_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(
            key="TOOLONGKEY123",
            name="My Project",
            description="desc",
            admin_user="admin",
        )


def test_key_special_chars_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(
            key="MY-PROJ", name="My Project", description="desc", admin_user="admin"
        )


def test_name_empty_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(key="MYPROJ", name="", description="desc", admin_user="admin")


def test_description_empty_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(key="MYPROJ", name="My Project", description="", admin_user="admin")


def test_admin_user_invalid_chars_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(
            key="MYPROJ", name="My Project", description="desc", admin_user="Admin User"
        )


def test_admin_group_valid_with_hyphens():
    spec = ProjectSpec(
        key="MYPROJ",
        name="My Project",
        description="desc",
        admin_user="admin",
        admin_group="my-group-01",
    )
    assert spec.admin_group == "my-group-01"


def test_admin_group_with_spaces_is_valid():
    # admin_group has no pattern anymore — AD/LDAP group names commonly contain spaces
    spec = ProjectSpec(
        key="MYPROJ",
        name="My Project",
        description="desc",
        admin_user="admin",
        admin_group="Domain Users",
    )
    assert spec.admin_group == "Domain Users"


def test_admin_user_at_max_length_20_is_valid():
    spec = ProjectSpec(
        key="MYPROJ", name="My Project", description="desc", admin_user="a" * 20
    )
    assert spec.admin_user == "a" * 20


def test_admin_user_over_max_length_21_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(
            key="MYPROJ", name="My Project", description="desc", admin_user="a" * 21
        )


def test_admin_user_starting_with_digit_raises():
    # pattern is ^[a-z][a-z0-9\-]*$ — must start with a lowercase letter
    with pytest.raises(ValidationError):
        ProjectSpec(
            key="MYPROJ", name="My Project", description="desc", admin_user="1admin"
        )
