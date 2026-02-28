import hashlib
import hmac


def verify_whatsapp_signature(body: bytes, signature_header: str, app_secret: str) -> bool:
    """
    Verify Meta webhook X-Hub-Signature-256 header using HMAC-SHA256.
    Uses constant-time comparison to prevent timing attacks.
    """
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    received = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)
