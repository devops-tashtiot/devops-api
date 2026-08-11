"""Error-path unit tests for argocd git-backed consumer-config operations."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.global_conf import global_config
from app.v1.argocd import operations as ops
from app.v1.argocd.schemas import (
    ConsumerConfigSpec,
    ConsumerExtraConfig,
    GLine,
    PLine,
    RbacActionEnum,
    RbacResourceEnum,
)

VALID_ENV = global_config.ARGOCD_ALLOWED_ENVS[0]
VALID_SIZE = global_config.ARGOCD_ALLOWED_SIZES[0]
VALID_RESOURCE = global_config.ARGOCD_ALLOWED_RESOURCES[0]


def _valid_spec():
    return ConsumerConfigSpec(
        name="consumer-a",
        environment=VALID_ENV,
        size=VALID_SIZE,
        include_resources=[VALID_RESOURCE],
        ad_admin_group="my-group",
    )


@pytest.mark.asyncio
async def test_create_consumer_config_reraises_on_git_error():
    git = MagicMock()
    git.add_file = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        await ops.create_consumer_config(git, _valid_spec())


@pytest.mark.asyncio
async def test_delete_consumer_config_reraises_on_git_error():
    git = MagicMock()
    git.delete_file = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        await ops.delete_consumer_config(git, VALID_ENV, "consumer-a")


@pytest.mark.asyncio
async def test_create_consumer_config_writes_rbac_and_config():
    # Populates g_lines/p_lines/extra_roles/config so the RBAC and config content-building
    # branches run, then asserts the rendered YAML was handed to git.add_file.
    spec = ConsumerConfigSpec(
        name="consumer-a",
        environment=VALID_ENV,
        size=VALID_SIZE,
        include_resources=[VALID_RESOURCE],
        ad_admin_group="my-group",
        g_lines=[GLine(ad_group="DEV_Group", role="myrole")],
        p_lines=[
            PLine(
                role="myrole",
                resource=next(iter(RbacResourceEnum)),
                action=next(iter(RbacActionEnum)),
                object="consumer-a/*",
                effect="allow",
            )
        ],
        config=ConsumerExtraConfig(
            extra_argocd_cm_args={"some.setting": "1"},
            extra_argocd_params={"other.setting": "2"},
        ),
    )
    git = MagicMock()
    git.add_file = AsyncMock()

    await ops.create_consumer_config(git, spec)

    git.add_file.assert_awaited_once()
    written_content = git.add_file.call_args.args[2]
    assert "extra_roles" in written_content
    assert "config" in written_content
