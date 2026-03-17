import pytest
from v1.dns.schemas import DNSRecordCreate, DNSRecordDelete
from pydantic import ValidationError
from fastapi.encoders import jsonable_encoder


def test_create_valid_schema(valid_create_dns_record):
    assert valid_create_dns_record.spec.record_name == "aln-aln-aln-1"
    assert valid_create_dns_record.spec.ip == "190.50.50.160"

def test_delete_valid_schema(valid_delete_dns_record):
    assert valid_delete_dns_record.spec.record_name == "aln-aln-aln-1"

def test_invalid_ip(metadata_request):
    with pytest.raises(ValidationError):
        DNSRecordCreate(
            record_name="test.example.com",
            ip="invalid-ip",
            record_type="A",
            dns_zone="net.com",
            metadata_request=metadata_request
        )

def test_invalid_record_name(metadata_request):
    with pytest.raises(ValidationError):
        DNSRecordCreate(
            record_name="dns-longest-then-15",
            ip="192.168.1.1",
            record_type="A",
            dns_zone="net.com",
            metadata_request=metadata_request
        )