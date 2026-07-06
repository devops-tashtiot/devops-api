import asyncio
import yaml
from loguru import logger
from fastapi import HTTPException
from tashtiot_apis_library import Git, ArgoCD

from .conf import config
from .schemas import ApplicationCluster, ConsumerConfigSpec, ClusterSecretSpec, ClusterSecretUpdateSpec, ClusterSecretIdentifier
from app.global_conf import global_config


async def _check_cluster_permissions(cluster: ApplicationCluster) -> None:
    namespaces = [ns.strip() for ns in cluster.namespace.split(",") if ns.strip()]
    missing_admin: list[str] = []

    for ns in namespaces:
        proc = await asyncio.create_subprocess_exec(
            "kubectl", "auth", "can-i", "*", "*",
            "--namespace", ns,
            "--token", cluster.token,
            "--server", cluster.address,
            "--insecure-skip-tls-verify",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        stdout_text = stdout.decode().strip()
        stderr_text = stderr.decode().strip()

        if stderr_text:
            # kubectl itself errored — bad token, unreachable server, or auth rejection
            logger.error(f"Cluster '{cluster.name}' ({cluster.address}): kubectl error for namespace '{ns}': {stderr_text}")
            raise HTTPException(
                status_code=401,
                detail=f"Cluster '{cluster.name}' ({cluster.address}): token is invalid or the server is unreachable. kubectl error: {stderr_text}",
            )

        if stdout_text != "yes":
            missing_admin.append(ns)

    if missing_admin:
        missing_str = ", ".join(missing_admin)
        logger.warning(f"Cluster '{cluster.name}' ({cluster.address}): token lacks admin on: {missing_str}")
        raise HTTPException(
            status_code=403,
            detail=f"Cluster '{cluster.name}' ({cluster.address}): token is missing admin permission on namespace(s): {missing_str}",
        )


async def _build_argocd(app_name: str, timeout: int, username: str, password: str) -> ArgoCD:
    base_url = f"https://{app_name}.argocd.{global_config.DOMAIN_SUFFIX}"
    return await ArgoCD.from_credentials(base_url, timeout, username, password)


async def create_cluster_secret(argocd_timeout: int, payload: ClusterSecretSpec) -> None:
    for cluster in payload.application_clusters:
        await _check_cluster_permissions(cluster)

    argocd = await _build_argocd(payload.app_name, argocd_timeout, payload.username, payload.password)
    helm_params = [{"name": "appName", "value": payload.app_name}]
    for i, cluster in enumerate(payload.application_clusters):
        prefix = f"applicationClusters[{i}]"
        helm_params.extend([
            {"name": f"{prefix}.address", "value": cluster.address},
            {"name": f"{prefix}.namespace", "value": cluster.namespace},
            {"name": f"{prefix}.name", "value": cluster.name},
            {"name": f"{prefix}.token", "value": cluster.token},
        ])

    app_body = {
        "metadata": {
            "name": f"{payload.chosen_name}-cluster-secret",
            "namespace": config.ARGOCD_APP_NAMESPACE,
        },
        "spec": {
            "project": "default",
            "source": {
                "repoURL": global_config.ARGOCD_CLUSTER_SECRET_REPO_URL,
                "targetRevision": "HEAD",
                "path": config.ARGOCD_CLUSTER_SECRET_CHART_PATH,
                "helm": {
                    "parameters": helm_params,
                },
            },
            "destination": {
                "server": config.ARGOCD_CLUSTER_SECRET_DEST_SERVER,
                "namespace": f"{payload.app_name}-argocd",
            },
            "syncPolicy": None,
        },
    }

    argo_app_name = f"{payload.chosen_name}-cluster-secret"
    try:
        await argocd.create_app(app_body, validate=False)
        await argocd.sync(argo_app_name)
    except Exception as e:
        logger.error(f"Unexpected error creating cluster secret {argo_app_name}: {str(e)}")
        raise


async def delete_cluster_secret(argocd_timeout: int, params: ClusterSecretIdentifier) -> None:
    argocd = await _build_argocd(params.app_name, argocd_timeout, params.username, params.password)
    argo_app_name = f"{params.chosen_name}-cluster-secret"
    try:
        await argocd.delete_app(argo_app_name, config.ARGOCD_APP_NAMESPACE)
    except Exception as e:
        logger.error(f"Unexpected error deleting cluster secret {argo_app_name}: {str(e)}")
        raise


async def edit_cluster_secret(argocd_timeout: int, app_name: str, chosen_name: str, payload: ClusterSecretUpdateSpec) -> None:
    argocd = await _build_argocd(app_name, argocd_timeout, payload.username, payload.password)
    argo_app_name = f"{chosen_name}-cluster-secret"
    helm_params = [{"name": "appName", "value": app_name}]
    for i, cluster in enumerate(payload.application_clusters):
        prefix = f"applicationClusters[{i}]"
        helm_params.extend([
            {"name": f"{prefix}.address", "value": cluster.address},
            {"name": f"{prefix}.namespace", "value": cluster.namespace},
            {"name": f"{prefix}.name", "value": cluster.name},
            {"name": f"{prefix}.token", "value": cluster.token},
        ])
    try:
        await argocd.modify_parameters(helm_params, argo_app_name, config.ARGOCD_APP_NAMESPACE, "default")
        await argocd.sync(argo_app_name)
    except Exception as e:
        logger.error(f"Unexpected error editing cluster secret {argo_app_name}: {str(e)}")
        raise


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
    data: dict = {
        "name": payload.name,
        "size": payload.size.value,
        "include_resources": [r.value for r in payload.include_resources],
        "ad_admin_group": payload.ad_admin_group,
    }
    all_rbac: list[str] = []
    for line in (payload.g_lines or []):
        all_rbac.append(line.to_rbac())
    for line in (payload.p_lines or []):
        all_rbac.append(line.to_rbac())
    all_rbac.extend(payload.extra_roles or [])
    if all_rbac:
        data["extra_roles"] = all_rbac
    if payload.config:
        config_data: dict = {}
        if payload.config.extra_argocd_cm_args:
            config_data["extra_argocd_cm_args"] = dict(payload.config.extra_argocd_cm_args)
        if payload.config.extra_argocd_params:
            config_data["extra_argocd_params"] = dict(payload.config.extra_argocd_params)
        if config_data:
            data["config"] = config_data
    content = yaml.dump(data, default_flow_style=False, sort_keys=False)
    try:
        await git.add_file(path, f"Add consumer config for {payload.name}", content)
    except Exception as e:
        logger.error(f"Unexpected error creating consumer config {payload.name}: {str(e)}")
        raise
