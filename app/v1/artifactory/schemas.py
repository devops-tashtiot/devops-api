from pydantic import BaseModel, Field

class StorageQuotaBytes(BaseModel):
    name: str = Field(
        ...,
        description="project or repo name",
    )
    
    storage_quota_giga_bytes: int = Field(
        description="storage quota giga bytes",
        gt=0, # Ensure positive integer
        le=10 # max GB per request
    )