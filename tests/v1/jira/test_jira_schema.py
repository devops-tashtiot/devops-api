import pytest
from pydantic import ValidationError

from app.v1.jira.schemas import ProjectSpec


def test_valid_with_admin_user():
    spec = ProjectSpec(key="MYPROJ", name="My Project", description="desc", admin_user="admin")
    assert spec.admin_user == "admin"
    assert spec.admin_group is None


def test_valid_with_admin_group():
    spec = ProjectSpec(key="MYPROJ", name="My Project", description="desc", admin_group="dev-team")
    assert spec.admin_group == "dev-team"
    assert spec.admin_user is None


def test_valid_with_both():
    spec = ProjectSpec(key="MYPROJ", name="My Project", description="desc", admin_user="admin", admin_group="dev-team")
    assert spec.admin_user == "admin"
    assert spec.admin_group == "dev-team"


def test_neither_admin_raises():
    with pytest.raises(ValidationError, match="at least one"):
        ProjectSpec(key="MYPROJ", name="My Project", description="desc")


def test_key_lowercase_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(key="myproj", name="My Project", description="desc", admin_user="admin")


def test_key_too_short_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(key="A", name="My Project", description="desc", admin_user="admin")


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
    spec = ProjectSpec(key="MYPROJ", name="My Project", description="desc", admin_group="my-group-01")
    assert spec.admin_group == "my-group-01"
