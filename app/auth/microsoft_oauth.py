import asyncio
import json
import logging

import msal
import redis.asyncio as aioredis

from app.config import settings
from app.services.token_store import save_token_cache, load_token_cache

logger = logging.getLogger(__name__)

SCOPES = ["Mail.Read", "Mail.ReadWrite", "offline_access", "User.Read"]


def _build_msal_app(token_cache: msal.SerializableTokenCache | None = None) -> msal.PublicClientApplication:
    return msal.PublicClientApplication(
        client_id=settings.azure_client_id,
        authority=f"https://login.microsoftonline.com/{settings.azure_tenant_id}",
        token_cache=token_cache,
    )


async def initiate_device_flow(phone_number: str, redis_client: aioredis.Redis) -> dict:
    """Start device code flow. Returns dict with user_code and verification_uri."""
    cache = msal.SerializableTokenCache()
    cached = await load_token_cache(redis_client, phone_number)
    if cached:
        cache.deserialize(cached)

    app = _build_msal_app(cache)
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise RuntimeError(f"Device flow failed: {flow.get('error_description', 'Unknown error')}")

    # Store the flow state in Redis for 10 minutes so we can poll later
    await redis_client.set(f"oauth_flow:{phone_number}", json.dumps(flow), ex=600)
    return flow


async def poll_for_token(phone_number: str, redis_client: aioredis.Redis) -> bool:
    """Poll for token completion. Returns True if authorized."""
    flow_data = await redis_client.get(f"oauth_flow:{phone_number}")
    if not flow_data:
        return False

    flow = json.loads(flow_data)
    cache = msal.SerializableTokenCache()
    app = _build_msal_app(cache)

    result = app.acquire_token_by_device_flow(flow)
    if "access_token" in result:
        await save_token_cache(redis_client, phone_number, cache.serialize())
        await redis_client.delete(f"oauth_flow:{phone_number}")
        logger.info("OAuth completed for %s", phone_number)
        return True
    return False


async def get_access_token(phone_number: str, redis_client: aioredis.Redis) -> str | None:
    """Get a valid access token, silently refreshing if needed. Returns None if not authorized."""
    cached = await load_token_cache(redis_client, phone_number)
    if not cached:
        return None

    cache = msal.SerializableTokenCache()
    cache.deserialize(cached)
    app = _build_msal_app(cache)

    accounts = app.get_accounts()
    if not accounts:
        return None

    result = app.acquire_token_silent(scopes=SCOPES, account=accounts[0])
    if result and "access_token" in result:
        # Save updated cache (may contain refreshed tokens)
        if cache.has_state_changed:
            await save_token_cache(redis_client, phone_number, cache.serialize())
        return result["access_token"]

    logger.warning("Silent token acquisition failed for %s", phone_number)
    return None
