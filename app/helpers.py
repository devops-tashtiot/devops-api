import httpx
from fastapi import HTTPException
from loguru import logger


async def fetch_from_s3(url: str, label: str, timeout: float = 60.0) -> bytes:
    try:
        async with httpx.AsyncClient(verify=False, timeout=timeout) as client:
            response = await client.get(url)
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"{label} not found in S3: {url}")
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail=f"S3 returned {response.status_code} for {url}")
            logger.info(f"Fetched {label} from S3 ({len(response.content)} bytes): {url}")
            return response.content
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch {label} from S3 ({url}): {e}")
        raise HTTPException(status_code=502, detail=f"S3 fetch failed: {e}")
