import json
import logging

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)


async def get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def get_user_context(redis_client: aioredis.Redis, phone_number: str) -> dict:
    data = await redis_client.get(f"session:{phone_number}")
    return json.loads(data) if data else {}


async def set_user_context(
    redis_client: aioredis.Redis,
    phone_number: str,
    context: dict,
    ttl: int = 86400,
) -> None:
    await redis_client.set(f"session:{phone_number}", json.dumps(context), ex=ttl)


async def check_rate_limit(
    redis_client: aioredis.Redis,
    phone_number: str,
    limit: int = 20,
    window: int = 60,
) -> bool:
    """Returns True if within rate limit, False if exceeded."""
    key = f"rate:{phone_number}"
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, window)
    within_limit = count <= limit
    if not within_limit:
        logger.warning("Rate limit exceeded for %s (count=%d)", phone_number, count)
    return within_limit
