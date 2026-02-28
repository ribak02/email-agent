import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone


@pytest.fixture
def mock_email_response():
    return {
        "value": [
            {
                "id": "AAMkABC123",
                "subject": "Test Email",
                "from": {
                    "emailAddress": {
                        "address": "sender@example.com",
                        "name": "Test Sender",
                    }
                },
                "receivedDateTime": "2024-01-15T10:30:00Z",
                "isRead": False,
                "importance": "normal",
                "parentFolderId": "inbox-folder-id",
            }
        ]
    }


@pytest.mark.asyncio
async def test_list_inbox_messages_parses_response(mock_email_response):
    with patch("app.services.graph_client._get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_email_response
        from app.services.graph_client import list_inbox_messages
        result = await list_inbox_messages("fake-token", top=20)

    assert len(result) == 1
    assert result[0].subject == "Test Email"
    assert result[0].sender_email == "sender@example.com"
    assert result[0].is_read is False


@pytest.mark.asyncio
async def test_list_inbox_messages_excludes_body():
    """Verify that $select never includes body fields."""
    captured_params = {}

    async def capture_get(url, token, params=None):
        captured_params.update(params or {})
        return {"value": []}

    with patch("app.services.graph_client._get", side_effect=capture_get):
        from app.services.graph_client import list_inbox_messages
        await list_inbox_messages("fake-token")

    select = captured_params.get("$select", "")
    assert "body" not in select.lower()
    assert "bodyPreview" not in select
    assert "uniqueBody" not in select


@pytest.mark.asyncio
async def test_move_message_calls_correct_endpoint():
    with patch("app.services.graph_client._post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = {"id": "AAMkABC123"}
        from app.services.graph_client import move_message
        result = await move_message("fake-token", "AAMkABC123", "dest-folder-id")

    assert result.success is True
    assert result.message_id == "AAMkABC123"
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert "AAMkABC123/move" in call_args[0][0]


@pytest.mark.asyncio
async def test_move_message_handles_error():
    import httpx
    with patch("app.services.graph_client._post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock(status_code=404)
        )
        from app.services.graph_client import move_message
        result = await move_message("fake-token", "bad-id", "dest-folder-id")

    assert result.success is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_get_inbox_stats():
    mock_response = {
        "unreadItemCount": 5,
        "totalItemCount": 42,
        "displayName": "Inbox",
    }
    with patch("app.services.graph_client._get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        from app.services.graph_client import get_inbox_stats
        result = await get_inbox_stats("fake-token")

    assert result.unread_count == 5
    assert result.total_count == 42
    assert result.folder_name == "Inbox"
