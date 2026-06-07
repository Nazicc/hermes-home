"""
CLI — command-line entry point for Professor Synapse.

Usage:
    prof-synapse session create --intent "分析威胁情报"
    prof-synapse session list
    prof-synapse session show <session_id>
    prof-synapse session resume <session_id>
    prof-synapse agent list
    prof-synapse agent add --name cyber-analyzer --protocol security ...
    prof-synapse agent remove <name>
    prof-synapse serve --input "最新漏洞 CVE-2024-..."
"""

from __future__ import annotations
import sys
from pathlib import Path

import click

from professor_synapse.session import Session
from professor_synapse.registry import AgentRegistry
from professor_synapse.conductor import route_and_serve, resume
from professor_synapse.state import Agent, AgentProtocol

DEFAULT_BASE = Path("~/.hermes/professor-synapse").expanduser()
DEFAULT_AGENTS = DEFAULT_BASE / "agents"


# ── Shared options ───────────────────────────────────────────

def _registry(ctx=None) -> AgentRegistry:
    agents_dir = Path(
        (ctx.params.get("agents_dir") if ctx else None) or DEFAULT_AGENTS
    )
    return AgentRegistry(agents_dir)


def _session(base_dir: str | None = None, session_id: str | None = None, intent: str = "") -> Session:
    bd = Path(base_dir) if base_dir else DEFAULT_BASE
    return Session.load_or_create(bd, session_id=session_id, intent=intent)


# ── CLI ──────────────────────────────────────────────────────

@click.group()
def cli():
    """Professor Synapse — persistent agent orchestration."""
    pass


# ── session ──────────────────────────────────────────────────

@cli.group()
def session():
    """Manage orchestration sessions."""
    pass


@session.command("create")
@click.option("--intent", default="", help="Session intent description")
@click.option("--base-dir", default=None, help="Checkpoint base directory")
def session_create(intent: str, base_dir: str | None):
    """Create a new session."""
    sess = _session(base_dir=base_dir, intent=intent)
    click.echo(f"✅ 会话已创建: {sess.session_id}")
    click.echo(f"   意图: {intent or '(空)'}")
    click.echo(f"   阶段: {sess.state.phase}")


@session.command("list")
@click.option("--base-dir", default=None, help="Checkpoint base directory")
def session_list(base_dir: str | None):
    """List all persisted sessions."""
    from professor_synapse.persistence import CheckpointManager
    bd = Path(base_dir) if base_dir else DEFAULT_BASE
    ckpt = CheckpointManager(bd)
    sessions = ckpt.list_sessions()
    if not sessions:
        click.echo("没有找到已持久化的会话。")
        return
    click.echo(f"已持久化的会话 ({len(sessions)}):")
    for sid in sessions:
        state = ckpt.load(sid)
        if state:
            click.echo(f"  {sid}  |  意图: {state.session.intent[:40]:40s}  |  "
                       f"轮次: {state.session.turn_count:3d}  |  "
                       f"{'✅ 完成' if state.completed else '🔄 进行中'}")
        else:
            click.echo(f"  {sid}  |  (无法加载)")


@session.command("show")
@click.argument("session_id")
@click.option("--base-dir", default=None, help="Checkpoint base directory")
def session_show(session_id: str, base_dir: str | None):
    """Show session details."""
    from professor_synapse.persistence import CheckpointManager
    bd = Path(base_dir) if base_dir else DEFAULT_BASE
    ckpt = CheckpointManager(bd)
    state = ckpt.load(session_id)
    if not state:
        click.echo(f"❌ 会话 {session_id} 不存在或损坏。")
        sys.exit(1)
    click.echo(state.as_json())


@session.command("resume")
@click.argument("session_id")
@click.option("--base-dir", default=None, help="Checkpoint base directory")
def session_resume(session_id: str, base_dir: str | None):
    """Resume an incomplete session after crash."""
    bd = Path(base_dir) if base_dir else DEFAULT_BASE
    reg = _registry()
    sess = Session.load_or_create(bd, session_id=session_id)
    result = resume(sess, reg)
    click.echo(result["response"])
    if result.get("registry_changed"):
        click.echo("⚠️ 请检查 Agent 注册表变更。")


# ── agent ────────────────────────────────────────────────────

@cli.group()
def agent():
    """Manage specialist agents."""
    pass


@agent.command("list")
@click.option("--agents-dir", default=None, help="Agent definitions directory")
def agent_list(agents_dir: str | None):
    """List all registered agents."""
    reg = _registry()
    agents = reg.all()
    if not agents:
        click.echo("没有注册的 Agent。在 agents/ 下创建 .yaml 文件即可添加。")
        return
    click.echo(f"已注册 Agent ({len(agents)}):")
    for a in agents:
        status = "✅" if a.enabled else "⛔"
        click.echo(f"  {status} {a.name:25s}  {a.protocol.value:15s}  {a.description[:50]}")


@agent.command("add")
@click.option("--name", required=True, help="Agent name")
@click.option("--description", default="", help="Agent description")
@click.option("--protocol", default="custom", help="Protocol (convener, code, security, ...)")
@click.option("--role", default="", help="Agent role")
@click.option("--agents-dir", default=None, help="Agent definitions directory")
def agent_add(name: str, description: str, protocol: str, role: str, agents_dir: str | None):
    """Register a new agent."""
    reg = _registry()
    agent = Agent(
        name=name,
        description=description or f"Agent {name}",
        protocol=AgentProtocol.from_str(protocol),
        role=role or "Specialist assistant",
    )
    reg.add_agent(agent)
    click.echo(f"✅ Agent {name} 已注册 (protocol: {protocol})")


@agent.command("remove")
@click.argument("name")
@click.option("--agents-dir", default=None, help="Agent definitions directory")
def agent_remove(name: str, agents_dir: str | None):
    """Remove an agent."""
    reg = _registry()
    if reg.remove_agent(name):
        click.echo(f"✅ Agent {name} 已移除")
    else:
        click.echo(f"❌ Agent {name} 未找到")


# ── serve ────────────────────────────────────────────────────

@cli.command()
@click.option("--input", "-i", required=True, help="User input to route")
@click.option("--session-id", default=None, help="Existing session ID (omit for auto)")
@click.option("--base-dir", default=None, help="Checkpoint base directory")
@click.option("--agents-dir", default=None, help="Agent definitions directory")
def serve(input: str, session_id: str | None, base_dir: str | None, agents_dir: str | None):
    """Route user input to the best agent and return response."""
    reg = _registry()
    sess = _session(base_dir=base_dir, session_id=session_id, intent=input)
    result = route_and_serve(input, sess, reg)
    click.echo(f"📨 Session: {result['session_id']}")
    click.echo(f"🤖 Agent:   {result['agent'] or '无匹配'}")
    click.echo(f"💬 响应:\n{result['response']}")


def main():
    cli()
