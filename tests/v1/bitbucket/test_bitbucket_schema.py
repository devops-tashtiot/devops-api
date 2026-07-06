import pytest
from pydantic import ValidationError

from app.v1.bitbucket.schemas import ProjectSpec


VALID = {
    "key": "MYPROJ",
    "name": "my-project",
    "description": "A valid project",
    "public": False,
    "admin_user": "nati",
}


def test_valid_payload_with_admin_user():
    spec = ProjectSpec(**VALID)
    assert spec.key == "MYPROJ"
    assert spec.admin_user == "nati"
    assert spec.admin_group is None


def test_valid_payload_with_admin_group():
    data = {**VALID, "admin_user": None, "admin_group": "devops-team"}
    spec = ProjectSpec(**data)
    assert spec.admin_group == "devops-team"
    assert spec.admin_user is None


def test_missing_admin_raises():
    data = {**VALID, "admin_user": None}
    with pytest.raises(ValidationError, match="admin_user or admin_group"):
        ProjectSpec(**data)


def test_missing_key_raises():
    data = {**VALID}
    del data["key"]
    with pytest.raises(ValidationError):
        ProjectSpec(**data)


def test_missing_name_raises():
    data = {**VALID}
    del data["name"]
    with pytest.raises(ValidationError):
        ProjectSpec(**data)


def test_missing_description_raises():
    data = {**VALID}
    del data["description"]
    with pytest.raises(ValidationError):
        ProjectSpec(**data)


def test_key_with_special_chars_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(**{**VALID, "key": "MY PROJ!"})


def test_name_with_spaces_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(**{**VALID, "name": "my project"})


def test_empty_key_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(**{**VALID, "key": ""})


def test_empty_description_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(**{**VALID, "description": ""})


def test_public_defaults_to_false():
    data = {k: v for k, v in VALID.items() if k != "public"}
    spec = ProjectSpec(**data)
    assert spec.public is False
