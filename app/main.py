from fastapi import FastAPI
from .global_conf import global_config
import uvicorn
from tashtiot_apis_library.fastapi_template.utils import BaseAPI
from tashtiot_apis_library import general_create_app

from tashtiot_apis_library import Git

from .v1.artifactory.routes import get_v1_artifactory_router
from .v1.bitbucket.routes import get_v1_bitbucket_router
from .v1.confluence.routes import get_v1_confluence_router
from .v1.argocd.routes import get_v1_argocd_router
from .v1.argocd.conf import config as argocd_config
from .v1.sonarqube.routes import get_v1_sonarqube_router
from .v1.sonarqube.conf import config as sonarqube_config
from .v1.jira.routes import get_v1_jira_router
def create_app() -> FastAPI:
    app = general_create_app()
    
    # Configure external services objects
    if global_config.ARTIFACTORY_ENABLE_API:
        artifactory_client = BaseAPI(
            global_config.ARTIFACTORY_API_URL,
            headers={"Authorization": f"Bearer {global_config.ARTIFACTORY_API_TOKEN}"}
        ).client
        app.include_router(get_v1_artifactory_router(artifactory_client))
        
    if global_config.BITBUCKET_ENABLE_API:
        bitbucket_client = BaseAPI(
            global_config.BITBUCKET_API_URL,
            auth=(global_config.BITBUCKET_USERNAME, global_config.BITBUCKET_PASSWORD)
        ).client
        app.include_router(get_v1_bitbucket_router(bitbucket_client))

    if global_config.CONFLUENCE_ENABLE_API:
        confluence_client = BaseAPI(
            global_config.CONFLUENCE_API_URL,
            auth=(global_config.CONFLUENCE_USERNAME, global_config.CONFLUENCE_PASSWORD)
        ).client
        app.include_router(get_v1_confluence_router(confluence_client))

    if global_config.SONARQUBE_ENABLE_API:
        sonarqube_git = Git(
            base_url=global_config.GIT_API_URL,
            token=global_config.GIT_TOKEN,
            username_or_email=global_config.GIT_USERNAME,
            project_key=global_config.GIT_PROJECT_KEY,
            repo_slug=global_config.SONARQUBE_AAS_REPO_SLUG,
            default_ref=sonarqube_config.SONARQUBE_GITOPS_DEFAULT_BRANCH,
            ssh_key_file_path=global_config.GIT_SSH_KEY_PATH,
        )
        app.include_router(get_v1_sonarqube_router(sonarqube_git))

    if global_config.JIRA_ENABLE_API:
        jira_client = BaseAPI(
            global_config.JIRA_API_URL,
            auth=(global_config.JIRA_USERNAME, global_config.JIRA_PASSWORD)
        ).client
        app.include_router(get_v1_jira_router(jira_client))

    if global_config.ARGOCD_ENABLE_API:
        git = Git(
            base_url=global_config.GIT_API_URL,
            token=global_config.GIT_TOKEN,
            username_or_email=global_config.GIT_USERNAME,
            project_key=global_config.GIT_PROJECT_KEY,
            repo_slug=global_config.ARGOCD_AAS_REPO_SLUG,
            default_ref=argocd_config.ARGOCD_GITOPS_DEFAULT_BRANCH,
            ssh_key_file_path=global_config.GIT_SSH_KEY_PATH,
        )
        app.include_router(get_v1_argocd_router(
            git,
            argocd_timeout=argocd_config.ARGOCD_APPLICATION_SET_TIMEOUT,
        ))

    return app

if __name__ == "__main__":
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=5000)