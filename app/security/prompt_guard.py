from app.security.sanitizer import check_injection


def is_safe_message(message: str) -> bool:
    """Return False if the message looks like a prompt injection attempt."""
    suspicious, _ = check_injection(message)
    return not suspicious


def redact_if_unsafe(text: str, replacement: str = "[filtered]") -> str:
    suspicious, _ = check_injection(text)
    return replacement if suspicious else text
