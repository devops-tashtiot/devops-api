# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the dev server (from the repo root)
uvicorn app.main:create_app --factory --reload --port 5000

# Run all tests
pytest

# Run a specific test suite
pytest tests/v1/dns -v
pytest tests/v2/dns -v

# Run a single test file
pytest tests/v1/dns/test_dns_routes.py -v

# Run with coverage
pytest --cov=app --cov-report=term-missing
```

## Architecture

The app is a FastAPI service that orchestrates DNS records, HAProxy load-balancer configs, and chat messages by delegating to external platforms (AWX, ArgoCD, Vault, Bitbucket/Git). All external client objects are constructed once in `app/main.py:create_app()` and passed into router factories as arguments — there is no global state or DI framework.

**Entry point:** `app/main.py` — `create_app()` builds the FastAPI app via `tashtiot_apis_library.general_create_app()`, instantiates external service clients, and mounts routers.

**Module layout** — every feature under `app/v1/<feature>/` follows this four-file convention:
- `conf.py` — `pydantic-settings` class, reads `.env`; instantiated as `config` at module level
- `schemas.py` — Pydantic request/response models
- `routes.py` — router factory `get_<feature>_router(...)` that closes over injected clients
- `operations.py` / `operation_*.py` — async business logic called by the router

**Configuration** — each module (`global_conf.py`, `v1/dns/conf.py`, `v1/haproxy/conf.py`, `v1/chat/conf.py`) has its own `pydantic-settings` class. All read from `.env` (see `.env.example`). Required fields without defaults must be in `.env` before the app starts (notably `HAPROXY_*`, `ARGOCD_*`, `VAULT_*`).

**Internal library** — `tashtiot-apis-library` (version-pinned in `requirements.txt`) provides `general_create_app`, `BaseAPI`, `Git`, `ArgoCD`, `Vault`, `AWX` connectors, and shared response types like `ArgoOperationResponse` / `ExternalServiceError`. Treat it as a black-box SDK.

**Tests** — `tests/v1/` and `tests/v2/` mirror the app structure. Fixtures (client, mock clients, sample payloads) live in `conftest.py` files at each level. `pytest.ini` sets `pythonpath = .` so imports start from the repo root.

**CI** — Woodpecker (`.woodpecker/build.yaml`). Only the Kaniko image-build step is active; test steps are commented out. Images are pushed to Artifactory on git tags.
