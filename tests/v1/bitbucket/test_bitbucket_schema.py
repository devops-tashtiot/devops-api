import pytest
from pydantic import ValidationError

from app.v1.bitbucket.schemas import MirrorProjectSpec, ProjectSpec

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


def test_name_with_spaces_is_valid():
    # name pattern allows whitespace (project display names are free text in Bitbucket's UI)
    spec = ProjectSpec(**{**VALID, "name": "my project"})
    assert spec.name == "my project"


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


def test_admin_user_at_max_length_20_is_valid():
    spec = ProjectSpec(**{**VALID, "admin_user": "a" * 20})
    assert spec.admin_user == "a" * 20


def test_admin_user_over_max_length_21_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(**{**VALID, "admin_user": "a" * 21})


def test_admin_user_with_uppercase_raises():
    # pattern is ^[a-z][a-z0-9\-]*$ — must start with a lowercase letter
    with pytest.raises(ValidationError):
        ProjectSpec(**{**VALID, "admin_user": "Admin"})


def test_admin_user_starting_with_digit_raises():
    # pattern requires the first character to be a lowercase letter
    with pytest.raises(ValidationError):
        ProjectSpec(**{**VALID, "admin_user": "1admin"})


def test_admin_user_with_hyphen_is_valid():
    # unlike the old ^[a-z0-9]+$ pattern, hyphens are now allowed after the first char —
    # needed for service-account-style usernames like "svc-devops-tashtiot"
    spec = ProjectSpec(**{**VALID, "admin_user": "svc-devops"})
    assert spec.admin_user == "svc-devops"


def test_key_at_min_length_2_is_valid():
    spec = ProjectSpec(**{**VALID, "key": "AB"})
    assert spec.key == "AB"


def test_key_below_min_length_1_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(**{**VALID, "key": "A"})


def test_key_at_max_length_10_is_valid():
    spec = ProjectSpec(**{**VALID, "key": "A" * 10})
    assert spec.key == "A" * 10


def test_key_over_max_length_11_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(**{**VALID, "key": "A" * 11})


def test_key_with_lowercase_raises():
    # pattern is ^[A-Z][A-Z0-9_]*$ — uppercase only
    with pytest.raises(ValidationError):
        ProjectSpec(**{**VALID, "key": "myproj"})


def test_key_starting_with_digit_raises():
    # pattern requires the first character to be an uppercase letter
    with pytest.raises(ValidationError):
        ProjectSpec(**{**VALID, "key": "1PROJ"})


def test_admin_group_with_spaces_is_valid():
    # admin_group has no pattern anymore — AD/LDAP group names commonly contain spaces
    spec = ProjectSpec(**{**VALID, "admin_user": None, "admin_group": "Domain Users"})
    assert spec.admin_group == "Domain Users"


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


# --- MirrorProjectSpec (POST /mirror) ---


def test_mirror_spec_with_nati_is_valid():
    spec = MirrorProjectSpec(**{**VALID, "mirrored_env_destination": "Nati"})
    assert spec.mirrored_env_destination == "Nati"


def test_mirror_spec_with_kat_is_valid():
    spec = MirrorProjectSpec(**{**VALID, "mirrored_env_destination": "Kat"})
    assert spec.mirrored_env_destination == "Kat"


def test_mirror_spec_without_mirrored_env_destination_raises():
    with pytest.raises(ValidationError):
        MirrorProjectSpec(**VALID)


def test_mirror_spec_invalid_choice_raises():
    with pytest.raises(ValidationError):
        MirrorProjectSpec(**{**VALID, "mirrored_env_destination": "SomeoneElse"})


def test_mirror_spec_still_requires_at_least_one_admin():
    data = {**VALID, "admin_user": None, "mirrored_env_destination": "Nati"}
    with pytest.raises(ValidationError, match="admin_user or admin_group"):
        MirrorProjectSpec(**data)
