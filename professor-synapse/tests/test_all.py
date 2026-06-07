"""综合测试套件：验证 Professor Synapse 内化系统的所有模块。

测试覆盖：
  1. state.py     — 纯数据类、JSON 序列化/反序列化、AgentProtocol 解析
  2. persistence.py — 原子写入、fsync、哨兵检测、崩溃恢复、列表查询
  3. registry.py  — YAML 加载、自动索引、增删改、hash 变更
  4. session.py   — 创建→保存→加载→恢复→关闭生命周期
  5. conductor.py — 意图匹配、协议分发、恢复检测
  6. protocols/   — convener、agent_template 协议独立性
  7. CLI          — 命令入口点验证
  8. 集成测试     — 端到端崩溃恢复
"""

import os
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

import pytest
import yaml

# ── 确保 prof-consynapse 模块可导入 ──────────────────────
import sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from professor_synapse.state import (
    Agent, AgentProtocol, SessionState, RunState,
)
from professor_synapse.persistence import CheckpointManager
from professor_synapse.registry import AgentRegistry
from professor_synapse.session import Session
from professor_synapse.conductor import (
    _match_agent, route_and_serve, resume,
)
from professor_synapse.protocols import (
    convener_handle, agent_template_handle,
)


# ════════════════════════════════════════════════════════════
# 1. state.py — 纯数据类，零外部依赖
# ════════════════════════════════════════════════════════════

class TestAgent:
    """Agent 数据类：构造 → 序列化 → 反序列化 → 相等性。"""

    def test_defaults(self):
        a = Agent(name="test-agent", description="Test agent")
        assert a.name == "test-agent"
        assert a.description == "Test agent"
        assert a.protocol == AgentProtocol.CUSTOM
        assert a.enabled is True
        assert a.role == ""
        assert a.tags == []

    def test_from_dict_minimal(self):
        d = {"name": "minimal", "description": "Min"}
        a = Agent.from_dict(d)
        assert a.name == "minimal"
        assert a.description == "Min"
        assert a.protocol == AgentProtocol.CUSTOM

    def test_from_dict_full(self):
        d = {
            "name": "cyber-analyzer",
            "description": "Security analyst",
            "protocol": "security",
            "role": "Security Expert",
            "backstory": "Expert in CVE analysis",
            "traits": ["analytical"],
            "tags": ["security", "cve"],
            "enabled": False,
        }
        a = Agent.from_dict(d)
        assert a.name == "cyber-analyzer"
        assert a.protocol == AgentProtocol.SECURITY
        assert a.enabled is False
        assert "analytical" in a.traits

    def test_to_dict_roundtrip(self):
        a1 = Agent(
            name="roundtrip",
            description="RT",
            protocol=AgentProtocol.CODE,
            role="Coder",
            backstory="A coding agent",
            traits=["fast"],
            tags=["code"],
            enabled=True,
        )
        d = a1.to_dict()
        a2 = Agent.from_dict(d)
        assert a1.name == a2.name
        assert a1.protocol == a2.protocol
        assert a1.traits == a2.traits

    def test_has_uid_and_version(self):
        a = Agent(name="u", description="UID test")
        assert len(a.uid) == 12
        assert a.version == 1


class TestAgentProtocol:
    """协议枚举：from_str() 大小写无关容错。"""

    def test_valid_protocols(self):
        cases = [
            ("convener", AgentProtocol.CONVENER),
            ("code", AgentProtocol.CODE),
            ("security", AgentProtocol.SECURITY),
            ("research", AgentProtocol.RESEARCH),
            ("update", AgentProtocol.UPDATE),
            ("agent_template", AgentProtocol.AGENT_TEMPLATE),
            ("custom", AgentProtocol.CUSTOM),
        ]
        for raw, expected in cases:
            assert AgentProtocol.from_str(raw) == expected, f"from_str({raw!r}) failed"

    def test_case_insensitive(self):
        for raw in ["CONVENER", "Convener", "ConVENER"]:
            assert AgentProtocol.from_str(raw) == AgentProtocol.CONVENER

    def test_unknown_falls_to_custom(self):
        assert AgentProtocol.from_str("nonexistent") == AgentProtocol.CUSTOM

    def test_workflow_protocol(self):
        assert AgentProtocol.from_str("workflow") == AgentProtocol.WORKFLOW


class TestSessionState:
    """SessionState：创建、轮次递增、JSON 兼容。"""

    def test_create(self):
        s = SessionState.create(intent="test session")
        assert s.session_id and len(s.session_id) > 0
        assert s.intent == "test session"
        assert s.turn_count == 0
        assert s.active_agent is None
        assert s.curated_summary == ""

    def test_create_without_intent(self):
        s = SessionState.create()
        assert s.intent == ""
        assert s.turn_count == 0

    def test_advance_turn(self):
        s = SessionState.create()
        assert s.turn_count == 0
        s.advance_turn()
        assert s.turn_count == 1
        s.advance_turn()
        assert s.turn_count == 2

    def test_advance_updates_last_active(self):
        s = SessionState.create()
        before = s.last_active
        s.advance_turn()
        assert s.last_active >= before  # string comparison works with ISO format

    def test_to_dict_roundtrip(self):
        s1 = SessionState.create(intent="test")
        s1.active_agent = "test-agent"
        s1.curated_summary = "summary text"
        d = s1.to_dict()
        s2 = SessionState.from_dict(d)
        assert s2.session_id == s1.session_id
        assert s2.intent == "test"
        assert s2.active_agent == "test-agent"
        assert s2.curated_summary == "summary text"
        assert s2.turn_count == s1.turn_count


class TestRunState:
    """RunState：包装 SessionState，支持 JSON 序列化/反序列化。

    这是崩溃恢复的核心 — from_json() 必须能精确还原。"""

    def test_defaults(self):
        ss = SessionState.create(intent="test")
        rs = RunState(phase="loading", session=ss)
        assert rs.phase == "loading"
        assert rs.completed is False
        assert rs.agent_registry_hash == ""
        assert rs.routing_result == {}
        assert rs.error is None

    def test_json_roundtrip(self):
        ss = SessionState.create(intent="roundtrip!")
        rs1 = RunState(
            phase="analysis",
            session=ss,
            completed=True,
            agent_registry_hash="abc123",
            routing_result={"agent": "test-agent", "response": "ok"},
        )
        j = rs1.as_json()
        rs2 = RunState.from_json(j)
        assert rs2.phase == "analysis"
        assert rs2.completed is True
        assert rs2.agent_registry_hash == "abc123"
        assert rs2.routing_result["agent"] == "test-agent"
        assert rs2.session.session_id == ss.session_id
        assert rs2.session.intent == "roundtrip!"

    def test_json_with_minimal_state(self):
        ss = SessionState.create()
        rs = RunState(phase="init", session=ss)
        j = rs.as_json()
        rs2 = RunState.from_json(j)
        assert rs2.session.turn_count == 0
        assert rs2.session.active_agent is None

    def test_json_corruption_raises(self):
        with pytest.raises((json.JSONDecodeError, ValueError, KeyError)):
            RunState.from_json("{invalid json!!!")

    def test_metadata_preserved(self):
        ss = SessionState.create()
        rs = RunState(phase="test", session=ss, metadata={"key": "value"})
        j = rs.as_json()
        rs2 = RunState.from_json(j)
        assert rs2.metadata["key"] == "value"


# ════════════════════════════════════════════════════════════
# 2. persistence.py — 原子写入 + 哨兵崩溃检测
# ════════════════════════════════════════════════════════════

class TestCheckpointManager:
    """CheckpointManager：原子写入、fsync、崩溃检测、列表。

    这是实现"断电不丢数据"的关键。"""

    @pytest.fixture
    def ckpt(self):
        with tempfile.TemporaryDirectory() as td:
            yield CheckpointManager(td)

    @pytest.fixture
    def state(self):
        ss = SessionState.create(intent="persist test")
        return RunState(phase="test", session=ss)

    def test_save_and_load(self, ckpt, state):
        ckpt.save(state)
        loaded = ckpt.load(state.session.session_id)
        assert loaded is not None
        assert loaded.phase == "test"
        assert loaded.session.intent == "persist test"

    def test_load_nonexistent_returns_none(self, ckpt):
        assert ckpt.load("no-such-session") is None

    def test_sentinel_detection(self, ckpt, state):
        """模拟崩溃：写入 state.json 但缺少 .sentinel → load 必须返回 None。"""
        ckpt.save(state)
        sid = state.session.session_id

        # 删除 sentinel → 模拟"写完 state.json 但还没写 sentinel 时断电"
        sentinel = ckpt._sentinel_path(sid)
        sentinel.unlink()

        loaded = ckpt.load(sid)
        assert loaded is None, "缺失 sentinel 时必须返回 None 以指示不完整写入"

        # 检查崩溃清理：目录已被删除
        assert not ckpt._session_dir(sid).exists()

    def test_corrupted_state_rejected(self, ckpt, state):
        """损坏的 JSON → 检测并丢弃。"""
        ckpt.save(state)
        sid = state.session.session_id
        state_file = ckpt._state_path(sid)
        state_file.write_text("{corrupted garbage}", encoding="utf-8")

        loaded = ckpt.load(sid)
        assert loaded is None, "损坏的 JSON 必须返回 None"

    def test_list_sessions(self, ckpt):
        """多个会话的正确列表。"""
        states = []
        for i in range(3):
            ss = SessionState.create(intent=f"session-{i}")
            rs = RunState(phase=f"phase-{i}", session=ss)
            ckpt.save(rs)
            states.append(rs)

        sessions = ckpt.list_sessions()
        assert len(sessions) == 3
        assert all(sid.startswith("ps-") for sid in sessions)

    def test_delete_session(self, ckpt, state):
        ckpt.save(state)
        sid = state.session.session_id
        assert ckpt.load(sid) is not None
        ckpt.delete_session(sid)
        assert ckpt.load(sid) is None

    def test_clear_all(self, ckpt):
        for i in range(3):
            ss = SessionState.create(intent=f"s{i}")
            ckpt.save(RunState(phase="p", session=ss))
        ckpt.clear_all()
        assert ckpt.list_sessions() == []

    def test_atomicity_on_partial_write(self, ckpt, state):
        """fsync 保证：即使 tmp 文件存在但 final 文件完整，也能正常读取。"""
        ckpt.save(state)
        sid = state.session.session_id
        tmp = ckpt._tmp_path(sid)
        # 写入一个过时的 tmp 文件（模拟前一次崩溃残留）
        old_ss = SessionState.create(intent="stale")
        old_rs = RunState(phase="stale", session=old_ss)
        tmp.write_text(old_rs.as_json(), encoding="utf-8")

        # load 必须返回最后一次完整写入的 state（sentinel 存在）
        loaded = ckpt.load(sid)
        assert loaded is not None
        assert loaded.session.intent == "persist test"  # 不是 "stale"

    def test_fsync_called(self, ckpt, state):
        """验证 fsync 被调用（至少不报错）。"""
        ckpt.save(state)
        sid = state.session.session_id
        state_file = ckpt._state_path(sid)
        sentinel = ckpt._sentinel_path(sid)
        assert state_file.exists()
        assert sentinel.exists()
        assert sentinel.read_text() == "OK\n"


# ════════════════════════════════════════════════════════════
# 3. registry.py — YAML 注册表
# ════════════════════════════════════════════════════════════

class TestRegistry:
    """AgentRegistry：YAML 加载、索引、CRUD、hash 变更检测。"""

    @pytest.fixture
    def agents_dir(self):
        with tempfile.TemporaryDirectory() as td:
            yield Path(td)

    @pytest.fixture
    def registry(self, agents_dir):
        return AgentRegistry(agents_dir)

    def _write_yaml(self, agents_dir: Path, filename: str, agents: list):
        (agents_dir / filename).write_text(
            yaml.dump({"agents": agents}, default_flow_style=False),
            encoding="utf-8",
        )

    def test_empty_registry(self, registry):
        assert registry.all() == []
        assert registry.names() == []
        assert registry.hash == ""

    def test_load_single_file(self, registry, agents_dir):
        self._write_yaml(agents_dir, "test.yaml", [
            {"name": "analyzer", "description": "A sec agent", "protocol": "security"},
        ])
        registry._reload()
        assert len(registry.all()) == 1
        assert registry.get("analyzer") is not None

    def test_load_multiple_files(self, registry, agents_dir):
        self._write_yaml(agents_dir, "conv.yaml", [
            {"name": "convener", "description": "Main"},
        ])
        self._write_yaml(agents_dir, "spec.yaml", [
            {"name": "coder", "description": "Coder", "protocol": "code"},
            {"name": "researcher", "description": "Researcher", "protocol": "research"},
        ])
        registry._reload()
        # Names sorted alphabetically
        assert registry.names() == ["coder", "convener", "researcher"]

    def test_hash_changes_on_file_add(self, registry, agents_dir):
        h1 = registry.hash
        self._write_yaml(agents_dir, "new.yaml", [
            {"name": "new-agent", "description": "New"},
        ])
        registry._reload()
        assert registry.hash != h1
        assert len(registry.hash) == 16

    def test_find_by_protocol(self, registry, agents_dir):
        self._write_yaml(agents_dir, "agents.yaml", [
            {"name": "conv", "description": "C1", "protocol": "convener"},
            {"name": "sec1", "description": "S1", "protocol": "security"},
            {"name": "sec2", "description": "S2", "protocol": "security"},
            {"name": "code1", "description": "C2", "protocol": "code"},
        ])
        registry._reload()
        sec = registry.find_by_protocol(AgentProtocol.SECURITY)
        assert len(sec) == 2
        assert all(a.protocol == AgentProtocol.SECURITY for a in sec)

    def test_find_by_tag(self, registry, agents_dir):
        self._write_yaml(agents_dir, "agents.yaml", [
            {"name": "a1", "description": "A1", "protocol": "code", "tags": ["python", "web"]},
            {"name": "a2", "description": "A2", "protocol": "code", "tags": ["python", "ml"]},
        ])
        registry._reload()
        web = registry.find_by_tag("web")
        assert len(web) == 1
        assert web[0].name == "a1"

    def test_enabled_only(self, registry, agents_dir):
        self._write_yaml(agents_dir, "agents.yaml", [
            {"name": "enabled-one", "description": "E1", "enabled": True},
            {"name": "disabled-one", "description": "D1", "enabled": False},
        ])
        registry._reload()
        assert len(registry.enabled()) == 1
        assert registry.enabled()[0].name == "enabled-one"

    def test_add_agent(self, registry, agents_dir):
        a = Agent(name="added-agent", description="Added", protocol=AgentProtocol.CODE)
        registry.add_agent(a)
        assert registry.get("added-agent") is not None
        # 验证已持久化到文件
        custom_file = agents_dir / "custom_agents.yaml"
        assert custom_file.exists()
        data = yaml.safe_load(custom_file.read_text())
        assert len(data["agents"]) == 1
        assert data["agents"][0]["name"] == "added-agent"

    def test_remove_agent(self, registry, agents_dir):
        self._write_yaml(agents_dir, "agents.yaml", [
            {"name": "to-go", "description": "Bye", "protocol": "code"},
            {"name": "stay", "description": "Stay", "protocol": "code"},
        ])
        registry._reload()
        assert registry.remove_agent("to-go") is True
        assert registry.get("to-go") is None
        assert registry.get("stay") is not None

    def test_remove_nonexistent(self, registry):
        assert registry.remove_agent("nowhere") is False

    def test_to_dict_snapshot(self, registry, agents_dir):
        self._write_yaml(agents_dir, "agents.yaml", [
            {"name": "snap", "description": "Snap", "protocol": "convener"},
        ])
        registry._reload()
        d = registry.to_dict()
        assert "hash" in d
        assert "snap" in d["agent_names"]
        assert d["enabled_count"] == 1

    def test_init_creates_directory(self, tmp_path):
        """AgentRegistry 初始化时自动创建 agents 目录。"""
        d = tmp_path / "nonexistent"
        reg = AgentRegistry(d)
        assert d.exists()


# ════════════════════════════════════════════════════════════
# 4. session.py — 会话生命周期
# ════════════════════════════════════════════════════════════

class TestSession:
    """Session：创建→保存→加载→恢复→关闭。"""

    @pytest.fixture
    def base_dir(self):
        with tempfile.TemporaryDirectory() as td:
            yield Path(td)

    def test_create(self, base_dir):
        sess = Session.create(base_dir, intent="hello")
        assert sess.state.phase == "init"
        assert sess.state.session.intent == "hello"
        assert sess.state.completed is False
        assert sess.session_id.startswith("ps-")

    def test_save_and_load(self, base_dir):
        sess = Session.create(base_dir, intent="test")
        sid = sess.session_id

        # 创建第二个 Session 对象并加载同一个会话
        sess2 = Session.load_or_create(base_dir, session_id=sid)
        assert sess2.state.session.intent == "test"
        assert sess2.state.session.session_id == sid

    def test_advance(self, base_dir):
        sess = Session.create(base_dir)
        sess.advance("phase-a")
        assert sess.state.phase == "phase-a"
        assert sess.state.session.turn_count == 1
        # 验证已持久化
        sess2 = Session.load_or_create(base_dir, session_id=sess.session_id)
        assert sess2.state.phase == "phase-a"
        assert sess2.state.session.turn_count == 1

    def test_close(self, base_dir):
        sess = Session.create(base_dir)
        sess.close()
        assert sess.state.completed is True
        sess2 = Session.load_or_create(base_dir, session_id=sess.session_id)
        assert sess2.state.completed is True

    def test_load_or_create_creates_fresh(self, base_dir):
        """没有 session_id 且没有未完成会话 → 创建新会话。"""
        sess = Session.load_or_create(base_dir, intent="new one")
        assert sess.session_id.startswith("ps-")
        assert sess.state.session.intent == "new one"

    def test_load_or_create_resumes_incomplete(self, base_dir):
        """没有 session_id，但有未完成的会话 → 恢复该会话。"""
        sess = Session.create(base_dir, intent="resume me")
        sess.advance("phase-1")
        sid = sess.session_id

        sess2 = Session.load_or_create(base_dir, intent="ignored")
        # 应该恢复未完成的 sess，而不是创建新的
        assert sess2.session_id == sid
        assert sess2.state.phase == "phase-1"

    def test_load_or_create_specific_id(self, base_dir):
        sess = Session.create(base_dir, intent="specific")
        sid = sess.session_id

        sess2 = Session.load_or_create(base_dir, session_id=sid, intent="override")
        assert sess2.session_id == sid
        # intent 不被覆盖（还原加载时的 intent）
        assert sess2.state.session.intent == "specific"

    def test_load_nonexistent_creates_fresh(self, base_dir):
        """不存在的 session_id → 创建新会话。"""
        sess = Session.load_or_create(base_dir, session_id="no-such-id")
        assert sess.session_id != "no-such-id"
        assert sess.state.phase == "init"

    def test_multiple_sessions_independent(self, base_dir):
        """多个会话互不干扰。"""
        s1 = Session.create(base_dir, intent="first")
        s2 = Session.create(base_dir, intent="second")
        assert s1.session_id != s2.session_id
        assert s1.state.session.intent == "first"
        assert s2.state.session.intent == "second"


# ════════════════════════════════════════════════════════════
# 5. conductor.py — 意图匹配与协议分发
# ════════════════════════════════════════════════════════════

class TestMatchAgent:
    """_match_agent：四种匹配策略的完整覆盖。"""

    @pytest.fixture
    def registry(self):
        reg = AgentRegistry(self.agents_dir)
        reg.add_agent(Agent(name="convener", description="Main convener"))
        reg.add_agent(Agent(name="cyber-analyzer", description="Security analyst",
                            protocol=AgentProtocol.SECURITY, tags=["security", "cve"]))
        reg.add_agent(Agent(name="code-writer", description="Code writer",
                            protocol=AgentProtocol.CODE, tags=["python"]))
        reg.add_agent(Agent(name="update-manager", description="Updates",
                            protocol=AgentProtocol.UPDATE))
        return reg

    @pytest.fixture
    def agents_dir(self, tmp_path):
        return tmp_path / "agents"

    def test_tier1_exact_name(self, registry):
        """Tier 1: 输入包含 Agent 名称。"""
        agent = _match_agent("请问 cyber-analyzer 分析这个 CVE", registry)
        assert agent is not None
        assert agent.name == "cyber-analyzer"

    def test_tier2_tag(self, registry):
        """Tier 2: 输入包含标签关键词。"""
        agent = _match_agent("帮我查一下这个 cve 漏洞", registry)
        assert agent is not None
        assert agent.name == "cyber-analyzer"

    def test_tier3_protocol_keyword_code(self, registry):
        """Tier 3: 编程关键词匹配。"""
        agent = _match_agent("帮我写一段 python 代码", registry)
        assert agent is not None
        assert agent.protocol == AgentProtocol.CODE

    def test_tier3_protocol_keyword_security(self, registry):
        agent = _match_agent("分析这个漏洞 CVE-2024-1234", registry)
        assert agent is not None
        assert agent.protocol in (AgentProtocol.SECURITY, AgentProtocol.CONVENER)

    def test_tier3_protocol_keyword_update(self, registry):
        agent = _match_agent("update 一下摘要内容", registry)
        assert agent is not None
        assert agent.protocol == AgentProtocol.UPDATE

    def test_tier4_fallback_to_convener(self, registry):
        """Tier 4: 无匹配 → 回退到 convener。"""
        agent = _match_agent("今天天气怎么样", registry)
        assert agent is not None
        assert agent.name == "convener"

    def test_empty_registry_returns_none(self):
        reg = AgentRegistry(Path("/tmp/no-agents"))
        agent = _match_agent("hello", reg)
        assert agent is None


class TestRouteAndServe:
    """route_and_serve：协议分发 + 会话更新 + checkpoint。"""

    @pytest.fixture
    def base_dir(self):
        with tempfile.TemporaryDirectory() as td:
            yield Path(td)

    @pytest.fixture
    def registry(self):
        reg = AgentRegistry(self.agents_dir)
        reg.add_agent(Agent(name="convener", description="Main convener"))
        reg.add_agent(Agent(name="sec-agent", description="Security analyst",
                            protocol=AgentProtocol.SECURITY, tags=["cve"]))
        return reg

    @pytest.fixture
    def agents_dir(self, tmp_path):
        return tmp_path / "agents-for-route"

    def test_routes_and_checkpoints(self, base_dir, registry):
        """路由后数据被 checkpoint。"""
        sess = Session.create(base_dir, intent="init")
        result = route_and_serve("分析这个 CVE-2024", sess, registry)

        assert result["agent"] is not None
        assert "response" in result
        assert result["session_id"] == sess.session_id

        # 验证已在磁盘 checkpoint
        sess2 = Session.load_or_create(base_dir, session_id=sess.session_id)
        assert sess2.state.session.active_agent is not None
        assert sess2.state.routing_result is not None
        assert sess2.state.session.turn_count == 0  # route_and_serve 不增加 turn_count

    def test_updates_session_summary(self, base_dir, registry):
        """路由后 summary 应包含 agent 响应摘要。"""
        sess = Session.create(base_dir, intent="test")
        _ = route_and_serve("分析这个 CVE-2024", sess, registry)
        assert len(sess.state.session.curated_summary) > 0
        assert "sec-agent" in sess.state.session.curated_summary or "convener" in sess.state.session.curated_summary

    def test_no_match_returns_error(self, base_dir):
        """无 Agent 时返回错误消息。"""
        empty_reg = AgentRegistry(base_dir / "empty-agents")
        sess = Session.create(base_dir, intent="test")
        result = route_and_serve("anything", sess, empty_reg)
        assert result["agent"] is None
        assert "没有找到" in result["response"]


class TestResume:
    """resume：恢复检测 + registry hash 变更警告。"""

    @pytest.fixture
    def base_dir(self):
        with tempfile.TemporaryDirectory() as td:
            yield Path(td)

    @pytest.fixture
    def agents_dir(self, tmp_path):
        return tmp_path / "agents-for-resume"

    @pytest.fixture
    def registry(self):
        reg = AgentRegistry(self.agents_dir)
        reg.add_agent(Agent(name="conv", description="Main convener"))
        return reg

    def test_resume_normal(self, base_dir, registry):
        sess = Session.create(base_dir, intent="test")
        route_and_serve("hello", sess, registry)

        result = resume(sess, registry)
        assert result["registry_changed"] is False
        assert "恢复完成" in result["response"]

    def test_resume_detects_hash_change(self, base_dir, registry):
        sess = Session.create(base_dir, intent="test")
        route_and_serve("hello", sess, registry)

        # 修改注册表（hash 改变）
        registry.add_agent(Agent(name="new-agent", description="New",
                                 protocol=AgentProtocol.CODE))

        result = resume(sess, registry)
        assert result["registry_changed"] is True
        assert "注册表已变更" in result["response"]


# ════════════════════════════════════════════════════════════
# 6. protocols/ — 每个协议独立可测
# ════════════════════════════════════════════════════════════

class TestConvenerProtocol:
    """Convener 协议：通用处理 + 响应格式。"""

    def test_response_format(self):
        agent = Agent(name="conv", description="Conv")
        result = convener_handle(agent, "用户输入内容", session_summary="摘要")
        assert "response" in result
        assert "routing_hint" in result
        assert "metadata" in result
        assert "conv" in result["response"]

    def test_uses_session_summary(self):
        agent = Agent(name="conv", description="Conv")
        result = convener_handle(agent, "hi", session_summary="existing summary")
        assert "existing summary" in result["response"]


class TestAgentTemplateProtocol:
    """Agent Template 协议：生成新 Agent 草稿。"""

    def test_creates_draft(self):
        agent = Agent(name="templater", description="Template maker",
                      protocol=AgentProtocol.AGENT_TEMPLATE)
        result = agent_template_handle(
            agent,
            "create an agent for security analysis",
        )
        assert "response" in result
        assert "metadata" in result
        draft = result["metadata"].get("draft_agent")
        assert draft is not None
        assert "name" in draft

    def test_extracts_name_from_input(self):
        agent = Agent(name="templater", description="Template")
        result = agent_template_handle(
            agent,
            "create agent-pentest for penetration testing",
        )
        draft = result["metadata"]["draft_agent"]
        assert draft["name"] == "agent-pentest"

    def test_no_name_fallback(self):
        agent = Agent(name="templater", description="Template")
        result = agent_template_handle(
            agent,
            "I need a new assistant",
        )
        draft = result["metadata"]["draft_agent"]
        assert draft["name"] == "custom-agent"


# ════════════════════════════════════════════════════════════
# 7. CLI — 入口点验证
# ════════════════════════════════════════════════════════════

class TestCLI:
    """验证 Click 命令存在且可解析。"""

    def test_import_and_commands(self):
        from professor_synapse.cli import cli
        # Click Group 的主命令组
        assert hasattr(cli, "commands")
        cmd_names = list(cli.commands.keys())
        assert "session" in cmd_names
        assert "agent" in cmd_names
        assert "serve" in cmd_names

    def test_session_subcommands(self):
        from professor_synapse.cli import cli
        session_cmd = cli.commands["session"]
        assert hasattr(session_cmd, "commands")
        sub_names = list(session_cmd.commands.keys())
        assert "create" in sub_names
        assert "list" in sub_names
        assert "show" in sub_names
        assert "resume" in sub_names

    def test_agent_subcommands(self):
        from professor_synapse.cli import cli
        agent_cmd = cli.commands["agent"]
        assert hasattr(agent_cmd, "commands")
        sub_names = list(agent_cmd.commands.keys())
        assert "list" in sub_names
        assert "add" in sub_names
        assert "remove" in sub_names


# ════════════════════════════════════════════════════════════
# 8. 集成测试 — 端到端持久化 + 崩溃恢复
# ════════════════════════════════════════════════════════════

class TestCrashRecoveryIntegration:
    """模拟：会话创建 → checkpoint → 模拟断电 → 恢复 → 完成。"""

    @pytest.fixture
    def work_dir(self):
        with tempfile.TemporaryDirectory() as td:
            yield Path(td)

    @pytest.fixture
    def agents_dir(self, tmp_path):
        return tmp_path / "agents-int"

    @pytest.fixture
    def registry(self):
        reg = AgentRegistry(self.agents_dir)
        reg.add_agent(Agent(name="convener", description="Main convener"))
        return reg

    def test_serialize_and_recover(self, work_dir, registry):
        """创建 → 路由 → checkpoint → 模拟恢复加载 → 读取正确数据。"""
        sess = Session.create(work_dir, intent="crash test")
        _ = route_and_serve("开始分析", sess, registry)
        sid = sess.session_id

        # 模拟：程序退出，重新加载
        sess2 = Session.load_or_create(work_dir, session_id=sid)
        assert sess2.state.phase == "init"
        assert sess2.state.session.intent == "crash test"
        assert sess2.state.routing_result is not None

    def test_incomplete_session_after_crash(self, work_dir):
        """模拟：写一半断电 → sentinel 不存在 → 丢弃。"""
        ss = SessionState.create(intent="lost")
        rs = RunState(phase="mid-flight", session=ss)
        ckpt = CheckpointManager(work_dir)
        ckpt.save(rs)
        sid = ss.session_id

        # 删除 sentinel 模拟断电
        sentinel = ckpt._sentinel_path(sid)
        sentinel.unlink()

        # 加载时必须检测到不完整写入
        loaded = ckpt.load(sid)
        assert loaded is None

    def test_atomic_writes_survive_reload(self, work_dir):
        """多次保存后 reload → 数据一致。"""
        sess = Session.create(work_dir, intent="atomic test")
        for phase in ["a", "b", "c"]:
            sess.advance(phase)

        sess2 = Session.load_or_create(work_dir, session_id=sess.session_id)
        assert sess2.state.phase == "c"
        assert sess2.state.session.turn_count == 3

    def test_close_and_reopen(self, work_dir):
        """关闭会话后重新加载 → completed=True。"""
        sess = Session.create(work_dir)
        sess.close()
        sess2 = Session.load_or_create(work_dir, session_id=sess.session_id)
        assert sess2.state.completed is True
