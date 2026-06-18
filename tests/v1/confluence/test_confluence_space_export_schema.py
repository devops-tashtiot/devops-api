import pytest
from pydantic import ValidationError

from app.v1.confluence.schemas import SpaceExportSpec


def test_valid_space_key():
    spec = SpaceExportSpec(space_key="MYSP")
    assert spec.space_key == "MYSP"


def test_valid_key_with_digits():
    spec = SpaceExportSpec(space_key="SP123")
    assert spec.space_key == "SP123"


def test_key_empty_raises():
    with pytest.raises(ValidationError):
        SpaceExportSpec(space_key="")


def test_key_lowercase_raises():
    with pytest.raises(ValidationError):
        SpaceExportSpec(space_key="mysp")


def test_key_mixed_case_raises():
    with pytest.raises(ValidationError):
        SpaceExportSpec(space_key="MySpace")


def test_key_starts_with_digit_raises():
    with pytest.raises(ValidationError):
        SpaceExportSpec(space_key="1SP")


def test_key_too_long_raises():
    with pytest.raises(ValidationError):
        SpaceExportSpec(space_key="A" * 51)


def test_key_max_length_valid():
    spec = SpaceExportSpec(space_key="A" * 50)
    assert len(spec.space_key) == 50
