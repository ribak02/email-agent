from app.services.graph_client import list_inbox_messages, get_inbox_stats, get_mail_folders, filter_by_sender
from app.schemas.email_schemas import EmailMetadata, UnreadSummary, FolderInfo


async def list_inbox(access_token: str, top: int = 20) -> list[EmailMetadata]:
    return await list_inbox_messages(access_token, top=top)


async def get_unread_summary(access_token: str) -> UnreadSummary:
    return await get_inbox_stats(access_token)


async def list_folders(access_token: str) -> list[FolderInfo]:
    return await get_mail_folders(access_token)


async def get_recent_from_sender(access_token: str, sender_email: str, top: int = 10) -> list[EmailMetadata]:
    return await filter_by_sender(access_token, sender_email, top=top)
