"""
Professor Synapse — persistent agent orchestration system.

Core principles:
1. Every orchestration step is checkpointed (survives crash/reboot)
2. Agent registry is file-based YAML (self-indexing, version-controllable)
3. Session = curated conversation state (not raw log)
4. Conductor routes intents to specialist agents via protocols
"""

from professor_synapse.state import Agent, SessionState, RunState, AgentProtocol
from professor_synapse.persistence import CheckpointManager
from professor_synapse.registry import AgentRegistry
from professor_synapse.conductor import route_and_serve, resume

__all__ = [
    "Agent",
    "SessionState",
    "RunState",
    "AgentProtocol",
    "CheckpointManager",
    "AgentRegistry",
    "route_and_serve",
    "resume",
]
