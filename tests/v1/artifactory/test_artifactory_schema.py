import pytest
from pydantic import ValidationError

from app.v1.artifactory.schemas import ProjectSpec, StorageQuotaBytes, ProjectPermissionSpec, MemberType


# ── ProjectSpec ───────────────────────────────────────────────────────────────

def test_project_spec_valid_with_admin_user():
    spec = ProjectSpec(name="my project", storage_quota_giga_bytes=2, admin_user="alice")
    assert spec.name == "my project"
    assert spec.admin_user == "alice"


def test_project_spec_valid_with_admin_group():
    spec = ProjectSpec(name="my-project", storage_quota_giga_bytes=1, admin_group="devops-team")
    assert spec.admin_group == "devops-team"


def test_project_spec_valid_with_both_admin_user_and_group():
    spec = ProjectSpec(name="my-project", storage_quota_giga_bytes=1, admin_user="alice", admin_group="devops-team")
    assert spec.admin_user == "alice"
    assert spec.admin_group == "devops-team"


def test_project_spec_no_admin_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(name="my-project", storage_quota_giga_bytes=1)


def test_project_spec_name_too_short_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(name="x", storage_quota_giga_bytes=1, admin_user="alice")


def test_project_spec_name_too_long_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(name="a" * 33, storage_quota_giga_bytes=1, admin_user="alice")


def test_project_spec_quota_zero_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(name="my-project", storage_quota_giga_bytes=0, admin_user="alice")


def test_project_spec_quota_too_high_raises():
    with pytest.raises(ValidationError):
        ProjectSpec(name="my-project", storage_quota_giga_bytes=11, admin_user="alice")


def test_project_key_derived_from_name():
    spec = ProjectSpec(name="My Project", storage_quota_giga_bytes=1, admin_user="alice")
    assert spec.project_key == "my-project"


def test_project_key_underscores_replaced():
    spec = ProjectSpec(name="my_project", storage_quota_giga_bytes=1, admin_user="alice")
    assert spec.project_key == "my-project"


# ── StorageQuotaBytes ─────────────────────────────────────────────────────────

def test_storage_quota_valid():
    spec = StorageQuotaBytes(name="my-project", storage_quota_giga_bytes=5)
    assert spec.storage_quota_giga_bytes == 5


def test_storage_quota_zero_raises():
    with pytest.raises(ValidationError):
        StorageQuotaBytes(name="my-project", storage_quota_giga_bytes=0)


def test_storage_quota_too_high_raises():
    with pytest.raises(ValidationError):
        StorageQuotaBytes(name="my-project", storage_quota_giga_bytes=11)


# ── ProjectPermissionSpec ─────────────────────────────────────────────────────

def test_permission_spec_valid_user():
    spec = ProjectPermissionSpec(
        project_key="my-project",
        member_name="alice",
        member_type=MemberType.USER,
        roles=["Developer"],
    )
    assert spec.member_type == MemberType.USER
    assert "Developer" in spec.roles


def test_permission_spec_valid_group():
    spec = ProjectPermissionSpec(
        project_key="my-project",
        member_name="ad-group-devops",
        member_type=MemberType.GROUP,
        roles=["Project Admin"],
    )
    assert spec.member_type == MemberType.GROUP


def test_permission_spec_multiple_roles():
    spec = ProjectPermissionSpec(
        project_key="my-project",
        member_name="alice",
        member_type=MemberType.USER,
        roles=["Developer", "Viewer"],
    )
    assert len(spec.roles) == 2


def test_permission_spec_empty_roles_raises():
    with pytest.raises(ValidationError):
        ProjectPermissionSpec(
            project_key="my-project",
            member_name="alice",
            member_type=MemberType.USER,
            roles=[],
        )


def test_permission_spec_invalid_project_key_uppercase_raises():
    with pytest.raises(ValidationError):
        ProjectPermissionSpec(
            project_key="My-Project",
            member_name="alice",
            member_type=MemberType.USER,
            roles=["Developer"],
        )


def test_permission_spec_invalid_member_type_raises():
    with pytest.raises(ValidationError):
        ProjectPermissionSpec(
            project_key="my-project",
            member_name="alice",
            member_type="admin",
            roles=["Developer"],
        )
