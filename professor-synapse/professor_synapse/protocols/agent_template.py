"""
Agent Template protocol — generates new agent definitions.

When a user needs a new specialist agent, this protocol creates
the YAML definition and registers it in the registry.
"""

from typing import Any, Dict, Optional

from professor_synapse.state import Agent, AgentProtocol


def handle(
    agent: Agent,
    user_input: str,
    session_summary: str = "",
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate a new agent definition from a natural language description.

    Returns a draft Agent definition that the user can accept/modify.
    """
    # Extract name hints from input
    words = user_input.lower().split()
    hint_name = "custom-agent"
    for word in words:
        if word.startswith("agent-") or word.startswith("ai-"):
            hint_name = word
            break

    draft = Agent(
        name=hint_name,
        description=f"Auto-generated from: {user_input[:120]}",
        protocol=AgentProtocol.CUSTOM,
        role="Specialist assistant",
        backstory=f"Dedicated to handling: {user_input[:200]}",
        tags=hint_name.split("-"),
    )

    return {
        "response": f"已生成 Agent 定义草稿: **{draft.name}** ({draft.protocol.value})",
        "routing_hint": None,
        "metadata": {
            "draft_agent": draft.to_dict(),
            "agent": agent.name,
            "protocol": "agent_template",
        },
    }
