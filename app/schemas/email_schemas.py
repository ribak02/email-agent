from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class EmailMetadata(BaseModel):
    """Sanitized email metadata. Body is NEVER included."""
    message_id: str
    subject: str = Field(max_length=200)
    sender_email: str
    sender_name: str = Field(max_length=100)
    received_at: datetime
    is_read: bool
    folder_id: str
    parent_folder_name: Optional[str] = None
    importance: str = "normal"


class FolderInfo(BaseModel):
    folder_id: str
    name: str
    unread_count: int = 0
    total_count: int = 0
    parent_folder_id: Optional[str] = None


class UnreadSummary(BaseModel):
    unread_count: int
    total_count: int
    folder_name: str


class MoveResult(BaseModel):
    message_id: str
    success: bool
    destination_folder_id: str
    error: Optional[str] = None


class BulkMoveResult(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: list[MoveResult]
