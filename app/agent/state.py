from typing import Annotated, Optional, Sequence
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    # Conversation history (LangGraph manages append semantics)
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # Input
    phone_number: str
    user_message: str

    # Intent parsing output
    intent: Optional[str]
    intent_confidence: Optional[float]
    intent_params: Optional[dict]

    # Email operation results
    email_results: Optional[list]    # list of EmailMetadata dicts
    action_taken: Optional[str]      # human-readable description
    folders_available: Optional[list]

    # Auth
    ms_access_token: Optional[str]
    needs_auth: bool

    # Response
    response_text: Optional[str]
    needs_clarification: bool
    clarification_question: Optional[str]

    # Security
    injection_detected: bool
