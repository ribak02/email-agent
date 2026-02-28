import logging
from contextlib import asynccontextmanager

import asyncpg
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.agent.graph import create_graph
from app.auth.microsoft_oauth import get_access_token, initiate_device_flow
from app.auth.whatsapp_verify import verify_whatsapp_signature
from app.config import settings
from app.security.sanitizer import sanitize_user_message
from app.services.session_store import check_rate_limit, get_redis
from app.services.whatsapp_client import extract_message_from_payload, send_text_message

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

_graph = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph
    logger.info("Starting email agent service...")
    conn = await asyncpg.connect(settings.database_url)
    checkpointer = AsyncPostgresSaver(conn)
    await checkpointer.setup()
    _graph = await create_graph(checkpointer)
    logger.info("LangGraph agent compiled and ready.")
    yield
    await conn.close()
    logger.info("Email agent service stopped.")


app = FastAPI(title="Email Agent", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "email-agent"}


@app.get("/webhook/whatsapp")
async def verify_webhook(request: Request):
    """Meta webhook verification handshake."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == settings.whatsapp_verify_token:
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Webhook verification failed")


@app.post("/webhook/whatsapp")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    """Receive incoming WhatsApp messages. Returns 200 immediately."""
    body = await request.body()
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not verify_whatsapp_signature(body, sig, settings.meta_app_secret):
        logger.warning("Invalid webhook signature received")
        raise HTTPException(status_code=403, detail="Invalid signature")
    payload = await request.json()
    background_tasks.add_task(_process_whatsapp_message, payload)
    return {"status": "ok"}


async def _process_whatsapp_message(payload: dict) -> None:
    """Process an incoming WhatsApp message in the background."""
    result = extract_message_from_payload(payload)
    if not result:
        return

    phone_number, user_message = result
    redis = await get_redis()

    try:
        if not await check_rate_limit(redis, phone_number):
            await send_text_message(
                phone_number,
                "You're sending messages too quickly. Please wait a moment and try again.",
            )
            return

        user_message = sanitize_user_message(user_message)
        access_token = await get_access_token(phone_number, redis)

        if not access_token:
            try:
                flow = await initiate_device_flow(phone_number, redis)
                user_code = flow.get("user_code", "")
                verification_uri = flow.get("verification_uri", "https://microsoft.com/devicelogin")
                await send_text_message(
                    phone_number,
                    f"To connect your Outlook account, please:\n\n"
                    f"1. Visit: {verification_uri}\n"
                    f"2. Enter code: {user_code}\n"
                    f"3. Sign in with your Microsoft account\n\n"
                    f"Then send me a message to continue.",
                )
            except Exception as e:
                logger.error("Failed to initiate OAuth flow: %s", e)
                await send_text_message(
                    phone_number,
                    "I couldn't connect to your Outlook account. Please try again later.",
                )
            return

        input_state = {
            "user_message": user_message,
            "phone_number": phone_number,
            "ms_access_token": access_token,
            "needs_auth": False,
            "needs_clarification": False,
            "injection_detected": False,
            "messages": [],
        }
        config = {
            "configurable": {
                "thread_id": phone_number,
                "checkpoint_ns": "email_agent",
            }
        }

        graph_result = await _graph.ainvoke(input_state, config=config)
        response_text = graph_result.get(
            "response_text",
            "Sorry, I encountered an error. Please try again.",
        )
        await send_text_message(phone_number, response_text)

    except Exception as e:
        logger.error("Error processing message from %s: %s", phone_number, e)
        await send_text_message(
            phone_number,
            "Sorry, something went wrong. Please try again in a moment.",
        )
    finally:
        await redis.aclose()
