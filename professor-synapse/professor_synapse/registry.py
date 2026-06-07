"""
Registry — file-based agent catalog with auto-indexing.

Each .yaml file in the agents directory defines one or more agents.
The registry auto-indexes on load, building an in-memory map keyed
by agent name. Registry state is also checkpointed (hash + list)
so the conductor can verify consistency at recovery time.

File format:
  agents/
    examples.yaml:
      agents:
        - name: cyber-analyzer
          description: "Deep analysis of cybersecurity incidents"
          protocol: security
          role: "Security Analyst"
          backstory: "..."
          traits: ["analytical", "precise"]
          tags: ["security", "analysis"]
"""

from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from professor_synapse.state import Agent, AgentProtocol


class AgentRegistry:
    """
    File-based agent registry.

    Agents are defined in YAML files under the `agents_dir`.
    Auto-indexes on every call to `reload()`.

    Thread-safe for reads; writes go through file operations.
    """

    def __init__(self, agents_dir: str | Path) -> None:
        self.agents_dir = Path(agents_dir).expanduser().resolve()
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self._agents: Dict[str, Agent] = {}
        self._hash: str = ""
        self._reload()

    # ── Indexing ────────────────────────────────────────────

    def _reload(self) -> None:
        """Scan agents_dir and rebuild internal index."""
        new_agents: Dict[str, Agent] = {}
        blob_parts: list[str] = []

        for yaml_path in sorted(self.agents_dir.glob("*.yaml")):
            raw = yaml_path.read_text(encoding="utf-8")
            blob_parts.append(raw)
            data = yaml.safe_load(raw)
            if not data or "agents" not in data:
                continue
            for entry in data["agents"]:
                agent = Agent.from_dict(entry)
                new_agents[agent.name] = agent

        self._agents = new_agents
        # Compute content hash over all raw YAML
        combined = "\n".join(blob_parts)
        self._hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16]

    # ── Queries ──────────────────────────────────────────────

    @property
    def hash(self) -> str:
        return self._hash

    def get(self, name: str) -> Optional[Agent]:
        return self._agents.get(name)

    def all(self) -> List[Agent]:
        return list(self._agents.values())

    def find_by_protocol(self, protocol: AgentProtocol) -> List[Agent]:
        return [a for a in self._agents.values() if a.protocol == protocol and a.enabled]

    def find_by_tag(self, tag: str) -> List[Agent]:
        return [a for a in self._agents.values() if tag in a.tags and a.enabled]

    def enabled(self) -> List[Agent]:
        return [a for a in self._agents.values() if a.enabled]

    def names(self) -> List[str]:
        return sorted(self._agents.keys())

    # ── Mutations (file-backed) ─────────────────────────────

    def add_agent(self, agent: Agent) -> None:
        """
        Add or update an agent in the default agents file.

        Loads -> modifies -> saves -> reloads.
        """
        default_file = self.agents_dir / "custom_agents.yaml"
        data: dict = {"agents": []}
        if default_file.exists():
            data = yaml.safe_load(default_file.read_text("utf-8")) or {"agents": []}

        # Update in-place (match by name) or append
        replaced = False
        for i, existing in enumerate(data["agents"]):
            if existing.get("name") == agent.name:
                data["agents"][i] = agent.to_dict()
                replaced = True
                break
        if not replaced:
            data["agents"].append(agent.to_dict())

        default_file.write_text(
            yaml.dump(data, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
        self._reload()

    def remove_agent(self, name: str) -> bool:
        """
        Remove an agent by name. Scans all YAML files.
        Returns True if found and removed.
        """
        found = False
        for yaml_path in list(self.agents_dir.glob("*.yaml")):
            data = yaml.safe_load(yaml_path.read_text("utf-8")) or {"agents": []}
            original_count = len(data.get("agents", []))
            data["agents"] = [e for e in data.get("agents", []) if e.get("name") != name]
            if len(data["agents"]) < original_count:
                found = True
                yaml_path.write_text(
                    yaml.dump(data, default_flow_style=False, allow_unicode=True),
                    encoding="utf-8",
                )
        if found:
            self._reload()
        return found

    # ── Serialization ─────────────────────────────────────────

    def to_dict(self) -> dict:
        """For checkpointing registry state."""
        return {
            "hash": self._hash,
            "agent_names": list(self._agents.keys()),
            "enabled_count": len(self.enabled()),
        }

    @classmethod
    def from_dict(cls, data: dict) -> dict:
        """Reconstruct registry config from checkpoint data (for diff)."""
        return data
