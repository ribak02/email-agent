from pydantic import BaseModel, Field
from typing import Literal, Optional
from pydantic_ai import Agent

from app.agent.prompts import INTENT_SYSTEM_PROMPT, EMAIL_ANALYSIS_SYSTEM_PROMPT


class IntentResult(BaseModel):
    intent: Literal[
        "read_emails", "show_unread", "organize_inbox",
        "move_email", "search_emails", "create_folder", "unknown"
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    target_folder: Optional[str] = Field(None, max_length=100)
    search_query: Optional[str] = Field(None, max_length=200)
    sender_filter: Optional[str] = Field(None, max_length=200)
    needs_clarification: bool = False
    clarification_question: Optional[str] = Field(None, max_length=500)


class OrganizeResult(BaseModel):
    folder_name: str = Field(max_length=100)
    matching_message_ids: list[str] = Field(default_factory=list)
    emails_to_move_count: int = 0
    action: Literal["move", "skip", "create_then_move"]
    reason: str = Field(max_length=300)
    injection_detected: bool = False


class FormattedResponse(BaseModel):
    message: str = Field(max_length=4096)
    action_summary: Optional[str] = None


# PydanticAI agents - these make structured calls to OpenAI
intent_agent = Agent(
    "openai:gpt-4o",
    result_type=IntentResult,
    system_prompt=INTENT_SYSTEM_PROMPT,
)

organize_agent = Agent(
    "openai:gpt-4o",
    result_type=OrganizeResult,
    system_prompt=EMAIL_ANALYSIS_SYSTEM_PROMPT,
)

response_agent = Agent(
    "openai:gpt-4o",
    result_type=FormattedResponse,
    system_prompt=(
        "Format a clear, friendly WhatsApp reply summarizing what was done. "
        "Keep under 4000 characters. Use plain text (no markdown). "
        "Be concise but informative."
    ),
)
