import yaml
from loguru import logger
from tashtiot_apis_library import Git

from .schemas import ConsumerConfigSpec


async def delete_consumer_config(git: Git, env: str, name: str) -> None:
    path = f"{env}/consumers/{name}/config.yaml"
    try:
        await git.delete_file(path, f"Delete consumer config for {name}")
    except Exception as e:
        logger.error(f"Unexpected error deleting consumer config {name}: {str(e)}")
        raise


async def create_consumer_config(git: Git, payload: ConsumerConfigSpec) -> None:
    env = payload.environment.value
    path = f"{env}/consumers/{payload.name}/config.yaml"
    content = yaml.dump(
        {
            "name": payload.name,
            "size": payload.size.value,
            "include_resources": [r.value for r in payload.include_resources],
            "ad_admin_group": payload.ad_admin_group,
        },
        default_flow_style=False,
        sort_keys=False,
    )
    try:
        await git.add_file(path, f"Add consumer config for {payload.name}", content)
    except Exception as e:
        logger.error(f"Unexpected error creating consumer config {payload.name}: {str(e)}")
        raise
