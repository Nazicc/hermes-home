"""
Conductor — intent router and orchestration engine.

The Conductor is the "Professor" in Professor Synapse. It:
  1. Receives user input and current session state
  2. Matches intent to a specialist agent (by protocol, tags, or name)
  3. Dispatches to the agent's protocol handler
  4. Updates session state with results
  5. Checkpoints after every step → crash-safe

Design principle: the conductor is stateless.
All state lives in the Session.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from professor_synapse.state import Agent, AgentProtocol, RunState, SessionState
from professor_synapse.registry import AgentRegistry
from professor_synapse.session import Session
from professor_synapse.protocols import convener_handle, agent_template_handle


# ── Protocol dispatch table ──────────────────────────────────

_PROTOCOL_HANDLERS = {
    AgentProtocol.CONVENER: convener_handle,
    AgentProtocol.AGENT_TEMPLATE: agent_template_handle,
}


def _get_handler(protocol: AgentProtocol):
    """Resolve protocol to handler function. Falls back to convener."""
    return _PROTOCOL_HANDLERS.get(protocol, convener_handle)


# ── Intent matching ──────────────────────────────────────────

def _match_agent(
    user_input: str,
    registry: AgentRegistry,
) -> Optional[Agent]:
    """
    Match user input to the best specialist agent.

    Matching strategy (tiered):
      1. Exact name match in input (e.g. "ask cyber-analyzer ...")
      2. Tag match: input contains a known tag
      3. Protocol keyword match: "update..." → UPDATE, "create agent..." → AGENT_TEMPLATE
      4. Fallback to convener
    """
    lower = user_input.lower()

    # Tier 1: explicit agent name
    for agent in registry.enabled():
        if agent.name.lower() in lower:
            return agent

    # Tier 2: tag keywords
    for agent in registry.enabled():
        for tag in agent.tags:
            if tag.lower() in lower:
                return agent

    # Tier 3: protocol keyword match
    protocol_keywords: Dict[AgentProtocol, List[str]] = {
        AgentProtocol.UPDATE: ["update", "变更", "更新", "修改"],
        AgentProtocol.AGENT_TEMPLATE: ["create agent", "new agent", "define agent",
                                       "创建 agent", "新建 agent"],
        AgentProtocol.CODE: ["code", "代码", "python", "写代码", "编写"],
        AgentProtocol.SECURITY: ["security", "安全", "漏洞", "vuln", "cve"],
        AgentProtocol.RESEARCH: ["research", "研究", "调查", "analyze", "分析"],
    }

    matched_protocol = None
    for protocol, keywords in protocol_keywords.items():
        for kw in keywords:
            if kw in lower:
                matched_protocol = protocol
                break
        if matched_protocol:
            break

    if matched_protocol:
        agents = registry.find_by_protocol(matched_protocol)
        if agents:
            return agents[0]

    # Tier 4: default — any convener agent, or first enabled agent
    conveners = registry.find_by_protocol(AgentProtocol.CONVENER)
    if conveners:
        return conveners[0]
    enabled = registry.enabled()
    if enabled:
        return enabled[0]

    return None


# ── Main conductor logic ─────────────────────────────────────

def route_and_serve(
    user_input: str,
    session: Session,
    registry: AgentRegistry,
) -> Dict[str, Any]:
    """
    Route user input to the right agent and return the response.

    This is the primary entry point. It:
      - Matches intent to agent
      - Dispatches protocol handler
      - Updates and checkpoints session
      - Returns structured result

    If serving crashes mid-flight, the session checkpoint is
    at the state BEFORE this call (completed step),
    so replay is safe.
    """
    state = session.state
    agent = _match_agent(user_input, registry)

    if agent is None:
        return {
            "response": "没有找到匹配的 Agent。请先创建或启用至少一个 Agent。",
            "agent": None,
            "session_id": session.session_id,
        }

    # Update session metadata
    state.session.active_agent = agent.name
    state.session.intent = user_input[:200]
    state.agent_registry_hash = registry.hash

    # Dispatch to protocol handler
    handler = _get_handler(agent.protocol)
    result = handler(
        agent=agent,
        user_input=user_input,
        session_summary=state.session.curated_summary,
        context={"session_id": session.session_id, "turn": state.session.turn_count},
    )

    # Update session summary (append, trimmed to 2000 chars)
    snippet = result.get("response", "")[:200]
    if state.session.curated_summary:
        state.session.curated_summary += f"\n→ [{agent.name}]: {snippet}"
        if len(state.session.curated_summary) > 2000:
            # Keep only last 1500 chars
            state.session.curated_summary = "..." + state.session.curated_summary[-1500:]
    else:
        state.session.curated_summary = f"[{agent.name}]: {snippet}"

    # Store routing result
    state.routing_result = {
        "agent": agent.name,
        "protocol": agent.protocol.value,
        "handler_result": result,
    }

    # Checkpoint
    session.save()

    return {
        "response": result.get("response", ""),
        "agent": agent.name,
        "session_id": session.session_id,
    }


def resume(session: Session, registry: AgentRegistry) -> Dict[str, Any]:
    """
    Resume an incomplete session after crash/reboot.

    Re-validates the registry hash and returns the last routing
    result so the caller can proceed.
    """
    state = session.state

    # Detect hash mismatch (registry changed since checkpoint)
    if state.agent_registry_hash and state.agent_registry_hash != registry.hash:
        return {
            "response": (
                f"⚠️ Agent 注册表已变更 (hash: {state.agent_registry_hash[:8]} → "
                f"{registry.hash[:8]})。请确认后继续。"
            ),
            "agent": state.session.active_agent,
            "session_id": session.session_id,
            "registry_changed": True,
        }

    return {
        "response": (
            f"🔄 会话恢复完成。阶段: {state.phase}, "
            f"当前 Agent: {state.session.active_agent or '无'}, "
            f"已对话 {state.session.turn_count} 轮"
        ),
        "agent": state.session.active_agent,
        "session_id": session.session_id,
        "registry_changed": False,
    }
