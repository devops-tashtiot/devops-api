import pytest
from pydantic import ValidationError

from app.v1.jira.schemas import ProjectSpec


def test_valid_with_admin_user():
    spec = ProjectSpec(key="MYPROJ", name="My Project", description="desc", admin_user="admin")
    assert spec.admin_user == "admin"
    assert spec.admin_group is None


def test_admin_group_alone_raises():
    # Jira's project-creation API unconditionally requires a lead (a user, never a group) —
    # confirmed live (see app/v1/jira/CLAUDE.md). admin_user is therefore required, unlike
    # Bitbucket/Confluence where "at least one of admin_user/admin_group" is enough.
    with pytest.raises(ValidationError, match="admin_user"):
        ProjectSpec(key="MYPROJ", name="My Project", description="desc", admin_group="dev-team")


def test_valid_with_both():
    spec = ProjectSpec(key="MYPROJ", name="My Project", description="desc", admin_user="admin", admin_group="dev-team")
    assert spec.admin_user == "admin"
    assert spec.admin_group == "dev-team"


def test_neither_admin_raises():
    with pytest.raises(ValidationError, match="admin_user"):
        ProjectSpec(key="MYPROJ", name="My Project", description="desc")


def test_key_lowercase_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(key="myproj", name="My Project", description="desc", admin_user="admin")


def test_key_too_short_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(key="A", name="My Project", description="desc", admin_user="admin")


def test_key_two_chars_valid():
    # The true regex minimum (^[A-Z][A-Z0-9]+$ needs a leading letter plus at least one more
    # char) — min_length=1 alone would suggest a single char is enough, but it isn't; this
    # pins down the actual boundary that succeeds.
    spec = ProjectSpec(key="AB", name="My Project", description="desc", admin_user="admin")
    assert spec.key == "AB"


def test_key_too_long_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(key="TOOLONGKEY123", name="My Project", description="desc", admin_user="admin")


def test_key_special_chars_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(key="MY-PROJ", name="My Project", description="desc", admin_user="admin")


def test_name_empty_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(key="MYPROJ", name="", description="desc", admin_user="admin")


def test_description_empty_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(key="MYPROJ", name="My Project", description="", admin_user="admin")


def test_admin_user_invalid_chars_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(key="MYPROJ", name="My Project", description="desc", admin_user="Admin User")


def test_admin_group_valid_with_hyphens():
    spec = ProjectSpec(key="MYPROJ", name="My Project", description="desc", admin_user="admin", admin_group="my-group-01")
    assert spec.admin_group == "my-group-01"
