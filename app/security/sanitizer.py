import re
import logging
from app.schemas.email_schemas import EmailMetadata

logger = logging.getLogger(__name__)

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"you\s+are\s+now",
    r"new\s+(system|persona|role|instructions)",
    r"forget\s+(everything|all|your\s+training)",
    r"act\s+as\s+(a\s+)?(different|new|unrestricted)",
    r"disregard\s+(your\s+)?(guidelines|rules|restrictions)",
    r"do\s+not\s+(follow|obey|listen\s+to)",
    r"override\s+(safety|system|previous)",
    r"\[system\]",
    r"\[instructions?\]",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"###\s*(instruction|system|prompt)",
    r"assistant:\s*",
    r"user:\s*",
]


def sanitize_text(text: str, max_length: int = 500) -> str:
    """Remove HTML tags, control characters, and truncate."""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[\x00-\x1f\x7f]', '', text)
    text = text.strip()
    return text[:max_length]


def check_injection(text: str) -> tuple[bool, str | None]:
    """Returns (is_suspicious, matched_pattern_description)."""
    if not text:
        return False, None
    lower = text.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lower):
            return True, pattern
    return False, None


def screen_metadata(m: EmailMetadata) -> EmailMetadata:
    """Screen all string fields for injection attempts, sanitize in place."""
    subject = sanitize_text(m.subject, max_length=200)
    sender_name = sanitize_text(m.sender_name, max_length=100)

    subject_suspicious, pattern = check_injection(subject)
    name_suspicious, _ = check_injection(sender_name)

    if subject_suspicious or name_suspicious:
        logger.warning(
            "Prompt injection attempt detected in email metadata. Pattern: %s. Message ID: %s",
            pattern,
            m.message_id,
        )
        subject = "[Content filtered]" if subject_suspicious else subject
        sender_name = "[Name filtered]" if name_suspicious else sender_name

    return m.model_copy(update={"subject": subject, "sender_name": sender_name})


def sanitize_user_message(text: str) -> str:
    """Basic sanitization for WhatsApp user messages."""
    return sanitize_text(text, max_length=1000)
