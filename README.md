# Email Agent

A personal AI agent that manages your Microsoft Outlook inbox via WhatsApp. Send it a message like "organize my inbox" or "show me emails from John" and it handles everything — running 24/7 in the cloud with no laptop required.

## What It Does

- **Organizes your inbox** — automatically moves emails into folders (newsletters, notifications, etc.)
- **Shows unread emails** — summarizes what's waiting for you
- **Searches your inbox** — find emails by sender, subject, or keyword
- **Moves emails** — "move all emails from Stripe to Finance folder"
- **Creates folders** — on the fly as needed
- **Talks to you via WhatsApp** — no app to install, just message it

## Architecture

```
WhatsApp → Meta Cloud API → FastAPI (Railway)
                                │
                    LangGraph StateGraph
                    ┌───────────┴────────────┐
                    │                        │
              PydanticAI agents      Microsoft Graph API
              (claude-sonnet-4-6)    (Outlook / Exchange)
                    │                        │
              PostgreSQL              Redis
              (conversation          (tokens,
               checkpoints)           rate limits)
```

**Tech stack:**
- **Agent framework:** LangGraph (workflow orchestration) + PydanticAI (structured LLM outputs)
- **LLM:** Claude (`claude-sonnet-4-6`) via Anthropic API
- **Email:** Microsoft Graph API with MSAL authentication
- **WhatsApp:** Meta Cloud API (direct, no Twilio)
- **API:** FastAPI + uvicorn
- **Deployment:** Railway (app + PostgreSQL + Redis plugins)

## Project Structure

```
email-agent/
├── app/
│   ├── main.py                    # FastAPI app, WhatsApp webhook endpoints
│   ├── config.py                  # All settings via pydantic-settings
│   ├── agent/
│   │   ├── graph.py               # LangGraph StateGraph (the agent brain)
│   │   ├── state.py               # AgentState TypedDict
│   │   ├── nodes.py               # Node functions (email_reader, organizer, etc.)
│   │   ├── edges.py               # Conditional routing logic
│   │   └── prompts.py             # System prompts with security rules
│   ├── tools/
│   │   ├── email_reader.py        # List inbox, unread count, folders
│   │   ├── email_organizer.py     # Move emails, create folders
│   │   └── email_search.py        # Search by query, sender, date
│   ├── schemas/
│   │   ├── email_schemas.py       # Pydantic models (EmailMetadata, FolderInfo, etc.)
│   │   └── intent_schemas.py      # PydanticAI output types + agent instances
│   ├── services/
│   │   ├── graph_client.py        # Microsoft Graph API wrapper (httpx + retry)
│   │   ├── token_store.py         # Encrypted MSAL token cache in Redis
│   │   ├── whatsapp_client.py     # Send WhatsApp messages via Meta API
│   │   └── session_store.py       # Redis session + rate limiting
│   ├── security/
│   │   ├── sanitizer.py           # Strip HTML, control chars, truncate
│   │   └── prompt_guard.py        # Prompt injection pattern detection
│   └── auth/
│       ├── microsoft_oauth.py     # MSAL device code flow + silent refresh
│       └── whatsapp_verify.py     # HMAC-SHA256 webhook signature verification
├── scripts/
│   └── authorize_user.py          # One-time CLI to connect an Outlook account
├── tests/
│   ├── test_sanitizer.py
│   ├── test_whatsapp.py
│   └── test_graph_client.py
├── Dockerfile
├── railway.toml
├── requirements.txt
└── .env.example
```

## Security

Email bodies are **never fetched or passed to the LLM** — only sanitized metadata (subject, sender, date, read status) is used. This prevents prompt injection attacks where a malicious email tries to hijack the agent.

Five layers of protection:
1. Microsoft Graph `$select` explicitly excludes `body`, `bodyPreview`, `uniqueBody`
2. All metadata fields are stripped of HTML and control characters before use
3. Regex-based injection pattern detection (15 patterns covering common attack vectors)
4. System prompts establish a clear boundary: email fields are *data*, not *instructions*
5. PydanticAI enforces typed output schemas — unexpected LLM output is rejected before any action

---

## Setup Guide

### Prerequisites

- Python 3.12+
- A Railway account (free tier works)
- A Microsoft account with Outlook (personal or work/school)
- A Meta developer account (for WhatsApp)
- An Anthropic API key

---

### Step 1: Azure App Registration (Microsoft Graph)

1. Go to [portal.azure.com](https://portal.azure.com) → **Azure Active Directory** → **App registrations** → **New registration**
2. Name: anything (e.g. "Email Agent")
3. Supported account types: **Accounts in any organizational directory and personal Microsoft accounts**
4. Redirect URI: **Web** → `https://your-app.up.railway.app/auth/callback` (update after Railway deploy)
5. Click **Register**, then note:
   - **Application (client) ID** → `AZURE_CLIENT_ID`
   - **Directory (tenant) ID** → `AZURE_TENANT_ID`
6. Go to **Certificates & secrets** → **New client secret** → copy the value → `AZURE_CLIENT_SECRET`
7. Go to **API permissions** → **Add a permission** → **Microsoft Graph** → **Delegated permissions**, add:
   - `Mail.Read`
   - `Mail.ReadWrite`
   - `offline_access`
   - `User.Read`
8. Click **Grant admin consent** (if on a work tenant, may require admin)

---

### Step 2: Meta WhatsApp App

1. Go to [developers.facebook.com](https://developers.facebook.com) → **Create App** → **Business** → Next
2. Add **WhatsApp** product to your app
3. Go to **WhatsApp → API Setup**:
   - Note the **Phone number ID** → `WHATSAPP_PHONE_NUMBER_ID`
   - Note the **App ID** → `META_APP_ID`
4. Go to **App Settings → Basic** → note the **App Secret** → `META_APP_SECRET`
5. For the access token:
   - **Development:** Use the temporary token shown on the API Setup page (24h, good for testing)
   - **Production:** Go to [Meta Business Suite](https://business.facebook.com) → **System Users** → create a system user → generate a permanent token with `whatsapp_business_messaging` permission → `WHATSAPP_ACCESS_TOKEN`
6. Choose a **verify token** — any random string you invent → `WHATSAPP_VERIFY_TOKEN`

> **Note:** During development, Meta provides a free test phone number. No business verification is needed to test. For production, you'll need to add and verify your own phone number.

---

### Step 3: Deploy to Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and initialize
railway login
cd /path/to/email-agent
railway init

# Add database plugins
railway add --plugin postgresql   # sets DATABASE_URL automatically
railway add --plugin redis        # sets REDIS_URL automatically

# Set all environment variables
railway variables set ANTHROPIC_API_KEY=sk-ant-...
railway variables set AZURE_CLIENT_ID=...
railway variables set AZURE_CLIENT_SECRET=...
railway variables set AZURE_TENANT_ID=...
railway variables set META_APP_ID=...
railway variables set META_APP_SECRET=...
railway variables set WHATSAPP_PHONE_NUMBER_ID=...
railway variables set WHATSAPP_ACCESS_TOKEN=...
railway variables set WHATSAPP_VERIFY_TOKEN=my-random-secret-string
railway variables set SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
railway variables set ENVIRONMENT=production
railway variables set LOG_LEVEL=INFO

# Deploy
railway up

# Get your public URL
railway domain
# → e.g. https://email-agent-production.up.railway.app

# Set URL-dependent vars
railway variables set RAILWAY_PUBLIC_DOMAIN=https://email-agent-production.up.railway.app
railway variables set AZURE_REDIRECT_URI=https://email-agent-production.up.railway.app/auth/callback

# Redeploy with updated vars
railway up
```

---

### Step 4: Register the WhatsApp Webhook

1. In your Meta App Dashboard → **WhatsApp → Configuration → Webhooks**
2. **Callback URL:** `https://your-app.up.railway.app/webhook/whatsapp`
3. **Verify token:** the value you set as `WHATSAPP_VERIFY_TOKEN`
4. Click **Verify and Save**
5. Under **Webhook fields**, subscribe to: `messages`

Verify it's working: `GET https://your-app.up.railway.app/health` should return `{"status": "healthy"}`.

---

### Step 5: Connect Your Outlook Account

Run this once to authorize your Microsoft account:

```bash
# Make sure your .env is set up locally first (copy from .env.example)
cp .env.example .env
# Fill in all values, then:

python scripts/authorize_user.py --phone +1234567890
```

It will output something like:
```
==================================================
  Visit:  https://microsoft.com/devicelogin
  Code:   ABCD1234
==================================================

Waiting for authorization......
✓ Authorization successful for +1234567890!
```

Open the link on any device, enter the code, and sign in with your Microsoft/Outlook account. The token is stored encrypted in Redis and auto-refreshes for 90 days.

---

### Step 6: Test It

Send a WhatsApp message to your test number:

- `show me my unread emails`
- `organize my inbox`
- `search for emails from stripe`
- `move newsletters to a Newsletters folder`
- `how many unread emails do I have?`

---

## Local Development

```bash
# Clone and set up
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy and fill in env vars
cp .env.example .env

# For local webhook testing, use ngrok to get a public URL:
ngrok http 8000
# Set your Meta webhook URL to the ngrok URL
# Set RAILWAY_PUBLIC_DOMAIN and AZURE_REDIRECT_URI to the ngrok URL

# Run the server
uvicorn app.main:app --reload --port 8000

# Run tests
pytest tests/ -v
```

---

## Environment Variables Reference

| Variable | Description | Where to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key | [console.anthropic.com](https://console.anthropic.com) |
| `AZURE_CLIENT_ID` | Azure app client ID | Azure Portal → App registrations |
| `AZURE_CLIENT_SECRET` | Azure app client secret | Azure Portal → Certificates & secrets |
| `AZURE_TENANT_ID` | Azure tenant ID | Azure Portal → App registrations |
| `AZURE_REDIRECT_URI` | OAuth callback URL | Must match what's in Azure Portal |
| `META_APP_ID` | Meta app ID | Meta App Dashboard → App Settings |
| `META_APP_SECRET` | Meta app secret | Meta App Dashboard → App Settings → Basic |
| `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp phone number ID | Meta App → WhatsApp → API Setup |
| `WHATSAPP_ACCESS_TOKEN` | WhatsApp access token | Meta Business Suite (system user) |
| `WHATSAPP_VERIFY_TOKEN` | Webhook verify token | You create this — any random string |
| `DATABASE_URL` | PostgreSQL connection string | Auto-set by Railway PostgreSQL plugin |
| `REDIS_URL` | Redis connection string | Auto-set by Railway Redis plugin |
| `RAILWAY_PUBLIC_DOMAIN` | Your Railway app URL | Output of `railway domain` |
| `SECRET_KEY` | 64-char hex secret for token encryption | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ENVIRONMENT` | `production` or `development` | Set manually |
| `LOG_LEVEL` | `INFO`, `DEBUG`, `WARNING` | Set manually |

---

## How the Agent Works

Each WhatsApp message triggers this flow:

1. **Webhook receives message** — HMAC signature verified immediately
2. **Rate limit check** — max 20 messages/minute per user (Redis counter)
3. **Auth check** — looks up Microsoft token in Redis; if missing, sends OAuth link
4. **LangGraph graph invoked** — per-user conversation state loaded from PostgreSQL
5. **Intent parsed** — PydanticAI + Claude determines what the user wants
6. **Email action executed** — Graph API called with sanitized metadata only
7. **Response formatted** — PydanticAI formats a WhatsApp-friendly reply
8. **State saved** — conversation checkpoint written to PostgreSQL
9. **Reply sent** — Meta Cloud API delivers the response

The conversation state persists across messages, so the agent remembers context within a session.

---

## Troubleshooting

**WhatsApp messages not arriving:**
- Check Railway logs: `railway logs --tail`
- Verify webhook is subscribed to `messages` in Meta Dashboard
- Confirm `WHATSAPP_VERIFY_TOKEN` matches exactly

**"I couldn't connect to your Outlook account":**
- Re-run `python scripts/authorize_user.py --phone +YOUR_NUMBER`
- Check that `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID` are correct

**Agent not responding / timing out:**
- Check that `DATABASE_URL` and `REDIS_URL` are set correctly
- Verify Railway PostgreSQL and Redis plugins are attached to the service

**Token expired after 90 days:**
- Re-run the `authorize_user.py` script to refresh
