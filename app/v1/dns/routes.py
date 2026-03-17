from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from .schemas import DNSRecordCreate, DNSRecordResponse, DNSRecordUpdate, DNSRecordDelete
from .operation_dns import create_dns, delete_dns, update_dns, get_dns, get_dns_status
from .conf import config
import sys
import os
from loguru import logger

def get_v1_dns_router(awx_client):

    router = APIRouter(prefix=config.API_PREFIX, tags = config.API_TAGS)

    @router.post("/", 
        response_model=DNSRecordResponse,
        summary="Create DNS Record",
        description="Creates a new DNS record with the specified Name and IP address"
    )
    async def create(record: DNSRecordCreate, request: Request) -> DNSRecordResponse:
        logger.info(f"Creating a DNS {record.spec.record_type} record: {record.spec.record_name}")
        logger.info(f"launching AWX job template for creating DNS record: {record.spec.record_name}")
        response = await create_dns(record, awx_client)
        return response

    @router.delete("/",
        response_model=DNSRecordResponse,
        summary="Delete DNS Record",
        description="Deletes an existing DNS record by its name"
    )
    async def delete(record: DNSRecordDelete, request: Request):
        logger.info(f"Deleting a DNS {record.spec.record_type} record: {record.spec.record_name}")
        response = await delete_dns(record, awx_client)
        return response

    @router.put("/{record_name}", 
        response_model=DNSRecordResponse,
        summary="Update DNS Record",
        description="Updates the IP address of an existing DNS record"
    )
    async def update(record_name: str, record: DNSRecordUpdate, request: Request):
        logger.info(f"Updating DNS record: {record_name} with IP: {record.ip}")
        response = update_dns(record_name, record.ip)
        return DNSRecordResponse(record_name=record_name, status= "updated", job_id=1234)

    @router.get("/{record_name}", 
        response_model=DNSRecordResponse,
        summary="Get DNS Record",
        description="Retrieves the details of a DNS record by its name"
    )
    async def get_record(record_name: str, request: Request):
        logger.info(f"Getting DNS record: {record_name}")
        ip = get_dns(record_name)
        return DNSRecordResponse(record_name=record_name, status= "fetched", job_id=1234)

    @router.get("/status/{job_id}", 
        response_model=DNSRecordResponse,
        summary="Get DNS Record Status",
        description="Retrieves the status of a DNS record operation job by its AWX Job ID"
    )
    async def status(job_id: str, request: Request, response: Response):
        
        response = await get_dns_status(job_id, awx_client)

        return response

    return router