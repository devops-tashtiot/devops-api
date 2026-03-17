import sys
import os
import json
from .schemas import DNSRecordCreate, DNSRecordResponse, DNSRecordDelete
from .conf import config

async def create_dns(dns_record: DNSRecordCreate, awx_client) -> DNSRecordResponse:
    extra_vars_json =  {
            "RECORD_TYPE": dns_record.spec.record_type,
            "RECORD_NAME": dns_record.spec.record_name,
            "RECORD_ADDRESS": dns_record.spec.ip,
            "DNS_ZONE": dns_record.spec.dns_zone
	}
    return await awx_client.launch_job(job_template_id=config.AWX_CREATE_DNS_TEMPLATE_ID, extra_vars=extra_vars_json)

async def delete_dns(dns_record: DNSRecordDelete, awx_client) -> DNSRecordResponse:
    extra_vars_json =  {
            "RECORD_TYPE": dns_record.spec.record_type,
            "RECORD_NAME": dns_record.spec.record_name,
            "DNS_ZONE": dns_record.spec.dns_zone
	}
    
    return await awx_client.launch_job(job_template_id=config.AWX_DELETE_DNS_TEMPLATE_ID, extra_vars=extra_vars_json)


def update_dns(record_name: str, ip: str) -> str:
    """Update DNS record with new IP"""
    print(f"update dns record: {record_name} with ip: {ip}")
    return "DNS record updated successfully"

def get_dns(record_name: str) -> str:
    """Get DNS record IP"""
    print(f"get dns record: {record_name}")
    return "192.168.1.1"  # Simulated IP address

async def get_dns_status(awx_job_id: int, awx_client) -> DNSRecordResponse:

    return await awx_client.get_job_status(job_id=awx_job_id)
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
        
    

