"""
Update protocol — knowledge update and session maintenance.

Handles user requests to update curated summaries, add knowledge
references, or modify session metadata.
"""

from typing import Any, Dict, Optional

from professor_synapse.state import Agent


def handle(
    agent: Agent,
    user_input: str,
    session_summary: str = "",
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Process an update/maintenance request.

    Can handle:
      - "update summary: ..."
      - "add knowledge ref: ..."
      - "set intent: ..."
    """
    update_type = "general"
    new_summary = None

    lower = user_input.lower()
    if "summary" in lower or "摘要" in user_input:
        update_type = "summary"
        # Extract content after "summary:" or "摘要:"
        for sep in ["summary:", "摘要:", "update:"]:
            if sep in lower or sep in user_input:
                _, _, after = user_input.partition(sep)
                if after.strip():
                    new_summary = after.strip()
                    break
    elif "intent" in lower or "意图" in user_input:
        update_type = "intent"
    elif "knowledge" in lower or "knowledge ref" in lower:
        update_type = "knowledge"

    return {
        "response": f"[{agent.name}] 更新类型: {update_type}",
        "routing_hint": None,
        "metadata": {
            "update_type": update_type,
            "new_summary_snippet": (new_summary[:100] if new_summary else None),
        },
    }
