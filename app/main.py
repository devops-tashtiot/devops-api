from fastapi import FastAPI
from .global_conf import global_config
import uvicorn
from tashtiot_apis_library.fastapi_template.utils import BaseAPI
from tashtiot_apis_library import general_create_app

from .v1.artifactory.routes import get_v1_artifactory_router
from .v1.bitbucket.routes import get_v1_bitbucket_router

def create_app() -> FastAPI:
    app = general_create_app()
    
    # Configure external services objects
    if global_config.ENABLE_ARTIFACTORY_API:
        artifactory_client = BaseAPI(
            global_config.ARTIFACTORY_API_URL,
            headers={"Authorization": f"Bearer {global_config.ARTIFACTORY_API_TOKEN}"}
        ).client
        app.include_router(get_v1_artifactory_router(artifactory_client))
        
    if global_config.ENABLE_BITBUCKET_API:
        bitbucket_client = BaseAPI(
            global_config.BITBUCKET_API_URL,
            auth=(global_config.BITBUCKET_USERNAME, global_config.BITBUCKET_PASSWORD)
        ).client
        app.include_router(get_v1_bitbucket_router(bitbucket_client))
        
    return app

if __name__ == "__main__":
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=5000)