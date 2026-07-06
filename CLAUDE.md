# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

`devops-api` is a FastAPI service that exposes our internal devtools as a single, unified API
surface. Its goal is to let day-to-day infra tasks (creating a DNS record, provisioning an
HAProxy config, notifying a chat channel, etc.) happen through one API call instead of a person
manually clicking through AWX, Bitbucket, ArgoCD, and Vault by hand.

It is the automation layer behind **RHDH (Red Hat Developer Hub) software templates**: a user
fills in a self-service form in RHDH, and RHDH calls the matching endpoint here, which then
drives whichever backend system actually performs the work. The user never touches AWX, Git, or
Vault directly — this API is the only thing that needs to know how each backend works.

## How a request flows

Each feature (DNS, HAProxy, Chat, ...) lives under `app/v1/<feature>/` with the same shape:

- `routes.py` — the FastAPI router (HTTP surface, exposed to RHDH)
- `schemas.py` — Pydantic request/response models
- `operations.py` (or `operation_<feature>.py`) — the actual logic that talks to a backend system
- `conf.py` — per-feature settings (API prefix/tags, feature-specific env vars)

`app/main.py` wires everything together: it builds one shared client per backend system (Git,
ArgoCD, Vault, AWX, the internal chat API), and injects those clients into each feature's router.
Feature code never constructs its own client — it receives one that `main.py` already configured.

Backend systems currently integrated:

| Feature | Backend(s) it drives |
|---|---|
| `v1/dns` | AWX (launches a job template that creates/updates/deletes a DNS record) |
| `v1/haproxy` | Git (commits values to a values repo) + ArgoCD (syncs the app) + Vault (writes secrets) |
| `v1/chat` | Internal chat/notification API |

Most create/update/delete operations are async and return an `ArgoOperationResponse`-style
`"InProgress"` status immediately (the underlying job, e.g. an AWX job or an ArgoCD sync, runs in
the background) — callers poll a `/status` endpoint to find out when it actually finished.
