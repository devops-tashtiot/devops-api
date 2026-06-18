import pytest
from pydantic import ValidationError

from app.v1.confluence.schemas import SpaceImportSpec


def test_valid_spec():
    spec = SpaceImportSpec(space_key="MYSP", archive_name="export.zip")
    assert spec.space_key == "MYSP"
    assert spec.archive_name == "export.zip"


def test_space_key_must_start_uppercase():
    with pytest.raises(ValidationError):
        SpaceImportSpec(space_key="mysp", archive_name="export.zip")


def test_space_key_lowercase_digit_raises():
    with pytest.raises(ValidationError):
        SpaceImportSpec(space_key="1SP", archive_name="export.zip")


def test_space_key_empty_raises():
    with pytest.raises(ValidationError):
        SpaceImportSpec(space_key="", archive_name="export.zip")


def test_archive_must_end_with_zip():
    with pytest.raises(ValidationError, match="zip"):
        SpaceImportSpec(space_key="MYSP", archive_name="export.tar.gz")


def test_archive_not_zip_raises():
    with pytest.raises(ValidationError):
        SpaceImportSpec(space_key="MYSP", archive_name="export.jar")


def test_archive_empty_raises():
    with pytest.raises(ValidationError):
        SpaceImportSpec(space_key="MYSP", archive_name="")


def test_archive_too_short_raises():
    with pytest.raises(ValidationError):
        SpaceImportSpec(space_key="MYSP", archive_name=".zip")


def test_archive_zip_extension_case_insensitive():
    spec = SpaceImportSpec(space_key="MYSP", archive_name="Export.ZIP")
    assert spec.archive_name == "Export.ZIP"


def test_space_key_with_digits_valid():
    spec = SpaceImportSpec(space_key="SP123", archive_name="export.zip")
    assert spec.space_key == "SP123"
