import pytest
from pydantic import ValidationError

from app.v1.confluence.schemas import PluginInstallSpec


def test_valid_spec():
    spec = PluginInstallSpec(plugin_name="my-plugin-1.0.jar")
    assert spec.plugin_name == "my-plugin-1.0.jar"


def test_valid_name_with_dots_and_hyphens():
    spec = PluginInstallSpec(plugin_name="com.example.plugin-2.3.1.jar")
    assert spec.plugin_name == "com.example.plugin-2.3.1.jar"


def test_empty_name_raises():
    with pytest.raises(ValidationError):
        PluginInstallSpec(plugin_name="")


def test_name_too_short_raises():
    with pytest.raises(ValidationError):
        PluginInstallSpec(plugin_name=".jar")


def test_name_too_long_raises():
    with pytest.raises(ValidationError):
        PluginInstallSpec(plugin_name="a" * 252 + ".jar")


def test_not_jar_extension_raises():
    with pytest.raises(ValidationError):
        PluginInstallSpec(plugin_name="plugin.zip")


def test_txt_extension_raises():
    with pytest.raises(ValidationError):
        PluginInstallSpec(plugin_name="readme.txt")


def test_no_extension_raises():
    with pytest.raises(ValidationError):
        PluginInstallSpec(plugin_name="myplugin")


def test_jar_extension_case_insensitive():
    spec = PluginInstallSpec(plugin_name="Plugin.JAR")
    assert spec.plugin_name == "Plugin.JAR"


def test_name_starting_with_hyphen_raises():
    with pytest.raises(ValidationError):
        PluginInstallSpec(plugin_name="-bad-name.jar")


def test_name_with_spaces_raises():
    with pytest.raises(ValidationError):
        PluginInstallSpec(plugin_name="my plugin.jar")


def test_name_with_slash_raises():
    with pytest.raises(ValidationError):
        PluginInstallSpec(plugin_name="path/to/plugin.jar")
