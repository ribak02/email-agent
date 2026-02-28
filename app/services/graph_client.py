import logging
from datetime import datetime

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from app.schemas.email_schemas import (
    EmailMetadata, FolderInfo, UnreadSummary, MoveResult, BulkMoveResult
)
from app.security.sanitizer import screen_metadata

logger = logging.getLogger(__name__)

BASE_URL = "https://graph.microsoft.com/v1.0"
# SECURITY: body fields are explicitly excluded
MESSAGE_SELECT = "id,subject,from,receivedDateTime,isRead,importance,parentFolderId"
FOLDER_SELECT = "id,displayName,unreadItemCount,totalItemCount,parentFolderId"


def _auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 503, 504)
    return isinstance(exc, httpx.TimeoutException)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10),
       retry=retry_if_exception(_is_retryable), reraise=True)
async def _get(url: str, access_token: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=_auth_headers(access_token), params=params)
        resp.raise_for_status()
        return resp.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10),
       retry=retry_if_exception(_is_retryable), reraise=True)
async def _post(url: str, access_token: str, json_body: dict) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=_auth_headers(access_token), json=json_body)
        resp.raise_for_status()
        return resp.json()


def _parse_email(msg: dict) -> EmailMetadata:
    sender = msg.get("from", {}).get("emailAddress", {})
    m = EmailMetadata(
        message_id=msg["id"],
        subject=msg.get("subject", "(no subject)"),
        sender_email=sender.get("address", ""),
        sender_name=sender.get("name", ""),
        received_at=datetime.fromisoformat(msg["receivedDateTime"].replace("Z", "+00:00")),
        is_read=msg.get("isRead", False),
        folder_id=msg.get("parentFolderId", ""),
        importance=msg.get("importance", "normal"),
    )
    return screen_metadata(m)


def _parse_folder(f: dict) -> FolderInfo:
    return FolderInfo(
        folder_id=f["id"],
        name=f["displayName"],
        unread_count=f.get("unreadItemCount", 0),
        total_count=f.get("totalItemCount", 0),
        parent_folder_id=f.get("parentFolderId"),
    )


async def list_inbox_messages(access_token: str, top: int = 20, unread_only: bool = False) -> list[EmailMetadata]:
    url = f"{BASE_URL}/me/mailFolders/inbox/messages"
    params = {"$select": MESSAGE_SELECT, "$top": top, "$orderby": "receivedDateTime desc"}
    if unread_only:
        params["$filter"] = "isRead eq false"
    data = await _get(url, access_token, params)
    return [_parse_email(m) for m in data.get("value", [])]


async def get_mail_folders(access_token: str) -> list[FolderInfo]:
    url = f"{BASE_URL}/me/mailFolders"
    data = await _get(url, access_token, {"$select": FOLDER_SELECT, "$top": 50})
    return [_parse_folder(f) for f in data.get("value", [])]


async def get_folder_by_name(access_token: str, folder_name: str) -> FolderInfo | None:
    folders = await get_mail_folders(access_token)
    name_lower = folder_name.lower()
    for f in folders:
        if f.name.lower() == name_lower:
            return f
    return None


async def create_mail_folder(access_token: str, folder_name: str) -> FolderInfo:
    url = f"{BASE_URL}/me/mailFolders"
    data = await _post(url, access_token, {"displayName": folder_name})
    return _parse_folder(data)


async def get_or_create_folder(access_token: str, folder_name: str) -> FolderInfo:
    existing = await get_folder_by_name(access_token, folder_name)
    if existing:
        return existing
    return await create_mail_folder(access_token, folder_name)


async def move_message(access_token: str, message_id: str, destination_folder_id: str) -> MoveResult:
    url = f"{BASE_URL}/me/messages/{message_id}/move"
    try:
        await _post(url, access_token, {"destinationId": destination_folder_id})
        return MoveResult(message_id=message_id, success=True, destination_folder_id=destination_folder_id)
    except Exception as e:
        logger.error("Failed to move message %s: %s", message_id, e)
        return MoveResult(message_id=message_id, success=False, destination_folder_id=destination_folder_id, error=str(e))


async def bulk_move_messages(access_token: str, message_ids: list[str], destination_folder_id: str) -> BulkMoveResult:
    results = []
    for msg_id in message_ids:
        result = await move_message(access_token, msg_id, destination_folder_id)
        results.append(result)
    succeeded = sum(1 for r in results if r.success)
    return BulkMoveResult(total=len(results), succeeded=succeeded, failed=len(results) - succeeded, results=results)


async def search_messages(access_token: str, query: str, top: int = 10) -> list[EmailMetadata]:
    url = f"{BASE_URL}/me/messages"
    params = {"$search": f'"{query}"', "$select": MESSAGE_SELECT, "$top": top}
    data = await _get(url, access_token, params)
    return [_parse_email(m) for m in data.get("value", [])]


async def filter_by_sender(access_token: str, sender_email: str, top: int = 20) -> list[EmailMetadata]:
    url = f"{BASE_URL}/me/messages"
    params = {
        "$filter": f"from/emailAddress/address eq '{sender_email}'",
        "$select": MESSAGE_SELECT,
        "$top": top,
        "$orderby": "receivedDateTime desc",
    }
    data = await _get(url, access_token, params)
    return [_parse_email(m) for m in data.get("value", [])]


async def get_inbox_stats(access_token: str) -> UnreadSummary:
    url = f"{BASE_URL}/me/mailFolders/inbox"
    data = await _get(url, access_token, {"$select": "unreadItemCount,totalItemCount,displayName"})
    return UnreadSummary(
        unread_count=data.get("unreadItemCount", 0),
        total_count=data.get("totalItemCount", 0),
        folder_name=data.get("displayName", "Inbox"),
    )


async def mark_as_read(access_token: str, message_id: str) -> bool:
    url = f"{BASE_URL}/me/messages/{message_id}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.patch(url, headers=_auth_headers(access_token), json={"isRead": True})
        return resp.status_code == 200
