from unittest.mock import MagicMock

import app.main as main

_ENABLE_FLAGS = [
    "ARTIFACTORY_ENABLE_API",
    "BITBUCKET_ENABLE_API",
    "CONFLUENCE_ENABLE_API",
    "SONARQUBE_ENABLE_API",
    "JIRA_ENABLE_API",
    "ARGOCD_ENABLE_API",
]

_ROUTER_FACTORIES = [
    "get_v1_artifactory_router",
    "get_v1_bitbucket_router",
    "get_v1_confluence_router",
    "get_v1_sonarqube_router",
    "get_v1_jira_router",
    "get_v1_argocd_router",
]


def _patch_construction(monkeypatch):
    """Stub out client/router construction so create_app() runs every branch without
    building real httpx/Git clients or touching the network."""
    fake_app = MagicMock()
    monkeypatch.setattr(main, "general_create_app", lambda **kwargs: fake_app)
    monkeypatch.setattr(main, "BaseAPI", MagicMock())
    monkeypatch.setattr(main, "Git", MagicMock())
    for factory in _ROUTER_FACTORIES:
        monkeypatch.setattr(main, factory, MagicMock(return_value=MagicMock()))
    return fake_app


def test_create_app_wires_all_routers_when_all_enabled(monkeypatch):
    for flag in _ENABLE_FLAGS:
        monkeypatch.setattr(main.global_config, flag, True)
    fake_app = _patch_construction(monkeypatch)

    app = main.create_app()

    assert app is fake_app
    # one include_router per enabled service
    assert fake_app.include_router.call_count == len(_ROUTER_FACTORIES)


def test_create_app_skips_disabled_services(monkeypatch):
    for flag in _ENABLE_FLAGS:
        monkeypatch.setattr(main.global_config, flag, False)
    fake_app = _patch_construction(monkeypatch)

    app = main.create_app()

    assert app is fake_app
    fake_app.include_router.assert_not_called()
