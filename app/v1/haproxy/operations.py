import asyncio
from typing import Any, Dict
from loguru import logger
from fastapi import HTTPException
from ...helpers import parse_payload, filter_secret_payload, build_app_name, break_app_name, yaml_data_equals
from tashtiot_apis_library import Git, ArgoCD, Vault
from tashtiot_apis_library.connectors import ArgoOperationResponse, ExternalServiceError
from .schemas import HaProxyPayload, HaProxyMeta, HaProxyIdentifier
import yaml

async def _restore_git(git: Any, path: str, app: str, content: str, commit_message: str) -> None:
    try:
        await git.modify_file(path, commit_message, content)
    except Exception as cleanup_error:
        logger.exception(
            "Failed rolling back yaml for haproxy {} at {}: {}",
            app,
            path,
            cleanup_error,
        )


async def _restore_secrets_to_previous(
    vault: Any,
    app: str,
    secret_path: str,
    secrets: Dict[str, Any],
    secret_existed: bool,
    secrets_written: bool,
    previous_secret_data: Dict[str, Any],
) -> None:
    if not secrets:
        return
    try:
        if secret_existed:
            await vault.write_secret(secret_path, previous_secret_data)
        elif secrets_written:
            await vault.delete_secret(secret_path)
    except Exception as cleanup_error:
        logger.exception(
            "Failed rolling back secrets for haproxy {} at {}: {}",
            app,
            secret_path,
            cleanup_error,
        )


def _get_parameters(payload):
    # Parsing the request payload
    path, yaml_data, cluster, namespace, name, secrets_raw = parse_payload(payload)
    
    # Filter secrets only for secrets with values
    secrets = filter_secret_payload(secrets_raw)

    # Build desired app name 
    app_name = build_app_name(cluster, namespace, name, "haproxy")

    return path, yaml_data, cluster, namespace, name, secrets_raw, secrets, app_name

async def create_haproxy_operation(git: Git, vault: Vault, argocd: ArgoCD, payload: HaProxyPayload) -> str:
    
    # parsing variable parameters before using it
    path, yaml_data, cluster, namespace, name, secrets_raw, secrets, app_name = _get_parameters(payload)

    # Create values file in Git 
    await git.add_file(path, f"Create haproxy in cluster={cluster} on namespace={namespace} for app={name}", yaml_data)

    # Create secrets
    secret_path = f"/perimeter/haproxy/{cluster}/{namespace}/{name}"

    # Variable to store thestatus of writing the secrets, for rollback purposes
    secrets_written = False

    # Statement to check if inpt includes secrets at all
    if secrets:

        # Try writing the secret to vault in the desired path
        try:
            await vault.write_secret(secret_path, secrets)
            secrets_written = True
            
        # Delete the git file in case the secrets writing has failed
        except Exception as secret_error:
            logger.exception("Failed writing secrets for haproxy {} at {}: {}", app_name, secret_path, secret_error)
            try:
                # Rolling back the values file creating in case if secrets writing failed
                await git.delete_file(path,commit_message=(f"Rollback haproxy create for {name} in {cluster}/{namespace}"))
                
            # Local log if rollback has failed
            except Exception as cleanup_error:
                logger.exception("Failed rolling back git file {} for haproxy {}: {}", path, app_name, cleanup_error)
            raise

    # Continue business logic (ArgoCD application creation) in the background
    async def _background_create() -> None:
        stage = "namespace"
        try:
            
            # Ensure namespace exists in the cluster-secret app
            await argocd.add_namespace_to_cluster_secret(f"perimeter-openshift-{cluster}-cluster-secret", namespace, "perimeter-argocd")

            # Sync ArgoCD new app
            stage = "argo"
            logger.info("Background sync for haproxy {} at {}/{}", name, cluster, namespace)
            await argocd.wait_for_app_creation(app_name)
            await argocd.sync(app_name)
            
        # Rollback if background task has failed    
        except Exception as e:
            logger.exception("Background create flow failed for app {} at stage {}: {}", app_name, stage,e)
            
            # Rollback secrets operations in case ArgoCD failed
            if secrets_written:
                try:
                    await vault.delete_secret(secret_path)
                except Exception as cleanup_error:
                    logger.exception("Failed rolling back secrets for haproxy {} at {}: {}", app_name, secret_path, cleanup_error)
                    
            # Rollback git operations
            try:
                await git.delete_file(path,commit_message=(f"Rollback haproxy create for {name} in {cluster}/{namespace}"))

            except Exception as cleanup_error:
                logger.exception("Failed rolling back git file {} for haproxy {}: {}", path, app_name, cleanup_error)

    # Creating the ArgoCD application creation background task
    asyncio.create_task(_background_create())

    return app_name


async def delete_haproxy_operation(git: Git, vault: Vault, argocd: ArgoCD, params: HaProxyMeta) -> str:

    cluster, namespace, name = params.cluster.value, params.namespace, params.name

    # Instance's values file path
    path = f"/{cluster}/{namespace}/{name}.yaml"

    # Build the existing ArgoCD app's name
    app_name = build_app_name(cluster, namespace, name, "haproxy")

    # Get current values file for RollBack purposes
    current_yaml = await git.get_file_content(path)

    secret_path = f"/perimeter/haproxy/{cluster}/{namespace}/{name}"

    # Create a baclup for existing secret
    secret_backup: Dict[str, Any] = {}
    secret_existed = False
    try:
        existing_secret = await vault.read_secret(secret_path)
    except HTTPException as vault_exc:

        # If Exception's status code is 404 we should not raise that, it just means secret dosen't exist
        if vault_exc.status_code != 404:
            raise

    # If not entered into except block, store the existing secret for backup and flag it as existed for RollBack purposes
    else:
        secret_backup = existing_secret
        secret_existed = True

    # Start the deleting with deleting the values file
    await git.delete_file(path, commit_message=f"Delete haproxy {name} in {cluster}/{namespace}", branch="master")

    # Store the current state of deletion for rollback purposes, we are not forcing vault secret deletion for a sucessful delete
    vault_deleted = False

    # Quietly failure for vault deletion failed
    try:
        await vault.delete_secret(secret_path)
        vault_deleted = True

    except Exception as secret_error:
        logger.exception(
            "Failed deleting secrets for haproxy {} at {}: {}",
            app_name,
            secret_path,
            secret_error,
        )

        # Create the values file to rollback the deletion (if failed to delete secret)
        try:
            await git.add_file(
                path,
                commit_message=f"Rollback haproxy delete for {name} in {cluster}/{namespace}",
                content=current_yaml,
            )

        # Log rollback git file failure    
        except Exception as cleanup_error:
            logger.exception(
                "Failed restoring git file {} for haproxy {}: {}",
                path,
                app_name,
                cleanup_error,
            )

        raise

    # Continue business logic (ArgoCD application deletion) in the background
    async def _background_delete() -> None:
        stage = "wait"
        try:
            await argocd.wait_for_app_deletion(app_name)
            logger.info(f"{app_name} ArgoCD application deleted")
            stage = "argo" 

        except Exception as e:
            logger.exception("Background delete flow failed for app {} at stage {}: {}", app_name, stage, e)
            try:
                await git.add_file(
                    path,
                    commit_message=f"Rollback haproxy delete for {name} in {cluster}/{namespace}",
                    content=current_yaml,
                )
            except Exception as cleanup_error:
                logger.exception(
                    "Failed restoring git file {} for haproxy {}: {}",
                    path,
                    app_name,
                    cleanup_error,
                )

            # In case secret deletion succedded and secret existed, recreate the secret
            if secret_existed and vault_deleted:
                try:
                    await vault.write_secret(secret_path, secret_backup)
                except Exception as cleanup_error:
                    logger.exception(
                        "Failed restoring secrets for haproxy {} at {}: {}",
                        app_name,
                        secret_path,
                        cleanup_error,
                    )

    asyncio.create_task(_background_delete())

    return app_name

async def update_haproxy_operation(git: Git, vault: Vault, argocd: ArgoCD, payload: HaProxyMeta) -> str:

    path, new_yaml, cluster, namespace, name, secrets_raw, secrets, app_name = _get_parameters(payload)

    current_yaml = await git.get_file_content(path)

    # Modify file if the input not equal to existing yanl
    if not yaml_data_equals(current_yaml, new_yaml):
        await git.modify_file(path, f"Modify haproxy for {app_name} in {cluster}/{namespace}", new_yaml)

    secret_path = f"/perimeter/haproxy/{cluster}/{namespace}/{app_name}"

    previous_secret_data: Dict[str, Any] = {}
    secret_existed = False
    secrets_written = False

    if secrets:
        try:
            try:
                existing_secret = await vault.read_secret(secret_path)
            except HTTPException as vault_exc:
                if vault_exc.status_code != 404:
                    raise
            else:
                previous_secret_data = existing_secret or {}
                secret_existed = True

            await vault.write_secret(secret_path, secrets)
            secrets_written = True
        except Exception as secret_error:
            logger.exception(
                "Failed updating secrets for haproxy {} at {}: {}",
                app_name,
                secret_path,
                secret_error,
            )
            await _restore_git(
                git,
                path,
                app_name,
                current_yaml,
                f"Rollback haproxy update for {app_name} in {cluster}/{namespace}",
            )
            await _restore_secrets_to_previous(
                vault,
                app_name,
                secret_path,
                secrets,
                secret_existed,
                secrets_written,
                previous_secret_data,
            )
            raise

    # Continue business logic in the background
    async def _background_update() -> None:
        try:
            await argocd.sync(app_name)
        except Exception as e:
            logger.exception(
                "Background update flow failed for app {}: {}",
                app_name,
                e,
            )
            await _restore_git(
                git,
                path,
                app_name,
                current_yaml,
                f"Rollback haproxy update for {app_name} in {cluster}/{namespace}",
            )
            await _restore_secrets_to_previous(
                vault,
                app_name,
                secret_path,
                secrets,
                secret_existed,
                secrets_written,
                previous_secret_data,
            )

    asyncio.create_task(_background_update())

    return app_name

async def get_haproxy_operation(git: Git, params: HaProxyMeta) -> dict:
    path = f"/{params.cluster.value}/{params.namespace}/{params.name}.yaml"
    response = await git.get_file_content(path)
    data = yaml.safe_load(response)
    return data

async def haproxy_get_status(git: Git, argocd: ArgoCD ,params: HaProxyIdentifier) -> ArgoOperationResponse:
    cluster, namespace, name = params.cluster.value, params.namespace, params.name
    path = f"/{cluster}/{namespace}/{name}.yaml"

    # Build the argocd app's name
    app_name = build_app_name(cluster, namespace, name, "haproxy")
    await git.file_exists(path)
    
    try:
        return await argocd.get_app_status(app_name)
        
    except HTTPException as e:
        
        if e.status_code == 403:
            return ArgoOperationResponse(status="InProgress", app_name=app_name)
        
        raise
		