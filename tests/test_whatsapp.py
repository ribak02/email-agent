import pytest
from app.auth.whatsapp_verify import verify_whatsapp_signature
from app.services.whatsapp_client import extract_message_from_payload
import hashlib
import hmac


def test_verify_whatsapp_signature_valid():
    body = b'{"test": "payload"}'
    secret = "my-app-secret"
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_whatsapp_signature(body, signature, secret) is True


def test_verify_whatsapp_signature_invalid():
    body = b'{"test": "payload"}'
    assert verify_whatsapp_signature(body, "sha256=invalidsig", "my-secret") is False


def test_verify_whatsapp_signature_tampered_body():
    body = b'{"test": "payload"}'
    tampered = b'{"test": "tampered"}'
    secret = "my-app-secret"
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_whatsapp_signature(tampered, signature, secret) is False


def test_extract_message_from_payload_success():
    payload = {
        "entry": [{"changes": [{"value": {"messages": [
            {"type": "text", "from": "+1234567890", "text": {"body": "Hello"}}
        ]}}]}]
    }
    result = extract_message_from_payload(payload)
    assert result is not None
    phone, text = result
    assert phone == "+1234567890"
    assert text == "Hello"


def test_extract_message_returns_none_for_non_text():
    payload = {
        "entry": [{"changes": [{"value": {"messages": [
            {"type": "image", "from": "+1234567890"}
        ]}}]}]
    }
    assert extract_message_from_payload(payload) is None


def test_extract_message_returns_none_for_empty_messages():
    payload = {"entry": [{"changes": [{"value": {"messages": []}}]}]}
    assert extract_message_from_payload(payload) is None


def test_extract_message_returns_none_for_malformed():
    assert extract_message_from_payload({}) is None
    assert extract_message_from_payload({"entry": []}) is None
