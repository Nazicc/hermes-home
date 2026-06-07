"""
Convener protocol — general-purpose assistant, planner, and router.

The default protocol for agents that handle open-ended requests,
orchestrate multi-step tasks, or triage incoming intents.

When no specialist agent matches the intent, the Convener handles it
directly or breaks it into sub-intents.
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
    Process input through a Convener-protocol agent.

    Args:
        agent: The agent definition
        user_input: Raw user message
        session_summary: Curated session context
        context: Additional runtime context

    Returns:
        dict with keys:
          - response: str  — the agent's output
          - routing_hint: str | None — if this should route elsewhere
          - metadata: dict — any extra info
    """
    # In a real deployment, this would call the LLM with the agent's
    # role/backstory as system prompt. Here we return the structured
    # frame that the Conductor uses.
    return {
        "response": (
            f"[{agent.name}] 收到输入，长度 {len(user_input)} 字符。"
            f"当前会话摘要: {session_summary[:100] if session_summary else '无'}"
        ),
        "routing_hint": None,
        "metadata": {
            "agent": agent.name,
            "protocol": "convener",
            "input_len": len(user_input),
        },
    }
