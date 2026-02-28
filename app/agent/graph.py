import logging

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.agent.state import AgentState
from app.agent.nodes import (
    entry_validator,
    auth_challenger,
    intent_parser,
    clarification_asker,
    email_reader,
    email_organizer,
    email_searcher,
    response_formatter,
    security_blocked,
)
from app.agent.edges import route_after_validation, route_after_intent_parse

logger = logging.getLogger(__name__)


async def create_graph(checkpointer: AsyncPostgresSaver):
    """Build and compile the email agent LangGraph StateGraph."""
    graph = StateGraph(AgentState)

    # Register all nodes
    graph.add_node("entry_validator", entry_validator)
    graph.add_node("auth_challenger", auth_challenger)
    graph.add_node("intent_parser", intent_parser)
    graph.add_node("clarification_asker", clarification_asker)
    graph.add_node("email_reader", email_reader)
    graph.add_node("email_organizer", email_organizer)
    graph.add_node("email_searcher", email_searcher)
    graph.add_node("response_formatter", response_formatter)
    graph.add_node("security_blocked", security_blocked)

    # Entry point
    graph.set_entry_point("entry_validator")

    # After validation: auth, security block, or proceed
    graph.add_conditional_edges(
        "entry_validator",
        route_after_validation,
        {
            "needs_auth": "auth_challenger",
            "injection_detected": "security_blocked",
            "valid": "intent_parser",
        },
    )

    # After intent parsing: route to appropriate action node
    graph.add_conditional_edges(
        "intent_parser",
        route_after_intent_parse,
        {
            "low_confidence": "clarification_asker",
            "read_emails": "email_reader",
            "show_unread": "email_reader",
            "organize": "email_organizer",
            "move": "email_organizer",
            "search": "email_searcher",
        },
    )

    # All action nodes feed into response formatter
    graph.add_edge("email_reader", "response_formatter")
    graph.add_edge("email_organizer", "response_formatter")
    graph.add_edge("email_searcher", "response_formatter")

    # Terminal nodes
    graph.add_edge("response_formatter", END)
    graph.add_edge("auth_challenger", END)
    graph.add_edge("clarification_asker", END)
    graph.add_edge("security_blocked", END)

    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("Email agent graph compiled successfully")
    return compiled
