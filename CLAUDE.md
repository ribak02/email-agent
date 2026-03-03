# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
uv sync
cp .env.example .env

# Development server (hot reload)
uv run uvicorn app.main:app --reload --port 8000

# Tests
uv run pytest tests/ -v
uv run pytest tests/test_sanitizer.py -v  # single test file

# One-time OAuth setup for a user
uv run python scripts/authorize_user.py

# Local webhook tunneling
ngrok http 8000
```

## Architecture

This is a **WhatsApp → LangGraph → Microsoft Graph API** email agent. Users send natural language commands via WhatsApp; the agent reads/organizes their Outlook email.

### Request Flow

```
WhatsApp Webhook (POST /webhook)
  → HMAC-SHA256 signature verification (app/auth/whatsapp_verify.py)
  → Rate limiting: 20 msgs/min per user (Redis counter)
  → Load encrypted MSAL token from Redis (app/services/token_store.py)
  → LangGraph StateGraph (app/agent/graph.py)
      entry_validator → auth_challenger | security_blocked | intent_parser
      intent_parser → clarification_asker | email_reader | email_organizer | email_searcher
      [action node] → response_formatter
  → WhatsApp reply (app/services/whatsapp_client.py)
```

### Key Layers

**`app/agent/`** — LangGraph orchestration
- `graph.py`: 9-node StateGraph with PostgreSQL checkpointer for per-user conversation persistence
- `nodes.py`: All node implementations (entry validation through response formatting)
- `edges.py`: Conditional routing logic
- `prompts.py`: System prompts with security boundaries

**`app/services/`** — External integrations
- `graph_client.py`: Microsoft Graph API wrapper (async, with retry via Tenacity)
- `token_store.py`: MSAL tokens encrypted with Fernet, stored in Redis (90-day TTL)
- `session_store.py`: Session management and rate limiting
- `whatsapp_client.py`: Meta Cloud API

**`app/tools/`** — Email operations called by agent nodes
- `email_reader.py`: List inbox, unread count, folder listing
- `email_organizer.py`: Move emails, create folders
- `email_search.py`: Search by query, sender, date

**`app/schemas/`** — Pydantic models
- `intent_schemas.py`: PydanticAI agent definitions for structured LLM outputs

### Security Model (critical to preserve)

**Email bodies never reach the LLM.** The Graph API `$select` in `graph_client.py` only fetches:
```
id,subject,from,receivedDateTime,isRead,importance,parentFolderId
```

Prompt injection detection runs in `entry_validator` (15 regex patterns in `app/security/sanitizer.py`) before any LLM call. Do not weaken or remove these checks.

### LLM Usage

- **Main model**: `gpt-4o` via `langchain-openai`
- **Structured outputs**: PydanticAI agents in `app/schemas/intent_schemas.py` for intent parsing and email organization decisions
- **State persistence**: LangGraph PostgreSQL checkpointer maintains per-user conversation history

## Configuration

All settings are in `app/config.py` (Pydantic Settings). Required env vars:
- `OPENAI_API_KEY`
- `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`, `AZURE_REDIRECT_URI`
- `META_APP_ID`, `META_APP_SECRET`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_VERIFY_TOKEN`
- `DATABASE_URL`, `REDIS_URL` (auto-injected by Railway)
- `RAILWAY_PUBLIC_DOMAIN`, `SECRET_KEY`

## Deployment

Railway with PostgreSQL + Redis plugins. Docker build uses Python 3.12-slim with `uv` for dependency management. Health check: `GET /health`.
