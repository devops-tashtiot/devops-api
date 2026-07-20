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


def test_admin_user_at_max_length_15_is_valid():
    spec = ProjectSpec(**{**VALID, "admin_user": "a" * 15})
    assert spec.admin_user == "a" * 15


def test_admin_user_over_max_length_16_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(**{**VALID, "admin_user": "a" * 16})


def test_admin_user_with_uppercase_raises():
    # pattern is ^[a-z0-9]+$ — lowercase only
    with pytest.raises(ValidationError):
        ProjectSpec(**{**VALID, "admin_user": "Admin"})


def test_key_at_max_length_255_is_valid():
    spec = ProjectSpec(**{**VALID, "key": "A" * 255})
    assert spec.key == "A" * 255


def test_key_over_max_length_256_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(**{**VALID, "key": "A" * 256})


def test_description_at_max_length_1000_is_valid():
    spec = ProjectSpec(**{**VALID, "description": "d" * 1000})
    assert spec.description == "d" * 1000


def test_description_over_max_length_1001_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(**{**VALID, "description": "d" * 1001})


def test_unknown_field_is_ignored_not_rejected():
    # pydantic's default extra policy ("ignore") — pin this so a future model_config change
    # (e.g. extra="forbid") is a deliberate decision, not an accidental behavior shift.
    spec = ProjectSpec(**{**VALID, "unexpected_field": "surprise"})
    assert not hasattr(spec, "unexpected_field")
