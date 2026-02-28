import base64
import hashlib
import logging

import redis.asyncio as aioredis
from cryptography.fernet import Fernet

from app.config import settings

logger = logging.getLogger(__name__)

TOKEN_TTL = 7_776_000  # 90 days in seconds


def _get_fernet() -> Fernet:
    """Derive a stable 32-byte Fernet key from SECRET_KEY."""
    key_bytes = hashlib.sha256(settings.secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


async def save_token_cache(redis_client: aioredis.Redis, phone_number: str, cache_str: str) -> None:
    """Encrypt and persist MSAL token cache to Redis."""
    fernet = _get_fernet()
    encrypted = fernet.encrypt(cache_str.encode())
    await redis_client.set(f"ms_token:{phone_number}", encrypted, ex=TOKEN_TTL)
    logger.debug("Saved token cache for %s", phone_number)


async def load_token_cache(redis_client: aioredis.Redis, phone_number: str) -> str | None:
    """Load and decrypt MSAL token cache from Redis."""
    fernet = _get_fernet()
    data = await redis_client.get(f"ms_token:{phone_number}")
    if not data:
        return None
    try:
        return fernet.decrypt(data).decode()
    except Exception:
        logger.warning("Failed to decrypt token cache for %s", phone_number)
        return None


async def delete_token_cache(redis_client: aioredis.Redis, phone_number: str) -> None:
    await redis_client.delete(f"ms_token:{phone_number}")
