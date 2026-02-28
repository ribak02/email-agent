from app.services.graph_client import search_messages, filter_by_sender, list_inbox_messages
from app.schemas.email_schemas import EmailMetadata


async def search_emails(access_token: str, query: str, top: int = 10) -> list[EmailMetadata]:
    return await search_messages(access_token, query, top=top)


async def filter_emails_by_sender(access_token: str, sender_email: str, top: int = 20) -> list[EmailMetadata]:
    return await filter_by_sender(access_token, sender_email, top=top)


async def filter_unread(access_token: str, top: int = 20) -> list[EmailMetadata]:
    return await list_inbox_messages(access_token, top=top, unread_only=True)
