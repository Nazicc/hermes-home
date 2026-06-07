"""
State — pure data classes for the Professor Synapse system.

Zero dependencies beyond stdlib. All state is JSON-serializable
for crash-safe checkpointing. No business logic lives here.
"""

from __future__ import annotations
import enum
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


class AgentProtocol(enum.Enum):
    """Protocols a specialist agent can declare."""
    CONVENER = "convener"          # General-purpose helper
    AGENT_TEMPLATE = "agent_template"  # Agent template definition
    UPDATE = "update"              # Knowledge update
    RESEARCH = "research"          # Deep research
    CODE = "code"                  # Code generation / review
    SECURITY = "security"          # Security analysis
    WORKFLOW = "workflow"          # Multi-step workflow
    CUSTOM = "custom"              # User-defined protocol

    @classmethod
    def from_str(cls, value: str) -> AgentProtocol:
        for member in cls:
            if member.value == value.lower():
                return member
        return cls.CUSTOM


@dataclass
class Agent:
    """
    A specialist agent definition.

    All data is YAML-serializable for file-based registry,
    and JSON-serializable for runtime checkpointing.
    """
    name: str
    description: str
    protocol: AgentProtocol = AgentProtocol.CUSTOM
    role: str = ""
    backstory: str = ""
    traits: List[str] = field(default_factory=list)
    response_hints: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    knowledge_refs: List[str] = field(default_factory=list)  # gbrain page slugs
    enabled: bool = True

    # Metadata (auto-filled)
    uid: str = field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["protocol"] = self.protocol.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Agent:
        data = dict(data)
        if isinstance(data.get("protocol"), str):
            data["protocol"] = AgentProtocol.from_str(data["protocol"])
        return cls(**data)


@dataclass
class SessionMessage:
    """A single message in a session transcript."""
    role: str  # "user", "assistant", "system", "agent:name"
    content: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionState:
    """
    Curated conversation state — NOT a raw log.

    Contains only what's needed for the conductor to make routing decisions
    and for agents to maintain context across turns.
    """
    session_id: str
    created_at: str
    intent: str = ""                 # Current intent being processed
    active_agent: Optional[str] = None  # Which agent is currently serving
    curated_summary: str = ""        # Compressed context (replaces raw history)
    turn_count: int = 0
    last_active: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def advance_turn(self) -> None:
        self.turn_count += 1
        self.last_active = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SessionState:
        return cls(**data)

    @classmethod
    def create(cls, intent: str = "") -> SessionState:
        now = datetime.now(timezone.utc).isoformat()
        return cls(
            session_id=uuid4().hex[:12],
            created_at=now,
            intent=intent,
            curated_summary="",
            turn_count=0,
        )


@dataclass
class RunState:
    """
    Full system state at a point in time.

    This is what gets checkpointed. Every orchestration step
    produces a new RunState, leaving the previous one untouched
    (immutable lineage for full crash recovery).
    """
    phase: str = "init"              # Current phase name
    session: SessionState = field(default_factory=SessionState.create)
    agent_registry_hash: str = ""    # Fingerprint of registry at this point
    routing_result: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    completed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "session": self.session.to_dict(),
            "agent_registry_hash": self.agent_registry_hash,
            "routing_result": self.routing_result,
            "metadata": self.metadata,
            "error": self.error,
            "completed": self.completed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RunState:
        state = cls(
            phase=data.get("phase", "init"),
            session=SessionState.from_dict(data["session"]),
            agent_registry_hash=data.get("agent_registry_hash", ""),
            routing_result=data.get("routing_result", {}),
            metadata=data.get("metadata", {}),
            error=data.get("error"),
            completed=data.get("completed", False),
        )
        return state

    def as_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> RunState:
        return cls.from_dict(json.loads(raw))
