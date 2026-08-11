import pytest
from pydantic import ValidationError

from app.v1.confluence.schemas import SpaceImportSpec


def test_valid_spec():
    # Confluence restores the space key from the archive itself — SpaceImportSpec has no
    # space_key field (see app/v1/confluence/CLAUDE.md).
    spec = SpaceImportSpec(archive_name="export.zip")
    assert spec.archive_name == "export.zip"


def test_archive_must_end_with_zip():
    with pytest.raises(ValidationError, match="zip"):
        SpaceImportSpec(archive_name="export.tar.gz")


def test_archive_not_zip_raises():
    with pytest.raises(ValidationError):
        SpaceImportSpec(archive_name="export.jar")


def test_archive_empty_raises():
    with pytest.raises(ValidationError):
        SpaceImportSpec(archive_name="")


def test_archive_too_short_raises():
    with pytest.raises(ValidationError):
        SpaceImportSpec(archive_name=".zip")


def test_archive_zip_extension_case_insensitive():
    spec = SpaceImportSpec(archive_name="Export.ZIP")
    assert spec.archive_name == "Export.ZIP"
