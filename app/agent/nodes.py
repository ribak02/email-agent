import json
import logging
from langchain_core.messages import HumanMessage

from app.agent.state import AgentState
from app.security.sanitizer import check_injection
from app.schemas.intent_schemas import intent_agent, organize_agent, response_agent

logger = logging.getLogger(__name__)


async def entry_validator(state: AgentState) -> dict:
    """Check auth status and screen for prompt injection."""
    updates: dict = {}

    # Check Microsoft token
    updates["needs_auth"] = not bool(state.get("ms_access_token"))

    # Screen user message for injection
    msg = state.get("user_message", "")
    suspicious, pattern = check_injection(msg)
    updates["injection_detected"] = suspicious
    if suspicious:
        logger.warning("Injection attempt in user message. Pattern: %s", pattern)

    # Add to conversation history
    updates["messages"] = [HumanMessage(content=msg)]

    return updates


async def auth_challenger(state: AgentState) -> dict:
    """Respond with Microsoft OAuth instructions."""
    # The actual device flow is initiated in main.py before invoking graph
    # This node just returns the appropriate message
    return {
        "response_text": (
            "To connect your Outlook account, I need you to authorize access.\n\n"
            "Please visit: https://microsoft.com/devicelogin\n"
            "Then message me again once you've completed the login."
        )
    }


async def intent_parser(state: AgentState) -> dict:
    """Parse user message into structured intent using PydanticAI."""
    user_msg = state.get("user_message", "")
    result = await intent_agent.run(user_msg)
    intent_data = result.data

    params = {}
    if intent_data.target_folder:
        params["target_folder"] = intent_data.target_folder
    if intent_data.search_query:
        params["search_query"] = intent_data.search_query
    if intent_data.sender_filter:
        params["sender_filter"] = intent_data.sender_filter

    return {
        "intent": intent_data.intent,
        "intent_confidence": intent_data.confidence,
        "intent_params": params,
        "needs_clarification": intent_data.needs_clarification,
        "clarification_question": intent_data.clarification_question,
    }


async def clarification_asker(state: AgentState) -> dict:
    """Ask the user for clarification."""
    question = state.get("clarification_question") or "Could you clarify what you'd like me to do with your emails?"
    return {"response_text": question}


async def email_reader(state: AgentState) -> dict:
    """Read inbox or unread emails from Microsoft Graph."""
    from app.tools.email_reader import list_inbox, get_unread_summary, list_folders

    token = state.get("ms_access_token", "")
    intent = state.get("intent", "read_emails")

    try:
        if intent == "show_unread":
            summary = await get_unread_summary(token)
            unread_emails = []
            if summary.unread_count > 0:
                from app.tools.email_search import filter_unread
                unread_emails = await filter_unread(token, top=10)

            email_dicts = [e.model_dump(mode="json") for e in unread_emails]
            action = f"Found {summary.unread_count} unread emails out of {summary.total_count} total in {summary.folder_name}."
            return {"email_results": email_dicts, "action_taken": action}
        else:
            emails = await list_inbox(token, top=15)
            email_dicts = [e.model_dump(mode="json") for e in emails]
            action = f"Retrieved {len(emails)} recent emails from inbox."
            return {"email_results": email_dicts, "action_taken": action}
    except Exception as e:
        logger.error("email_reader error: %s", e)
        return {"email_results": [], "action_taken": f"Error reading emails: {str(e)[:100]}"}


async def email_organizer(state: AgentState) -> dict:
    """Organize emails by moving them to appropriate folders."""
    from app.tools.email_reader import list_inbox
    from app.tools.email_organizer import bulk_move, get_or_create_email_folder

    token = state.get("ms_access_token", "")
    params = state.get("intent_params", {})
    target_folder_name = params.get("target_folder", "")

    try:
        # Get recent inbox emails (metadata only - no body)
        emails = await list_inbox(token, top=50)
        if not emails:
            return {"email_results": [], "action_taken": "No emails found in inbox to organize."}

        # Build prompt for organize_agent with SANITIZED metadata only
        email_summaries = []
        for e in emails:
            email_summaries.append(
                f"ID:{e.message_id[:8]}... | From:{e.sender_email} | Subject:{e.subject} | "
                f"Date:{e.received_at.strftime('%Y-%m-%d')} | Read:{e.is_read}"
            )

        prompt = (
            f"Target folder: '{target_folder_name or 'Auto-organize'}'\n\n"
            f"Email metadata to analyze (NO body content, only headers):\n"
            + "\n".join(email_summaries[:20])  # Limit to 20 for context
        )

        result = await organize_agent.run(prompt)
        organize_data = result.data

        if organize_data.injection_detected:
            logger.warning("Injection detected during organize analysis")
            return {"email_results": [], "action_taken": "Skipped some emails due to suspicious content."}

        if organize_data.action == "skip" or not organize_data.matching_message_ids:
            return {"email_results": [], "action_taken": f"No emails matched criteria for folder '{organize_data.folder_name}'."}

        # Get or create the target folder
        folder = await get_or_create_email_folder(token, organize_data.folder_name)

        # Map short IDs back to full IDs
        full_ids = []
        for short_id in organize_data.matching_message_ids:
            for e in emails:
                if e.message_id.startswith(short_id.rstrip("...")):
                    full_ids.append(e.message_id)
                    break

        if not full_ids:
            # Fallback: use all matching emails if ID mapping fails
            full_ids = [e.message_id for e in emails if e.message_id in organize_data.matching_message_ids]

        # Move matched emails
        move_result = await bulk_move(token, full_ids, folder.folder_id)
        action = (
            f"Moved {move_result.succeeded} of {move_result.total} emails to '{folder.name}'. "
            f"Reason: {organize_data.reason}"
        )
        return {"email_results": [e.model_dump(mode="json") for e in emails[:5]], "action_taken": action}

    except Exception as e:
        logger.error("email_organizer error: %s", e)
        return {"email_results": [], "action_taken": f"Error organizing emails: {str(e)[:100]}"}


async def email_searcher(state: AgentState) -> dict:
    """Search emails by query or sender."""
    from app.tools.email_search import search_emails, filter_emails_by_sender

    token = state.get("ms_access_token", "")
    params = state.get("intent_params", {})
    query = params.get("search_query", "")
    sender = params.get("sender_filter", "")

    try:
        if sender:
            emails = await filter_emails_by_sender(token, sender, top=10)
            action = f"Found {len(emails)} emails from {sender}."
        elif query:
            emails = await search_emails(token, query, top=10)
            action = f"Found {len(emails)} emails matching '{query}'."
        else:
            emails = []
            action = "No search criteria provided."

        return {"email_results": [e.model_dump(mode="json") for e in emails], "action_taken": action}
    except Exception as e:
        logger.error("email_searcher error: %s", e)
        return {"email_results": [], "action_taken": f"Error searching emails: {str(e)[:100]}"}


async def response_formatter(state: AgentState) -> dict:
    """Format a friendly WhatsApp response summarizing the action taken."""
    action_taken = state.get("action_taken", "")
    email_results = state.get("email_results", [])

    # Build a brief summary for the LLM to format
    summary_parts = []
    if action_taken:
        summary_parts.append(f"Action: {action_taken}")

    if email_results:
        summary_parts.append(f"\nEmails ({min(len(email_results), 5)} shown):")
        for e in email_results[:5]:
            if isinstance(e, dict):
                subject = e.get("subject", "(no subject)")
                sender = e.get("sender_email", "")
                is_read = "read" if e.get("is_read") else "unread"
                summary_parts.append(f"  [{is_read}] {subject} -- from {sender}")

    prompt = "\n".join(summary_parts) if summary_parts else "No action was taken."

    try:
        result = await response_agent.run(prompt)
        return {"response_text": result.data.message}
    except Exception as e:
        logger.error("response_formatter error: %s", e)
        # Fallback: return the raw action taken
        return {"response_text": action_taken or "Done! Your request has been processed."}


async def security_blocked(state: AgentState) -> dict:
    """Return a safe static response when injection is detected."""
    return {
        "response_text": (
            "I detected unusual content in your request and couldn't process it safely. "
            "Please rephrase your message and try again."
        )
    }
