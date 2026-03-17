from v1.dns.conf import API_PREFIX
from fastapi.encoders import jsonable_encoder

def test_create_valid_dns_record(client, valid_create_dns_record, authenticated_headers):
    response = client.post(API_PREFIX, json=jsonable_encoder(valid_create_dns_record), headers=authenticated_headers)
    assert response.status_code == 200

def test_create_invalid_dns_record(client, invalid_create_dns_record, authenticated_headers):
    response = client.post(API_PREFIX, json=jsonable_encoder(invalid_create_dns_record), headers=authenticated_headers)
    assert response.status_code == 422

def test_delete_valid_dns_record(client, valid_delete_dns_record, authenticated_headers):
    response = client.request(method='DELETE',url=API_PREFIX, json=jsonable_encoder(valid_delete_dns_record), headers=authenticated_headers)
    assert response.status_code == 200

def test_delete_invalid_dns_record(client, invalid_delete_dns_record, authenticated_headers):
    response = client.request(method='DELETE', url=API_PREFIX, json=jsonable_encoder(invalid_delete_dns_record), headers=authenticated_headers)
    assert response.status_code == 422
