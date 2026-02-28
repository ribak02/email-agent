from app.agent.state import AgentState


def route_after_validation(state: AgentState) -> str:
    """Route based on auth status and security checks."""
    if state.get("injection_detected"):
        return "injection_detected"
    if state.get("needs_auth"):
        return "needs_auth"
    return "valid"


def route_after_intent_parse(state: AgentState) -> str:
    """Route to the appropriate action node based on parsed intent."""
    if state.get("needs_clarification"):
        return "low_confidence"

    intent = state.get("intent", "unknown")
    mapping = {
        "read_emails": "read_emails",
        "show_unread": "show_unread",
        "organize_inbox": "organize",
        "move_email": "move",
        "search_emails": "search",
        "create_folder": "organize",
        "unknown": "low_confidence",
    }
    return mapping.get(intent, "low_confidence")
