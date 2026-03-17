import pytest
from fastapi.testclient import TestClient
from v1.dns.schemas import DNSRecordCreate, DNSRecordDelete, DNSRecordCreateSpec, DNSRecordDeleteSpec
from main import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def authenticated_headers():
    # Replace 'your-auth-token' with your actual token
    return {"Authorization": "Bearer 1234"}

@pytest.fixture
def metadata_request():
    return MetadataRequest(
        project="test",
        network="net",
        region="kirya",
        space="net",
        environment="test"
    )

@pytest.fixture
def create_spec():
    return DNSRecordCreateSpec(
        record_name="aln-aln-aln-1",
        ip="190.50.50.160",
        record_type="a",
        dns_zone="net.com"
    )

@pytest.fixture
def delete_spec():
    return DNSRecordDeleteSpec(
        record_name="aln-aln-aln-1",
        record_type="a",
        dns_zone="net.com"
    )

@pytest.fixture
def valid_create_dns_record(metadata_request, create_spec):
    return DNSRecordCreate(
        spec=create_spec,
        metadata=metadata_request
    )

@pytest.fixture
def valid_delete_dns_record(metadata_request, delete_spec):
    return DNSRecordDelete(
        spec=delete_spec,
        metadata=metadata_request
    )

@pytest.fixture
def invalid_create_dns_record(metadata_request):
    return {
        "spec": {
            "record_name": "its-more-then-15",
            "ip": "190.50.50.160",
            "record_type": "a",
            "dns_zone": "net.com"
        },
        "metadata": metadata_request
    }


@pytest.fixture
def invalid_delete_dns_record(metadata_request):
    return {
        "spec": {
            "record_name": "its-more-then-15",
            "record_type": "a",
            "dns_zone": "net.com"
        },
        "metadata": metadata_request
    }