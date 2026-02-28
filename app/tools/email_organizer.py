from app.services.graph_client import (
    move_message, bulk_move_messages, create_mail_folder, get_or_create_folder, mark_as_read
)
from app.schemas.email_schemas import MoveResult, BulkMoveResult, FolderInfo


async def move_email(access_token: str, message_id: str, destination_folder_id: str) -> MoveResult:
    return await move_message(access_token, message_id, destination_folder_id)


async def bulk_move(access_token: str, message_ids: list[str], destination_folder_id: str) -> BulkMoveResult:
    return await bulk_move_messages(access_token, message_ids, destination_folder_id)


async def create_folder(access_token: str, folder_name: str) -> FolderInfo:
    return await create_mail_folder(access_token, folder_name)


async def get_or_create_email_folder(access_token: str, folder_name: str) -> FolderInfo:
    return await get_or_create_folder(access_token, folder_name)


async def mark_email_read(access_token: str, message_id: str) -> bool:
    return await mark_as_read(access_token, message_id)
