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


def test_key_lowercase_is_valid():
    # space_key pattern is ^[A-Za-z0-9]+$ — no longer requires uppercase
    spec = SpaceExportSpec(space_key="mysp")
    assert spec.space_key == "mysp"


def test_key_mixed_case_is_valid():
    spec = SpaceExportSpec(space_key="MySpace")
    assert spec.space_key == "MySpace"


def test_key_starting_with_digit_is_valid():
    # pattern no longer requires the first char to be a letter
    spec = SpaceExportSpec(space_key="1SP")
    assert spec.space_key == "1SP"


def test_key_with_special_chars_raises():
    with pytest.raises(ValidationError):
        SpaceExportSpec(space_key="MY-SP")


def test_key_too_long_raises():
    with pytest.raises(ValidationError):
        SpaceExportSpec(space_key="A" * 256)


def test_key_max_length_255_valid():
    spec = SpaceExportSpec(space_key="A" * 255)
    assert len(spec.space_key) == 255
