# Example-FastAPI-template

## Project Structure
```
Here is the project structure with a brief explanation for each row:

main.py - The main file of the api server.

metadata.py - A file containing metadata for the entire api (team scope).

v1/ - The first version of the API.
    dns/ - A directory for DNS-related functionality.
        metadata.py -  Metadata for the DNS service (DNS scope).
        routes.py -  Routing configuration for the DNS service.
        schemas.py -  Schema definitions for the requests and responses of the DNS service.
        operation -  Operations related to DNS.

    fqdn/ - A directory for fully qualified domain name (FQDN) functionality.
        metadata.py -  Metadata for the FQDN service (FQDN scope).
        routes.py -  Routing configuration for the FQDN service.
        schemas.py -  Schema definitions for the requests and responses of the FQDN service.
        operation -  Operations related to FQDN.

v2/ -  The second version of the API.
    dns/ - A directory for DNS-related functionality.
        metadata.py -  Metadata for the DNS service (DNS scope).
        routes.py -  Routing configuration for the DNS service.
        schemas.py -  Schema definitions for the requests and responses of the DNS service.
        operation -  Operations related to DNS.

    fqdn/ - A directory for fully qualified domain name (FQDN) functionality.
        metadata.py -  Metadata for the FQDN service (FQDN scope).
        routes.py -  Routing configuration for the FQDN service.
        schemas.py -  Schema definitions for the requests and responses of the FQDN service.
        operation -  Operations related to FQDN.

tests/ -  A directory for unit tests for the api server capabilities.

```




## Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run FastAPI server
uvicorn main:app --reload --port 5000
```

## Docker Deployment
```bash
# Build Docker image
docker build -t dns-api .

# Run Docker container
docker run -p 5000:5000 dns-api
```
## API Documentation
OpenAPI UI: http://localhost:5000/docs

Metrics: http://localhost:5000/metrics
