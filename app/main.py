from fastapi import FastAPI
from .v1.dns.routes import get_v1_dns_router
from .global_conf import global_config
import uvicorn
from tashtiot_apis_library.fastapi_template.utils import BaseAPI
from tashtiot_apis_library import general_create_app, Git, ArgoCD, Vault, AWX
from .v1.haproxy.conf import config as ha_proxy_config
from .v1.haproxy.routes import get_router
from .v1.chat.routes import get_v1_chat_router

def create_app() -> FastAPI:
    app = general_create_app()
    
    # Configure external services objects
    chat_client = BaseAPI(global_config.CHAT_API_URL, headers={"x-api-token": global_config.CHAT_API_TOKEN}).client
    awx_client = AWX(global_config.AWX_URL, global_config.AWX_TOKEN)
    git = Git(base_url=ha_proxy_config.HAPROXY_VALUES_REPO_URL,token=ha_proxy_config.HAPROXY_VALUES_REPO_ACCESS_TOKEN, username_or_email=ha_proxy_config.HAPROXY_VALUES_REPO_EMAIL, project_key=ha_proxy_config.HAPROXY_REPO_PROJECT_KEY, repo_slug=ha_proxy_config.HAPROXY_VALUES_REPO_SLUG, default_ref="master", ssh_key_file_path=ha_proxy_config.HAPROXY_VALUES_REPO_SSH_KEY_PATH)
    argocd = ArgoCD(global_config.ARGOCD_URL, global_config.ARGOCD_TOKEN, global_config.APPLICATION_SET_TIMEOUT)
    vault = Vault(global_config.VAULT_URL, global_config.VAULT_TOKEN)
    
    # Add routes to app
    app.include_router(get_router(git=git, argocd=argocd, vault=vault))

    # Include DNS routes
    app.include_router(get_v1_dns_router(awx_client))

    app.include_router(get_v1_chat_router(chat_client))

    return app

if __name__ == "__main__":
	app = create_app()
    
	uvicorn.run(app, host="0.0.0.0", port=5000)
