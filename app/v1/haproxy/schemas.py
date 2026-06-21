from pydantic import BaseModel, Field, model_validator
from typing import Optional, List
from enum import Enum
from tashtiot_apis_library import DefaultMetaSpec, ResourceSpec, NameNamespace, OperationRequest
from .conf import config

ClusterEnum = Enum("ClusterEnum", {c: c for c in config.CLUSTERS})


class HaProxyMeta(DefaultMetaSpec):

    cluster: ClusterEnum = Field(..., description="Allowed clusters to deploy HaProxy in.")
    
    version: str = Field(..., description="Allowed versions.")


class HaProxyValues(BaseModel):
    
    backends: List = Field(..., description="HaProxy backends.")

    resources: Optional[ResourceSpec] = Field(default=None, description="HaProxy resources requests and limits.")


class HaProxySecrets(BaseModel):
    # example secrets
    sheker_secret: str = Field(default="token", description="Some sheker secret.")


class HaProxySpec(BaseModel):

    metadata: HaProxyMeta = Field(..., description="Metadata about the deployment (cluster, namespace, name)")

    values: HaProxyValues = Field(..., description="Values serialized into YAML (required)")

    secrets: HaProxySecrets = Field(..., description="HaProxy's secrets schema.")


class HaProxyPayload(OperationRequest):

    spec: HaProxySpec = Field(..., description="Haproxy's spec schema.")
    
    
class HaProxyIdentifier(NameNamespace):
    
    cluster: ClusterEnum = Field(..., description="Allowed clusters to deploy HaProxy in.")

HaProxyMeta.model_rebuild()
HaProxyValues.model_rebuild()
HaProxySecrets.model_rebuild()
HaProxySpec.model_rebuild()
HaProxyPayload.model_rebuild()
HaProxyIdentifier.model_rebuild()