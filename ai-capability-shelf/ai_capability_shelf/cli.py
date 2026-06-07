"""
CLI — AI场景能力货架 命令行接口
================================
Click 命令组，六条命令：
  init / add / list / run / build / info

高内聚：每条命令只处理单一职责（初始化/增/查/执行/管线/详细）
低耦合：通过模块公开 API 调用，不直接访问内部数据结构
崩溃安全：所有写操作均通过 CapabilityStore（AtomicWriter + fsync）
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from ai_capability_shelf.models import (
    AtomicComponent,
    CompositeSkill,
    ScenarioSolution,
    CapabilityShelfState,
    CapabilityStatus,
    InterfaceSpec,
    InvokeProtocol,
    ErrorCategory,
    WorkflowStep,
)
from ai_capability_shelf.registry import CapabilityRegistry
from ai_capability_shelf.persistence import AtomicWriter, CapabilityStore, SentinelManager
from ai_capability_shelf.lifecycle import LifecycleManager, PipelineContext
from ai_capability_shelf.runtime import RuntimeEngine, ExecutionResult
from ai_capability_shelf.composition import (
    CompositionValidator,
    DagBuilder,
    CompositeAssembler,
)
from ai_capability_shelf.governance import GovernanceGuard, GovernancePolicy
from ai_capability_shelf.standardization import StandardizationService
from ai_capability_shelf.lottery.cli import cli as lottery_cli


# ══════════════════════════════════════════════════════════
#  全局状态（惰性加载，每个命令调用时构建）
# ══════════════════════════════════════════════════════════

def _resolve_shelf_dir(shelf_dir: str | None = None) -> str:
    """解析货架目录（统一默认值逻辑）"""
    if shelf_dir is None:
        shelf_dir = os.environ.get(
            "CAP_SHELF_DIR",
            str(Path.home() / ".capability-shelf"),
        )
    return shelf_dir


def _get_store_and_registry(
    shelf_dir: str | None = None,
) -> tuple[CapabilityStore, CapabilityRegistry]:
    """获取持久化存储和注册表（惰性初始化，自动连接回调）

    load() 的 meta 信息可通过 ``store.last_load_meta`` 访问，
    包含崩溃恢复状态、哨兵检测结果等。
    registry 的每次变更自动触发 store.save()。
    """
    shelf_dir = _resolve_shelf_dir(shelf_dir)
    store = CapabilityStore(shelf_dir)
    state, _meta = store.load()
    registry = CapabilityRegistry(state)
    return store, registry


def _pretty_json(obj: Any) -> str:
    """格式化 JSON 输出"""
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


# ══════════════════════════════════════════════════════════
#  公共选项
# ══════════════════════════════════════════════════════════

_shelf_dir_option = click.option(
    "--shelf-dir", "-d",
    default=None,
    envvar="CAP_SHELF_DIR",
    help="货架数据目录（默认 ~/.capability-shelf）",
    show_default=False,
)


# ══════════════════════════════════════════════════════════
#  命令: init
# ══════════════════════════════════════════════════════════

@click.group(invoke_without_command=False)
@click.version_option(version="0.1.0", prog_name="cap-shelf")
def cli() -> None:
    """AI场景能力货架 — 五层架构能力管理工具"""
    pass


cli.add_command(lottery_cli)


@cli.command()
@_shelf_dir_option
@click.argument("project_name", required=False)
def init(shelf_dir: str | None, project_name: str | None) -> None:
    """初始化货架存储目录

    PROJECT_NAME 可选 — 不传则只创建空货架结构
    """
    shelf_dir = _resolve_shelf_dir(shelf_dir)
    path = Path(shelf_dir)

    # 创建目录结构
    path.mkdir(parents=True, exist_ok=True)
    (path / "capabilities").mkdir(exist_ok=True)

    # 初始化空状态并持久化（原子写入 + fsync）
    store = CapabilityStore(str(path))
    empty_state = CapabilityShelfState()
    # 写入初始化检查
    store.save(empty_state)

    click.echo(f"✓ 货架已初始化: {path.resolve()}")
    click.echo(f"  状态文件: {path / 'shelf_state.json'}")

    if project_name:
        # 创建项目标记文件
        project_file = path / f".project_{project_name}.json"
        project_data = {
            "project": project_name,
            "created_at": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
            "shelf_dir": str(path.resolve()),
        }
        # 原子写入
        AtomicWriter.write_json_atomic(project_file, project_data)
        click.echo(f"✓ 项目 '{project_name}' 已创建")


# ══════════════════════════════════════════════════════════
#  命令: add (子命令组)
# ══════════════════════════════════════════════════════════

@cli.group()
def add() -> None:
    """添加能力到货架"""
    pass


def _parse_kv_pairs(kv_list: tuple[str, ...] | None) -> Dict[str, str]:
    """解析 KEY=VAL 参数对"""
    result: Dict[str, str] = {}
    for kv in kv_list or []:
        if "=" not in kv:
            click.echo(f"⚠  无效的键值对: {kv} (应为 KEY=VAL)", err=True)
            sys.exit(1)
        key, val = kv.split("=", 1)
        result[key] = val
    return result


@add.command("atomic")
@_shelf_dir_option
@click.argument("name")
@click.option("--description", "-d", default="", help="能力描述")
@click.option("--category", "-c", default="general", help="分类")
@click.option("--version", "-V", default="0.1.0", help="语义版本号")
@click.option("--invoke", "-i", "invoke_str",
              type=click.Choice([p.value for p in InvokeProtocol]),
              default=InvokeProtocol.FUNCTION.value,
              help="调用协议")
@click.option("--tag", "-t", multiple=True, help="标签（可多次）")
def add_atomic(
    shelf_dir: str | None,
    name: str,
    description: str,
    category: str,
    version: str,
    invoke_str: str,
    tag: tuple[str, ...],
) -> None:
    """添加原子组件到货架"""
    store, registry = _get_store_and_registry(shelf_dir)

    comp_id = f"atomic.{name.lower().replace(' ', '_')}"

    component = AtomicComponent(
        id=comp_id,
        name=name,
        description=description or f"原子组件: {name}",
        category=category,
        version=version,
        status=CapabilityStatus.DRAFT,
        invoke=InvokeProtocol(invoke_str),
        interface=InterfaceSpec(
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
            error_definitions=[
                {"code": "INTERNAL_ERROR", "message": "内部错误",
                 "category": ErrorCategory.INTERNAL.value},
            ],
        ),
        tags=list(tag),
        documentation="",
    )

    # 标准化校验
    valid, errors = StandardizationService.check_atomic(component)
    if not valid:
        click.echo("✗ 标准化校验失败:", err=True)
        for e in errors:
            click.echo(f"  - {e}", err=True)
        sys.exit(1)

    registry.register_atomic(component)
    store.save(registry.state)
    click.echo(f"✓ 原子组件已添加: {component.id}")
    click.echo(f"  name={name}, version={version}, invoke={invoke_str}")


@add.command("composite")
@_shelf_dir_option
@click.argument("name")
@click.option("--description", "-d", default="", help="技能描述")
@click.option("--version", "-V", default="0.1.0", help="语义版本号")
@click.option("--step", "-s", "steps", multiple=True,
              help="工作流步骤 (格式: component_id@label)")
def add_composite(
    shelf_dir: str | None,
    name: str,
    description: str,
    version: str,
    steps: tuple[str, ...],
) -> None:
    """添加组合技能到货架"""
    store, registry = _get_store_and_registry(shelf_dir)

    skill_id = f"composite.{name.lower().replace(' ', '_')}"

    # 解析步骤
    workflow_steps: List[WorkflowStep] = []
    for i, raw in enumerate(steps):
        if "@" in raw:
            comp_id, label = raw.split("@", 1)
        else:
            comp_id, label = raw, f"步骤{i+1}"
        workflow_steps.append(WorkflowStep(
            component_id=comp_id.strip(),
            label=label.strip(),
        ))

    skill = CompositeSkill(
        id=skill_id,
        name=name,
        description=description or f"组合技能: {name}",
        version=version,
        status=CapabilityStatus.DRAFT,
        steps=workflow_steps,
    )

    # 标准化校验
    valid, errors = StandardizationService.check_composite(skill)
    if not valid:
        click.echo("✗ 标准化校验失败:", err=True)
        for e in errors:
            click.echo(f"  - {e}", err=True)
        sys.exit(1)

    registry.register_composite(skill)
    store.save(registry.state)
    click.echo(f"✓ 组合技能已添加: {skill.id}")
    click.echo(f"  name={name}, version={version}, steps={len(workflow_steps)}")


@add.command("scenario")
@_shelf_dir_option
@click.argument("name")
@click.option("--description", "-d", default="", help="场景描述")
@click.option("--version", "-V", default="0.1.0", help="语义版本号")
@click.option("--require", "-r", "requires", multiple=True,
              help="依赖的能力 ID（可多次）")
def add_scenario(
    shelf_dir: str | None,
    name: str,
    description: str,
    version: str,
    requires: tuple[str, ...],
) -> None:
    """添加场景方案到货架"""
    store, registry = _get_store_and_registry(shelf_dir)

    scenario_id = f"scenario.{name.lower().replace(' ', '_')}"
    scenario = ScenarioSolution(
        id=scenario_id,
        name=name,
        description=description or f"场景方案: {name}",
        version=version,
        status=CapabilityStatus.DRAFT,
        required_capabilities=list(requires),
    )

    # 标准化校验
    valid, errors = StandardizationService.check_scenario(scenario)
    if not valid:
        click.echo("✗ 标准化校验失败:", err=True)
        for e in errors:
            click.echo(f"  - {e}", err=True)
        sys.exit(1)

    registry.register_scenario(scenario)
    store.save(registry.state)
    click.echo(f"✓ 场景方案已添加: {scenario.id}")
    click.echo(f"  name={name}, version={version}, deps={len(requires)}")


# ══════════════════════════════════════════════════════════
#  命令: list
# ══════════════════════════════════════════════════════════

@cli.command()
@_shelf_dir_option
@click.option("--type", "-t", "type_filter",
              type=click.Choice(["atomic", "composite", "scenario", "all"]),
              default="all", help="能力类型过滤")
@click.option("--status", "-s", "status_filter", default=None,
              help="状态过滤 (draft/on_shelf/retired)")
@click.option("--category", "-c", "cat_filter", default=None,
              help="分类过滤")
@click.option("--json", "-j", "json_output", is_flag=True,
              help="JSON 格式输出")
def list_cmd(
    shelf_dir: str | None,
    type_filter: str,
    status_filter: str | None,
    cat_filter: str | None,
    json_output: bool,
) -> None:
    """列出货架中的能力"""
    store, registry = _get_store_and_registry(shelf_dir)
    state = registry.state

    results: Dict[str, List[Dict[str, Any]]] = {}

    # 原子组件
    if type_filter in ("atomic", "all"):
        items = []
        for comp in state.atomic_components.values():
            if status_filter and comp.status.value != status_filter:
                continue
            if cat_filter and comp.category != cat_filter:
                continue
            items.append({
                "id": comp.id,
                "name": comp.name,
                "type": "atomic",
                "version": comp.version,
                "status": comp.status.value,
                "category": comp.category,
            })
        results["atomics"] = items

    # 组合技能
    if type_filter in ("composite", "all"):
        items = []
        for skill in state.composite_skills.values():
            if status_filter and skill.status.value != status_filter:
                continue
            items.append({
                "id": skill.id,
                "name": skill.name,
                "type": "composite",
                "version": skill.version,
                "status": skill.status.value,
                "steps": len(skill.steps),
            })
        results["composites"] = items

    # 场景方案
    if type_filter in ("scenario", "all"):
        items = []
        for scenario in state.scenario_solutions.values():
            if status_filter and scenario.status.value != status_filter:
                continue
            items.append({
                "id": scenario.id,
                "name": scenario.name,
                "type": "scenario",
                "version": scenario.version,
                "status": scenario.status.value,
                "deps": len(scenario.required_capabilities),
            })
        results["scenarios"] = items

    if json_output:
        click.echo(_pretty_json(results))
        return

    # 人类可读输出
    total = 0
    for key, items in results.items():
        if not items:
            continue
        label = {"atomics": "原子组件", "composites": "组合技能", "scenarios": "场景方案"}
        click.echo(f"\n── {label.get(key, key)} ({len(items)}) ──")
        for item in items:
            meta = _item_meta(item)
            click.echo(f"  {item['id']:<40} v{item['version']:<8} [{item['status']}]{meta}")
        total += len(items)

    click.echo(f"\n总计: {total} 项能力")


def _item_meta(item: Dict[str, Any]) -> str:
    """生成列表项附加信息"""
    parts = []
    if "category" in item and item["category"]:
        parts.append(f" cat={item['category']}")
    if "steps" in item:
        parts.append(f" steps={item['steps']}")
    if "deps" in item:
        parts.append(f" deps={item['deps']}")
    return "".join(parts)


# ══════════════════════════════════════════════════════════
#  命令: run
# ══════════════════════════════════════════════════════════

@cli.command()
@_shelf_dir_option
@click.argument("cap_id")
@click.option("--input", "-i", "input_data", multiple=True,
              help="输入参数 KEY=VAL")
@click.option("--timeout", "-T", type=float, default=30.0,
              help="超时秒数（默认 30）")
@click.option("--policy", "-p", "policy_file", default=None,
              help="管控策略 JSON 文件路径")
@click.option("--json", "-j", "json_output", is_flag=True,
              help="JSON 格式输出")
def run(
    shelf_dir: str | None,
    cap_id: str,
    input_data: tuple[str, ...],
    timeout: float,
    policy_file: str | None,
    json_output: bool,
) -> None:
    """运行货架中的一个能力

    CAP_ID 可以是原子组件、组合技能或场景方案的 ID
    """
    store, registry = _get_store_and_registry(shelf_dir)
    state = registry.state

    # 解析输入数据
    parsed_input = _parse_kv_pairs(input_data) if input_data else {}

    # 加载管控策略
    policy: GovernancePolicy | None = None
    if policy_file:
        p_path = Path(policy_file)
        if not p_path.exists():
            click.echo(f"✗ 策略文件不存在: {policy_file}", err=True)
            sys.exit(1)
        try:
            p_data = json.loads(p_path.read_text(encoding="utf-8"))
            policy = GovernancePolicy(**p_data)
        except (json.JSONDecodeError, Exception) as e:
            click.echo(f"✗ 策略文件解析失败: {e}", err=True)
            sys.exit(1)

    # 构建运行时
    engine = RuntimeEngine(state)

    # 路由到对应的执行器
    result: Dict[str, Any] = {}

    if cap_id in state.atomic_components:
        exec_result = engine.execute_atomic(cap_id, parsed_input, policy)
        result = exec_result.to_dict()
    elif cap_id in state.composite_skills:
        results = engine.execute_composite(cap_id, parsed_input, policy)
        result = {
            "cap_id": cap_id,
            "success": all(r.success for r in results),
            "steps": [r.to_dict() for r in results],
        }
    elif cap_id in state.scenario_solutions:
        raw = engine.execute_scenario(cap_id, parsed_input, policy)
        result = raw  # 已经是 dict
    else:
        click.echo(f"✗ 能力 '{cap_id}' 未在货架中找到", err=True)
        click.echo("  提示: 用 cap-shelf list 查看已有能力")
        sys.exit(1)

    if json_output:
        click.echo(_pretty_json(result))
    else:
        _print_run_result(result)


def _print_run_result(result: Dict[str, Any]) -> None:
    """人类可读的执行结果输出"""
    success = result.get("success", False)
    status_icon = "✓" if success else "✗"
    click.echo(f"\n{status_icon} 执行结果 — {result.get('cap_id', 'unknown')}")
    click.echo(f"  成功: {success}")

    if "error" in result and result["error"]:
        click.echo(f"  错误: {result['error']}")

    if "output" in result and result["output"]:
        click.echo(f"  输出: {_pretty_json(result['output'])}")

    if "duration_ms" in result:
        click.echo(f"  耗时: {result['duration_ms']:.1f}ms")

    if "steps" in result:
        steps = result["steps"]
        ok = sum(1 for s in steps if s.get("success"))
        fail = sum(1 for s in steps if not s.get("success"))
        click.echo(f"  步骤: {ok}/{len(steps)} 通过" + (f", {fail} 失败" if fail else ""))

    if "results" in result:
        sub = result["results"]
        if isinstance(sub, dict):
            click.echo(f"  子能力: {len(sub)} 个")


# ══════════════════════════════════════════════════════════
#  命令: build
# ══════════════════════════════════════════════════════════

@cli.command()
@_shelf_dir_option
@click.argument("project_name")
@click.option("--capabilities", "-c", "caps_file", default=None,
              help="能力定义 JSON 文件路径")
@click.option("--test-cases", "-t", "test_file", default=None,
              help="测试用例 JSON 文件路径")
@click.option("--policies", "-p", "policy_file", default=None,
              help="管控策略 JSON 文件路径")
@click.option("--skip-validation", is_flag=True, default=False,
              help="跳过标准化校验")
@click.option("--work-dir", "-w", default="/tmp/cap_shelf_lifecycle",
              help="检查点目录（默认 /tmp/cap_shelf_lifecycle）")
@click.option("--resume", is_flag=True, default=False,
              help="从检查点恢复（自动检测）")
@click.option("--json", "-j", "json_output", is_flag=True,
              help="JSON 格式输出")
def build(
    shelf_dir: str | None,
    project_name: str,
    caps_file: str | None,
    test_file: str | None,
    policy_file: str | None,
    skip_validation: bool,
    work_dir: str,
    resume: bool,
    json_output: bool,
) -> None:
    """执行七步搭建管线

    PROJECT_NAME 管线项目名称

    崩溃安全：每步完成后原子写入哨兵检查点（tmp → fsync → replace）
    断电重启后，--resume 可从上一步继续
    """
    store, registry = _get_store_and_registry(shelf_dir)

    # 加载能力定义
    capabilities: List[Dict[str, Any]] = []
    if caps_file:
        c_path = Path(caps_file)
        if not c_path.exists():
            click.echo(f"✗ 能力定义文件不存在: {caps_file}", err=True)
            sys.exit(1)
        try:
            cap_data = json.loads(c_path.read_text(encoding="utf-8"))
            if isinstance(cap_data, list):
                capabilities = cap_data
            elif isinstance(cap_data, dict):
                capabilities = cap_data.get("capabilities", [])
            else:
                click.echo("✗ 能力定义格式错误: 需为 list 或 {capabilities: [...]}", err=True)
                sys.exit(1)
        except json.JSONDecodeError as e:
            click.echo(f"✗ 能力定义 JSON 解析失败: {e}", err=True)
            sys.exit(1)
    else:
        click.echo("⚠  未指定能力定义文件 (--capabilities)，使用空列表", err=True)

    # 加载测试用例
    test_cases: List[Dict[str, Any]] | None = None
    if test_file:
        t_path = Path(test_file)
        if not t_path.exists():
            click.echo(f"✗ 测试用例文件不存在: {test_file}", err=True)
            sys.exit(1)
        test_cases = json.loads(t_path.read_text(encoding="utf-8"))
        if not isinstance(test_cases, list):
            click.echo("✗ 测试用例格式错误: 需为 JSON 数组", err=True)
            sys.exit(1)

    # 加载管控策略
    policies: Dict[str, Any] | None = None
    if policy_file:
        p_path = Path(policy_file)
        if not p_path.exists():
            click.echo(f"✗ 策略文件不存在: {policy_file}", err=True)
            sys.exit(1)
        p_data = json.loads(p_path.read_text(encoding="utf-8"))

        if isinstance(p_data, list):
            policies = {}
            for item in p_data:
                if "cap_id" in item and "policy" in item:
                    policies[item["cap_id"]] = GovernancePolicy(**item["policy"])
                elif "cap_id" in item:
                    policies[item["cap_id"]] = GovernancePolicy(**item)
        elif isinstance(p_data, dict):
            policies = {
                k: GovernancePolicy(**v) if isinstance(v, dict) else v
                for k, v in p_data.items()
            }

    # 检查点检测
    checkpoint_mgr = SentinelManager(Path(work_dir).expanduser())
    cp = checkpoint_mgr.read_checkpoint(project_name)
    if cp:
        click.echo(f"ℹ  检测到检查点: 步骤 {cp['step']}/7 — {cp.get('description', '')}")
        if not resume:
            click.echo("  使用 --resume 从检查点继续，或清除检查点文件重新开始")
            click.echo(f"  检查点文件: {work_dir}/.lifecycle_{project_name}.checkpoint")

    # 构建管线管理器
    manager = LifecycleManager(
        registry=registry,
        store=store,
        work_dir=work_dir,
    )

    click.echo(f"\n开始七步管线: {project_name}")
    click.echo(f"  能力数: {len(capabilities)}")
    click.echo(f"  检查点: {work_dir}")
    if policies:
        click.echo(f"  策略数: {len(policies)}")
    if test_cases:
        click.echo(f"  测试用例: {len(test_cases)}")
    if resume and cp:
        click.echo(f"  恢复模式: 从步骤 {cp['step'] + 1} 继续")

    # 执行管线
    result = manager.build_pipeline(
        project_name=project_name,
        capabilities=capabilities,
        policies=policies,
        test_cases=test_cases,
        composites=None,
        scenarios=None,
        skip_validation=skip_validation,
    )

    # 输出结果
    if json_output:
        click.echo(_pretty_json(result))
        return

    _print_build_result(result)


def _print_build_result(result: Dict[str, Any]) -> None:
    """人类可读的管线执行结果"""
    click.echo(f"\n{'='*60}")
    click.echo(f"管线执行完成 — {result.get('project', 'unknown')}")

    if result.get("recovery"):
        click.echo("⚡ 从崩溃检查点恢复执行")

    click.echo("")
    steps = result.get("steps", {})
    for step_name, step_data in steps.items():
        status_icon = {
            "done": "✓", "skipped": "○", "error": "✗",
        }.get(step_data.get("status", "unknown"), "?")
        label = step_name.capitalize()
        status = step_data.get("status", "unknown")

        click.echo(f"  {status_icon} {label:<15} [{status}]")

        # 显示摘要
        if status == "done" and "result" in step_data:
            r = step_data["result"]
            if isinstance(r, dict):
                summary = _step_result_summary(step_name, r)
                if summary:
                    click.echo(f"    {summary}")
            elif isinstance(r, (int, float)):
                click.echo(f"    count={r}")

    if "final" in result:
        final = result["final"]
        click.echo(f"\n  最终状态: {final.get('status', '?')}")
        if "stats" in final:
            stats = final["stats"]
            click.echo(f"  统计: {_pretty_json(stats)}")


def _step_result_summary(step_name: str, r: Dict[str, Any]) -> str:
    """生成步骤结果的单行摘要"""
    if step_name == "inventory":
        return f"共 {r.get('total', 0)} 项能力"
    elif step_name == "package":
        ok = r.get("success", 0)
        total = r.get("total", 0)
        errors = r.get("errors", [])
        verdict = f"{ok}/{total} 封装成功"
        if errors:
            verdict += f", {len(errors)} 个错误"
        return verdict
    elif step_name == "shelve":
        return f"上架 {r} 项"
    elif step_name == "configure":
        return f"已应用于 {r.get('count', 0)} 项能力"
    elif step_name == "test":
        passed = r.get("passed", 0)
        failed = r.get("failed", 0)
        total = r.get("total", 0)
        return f"{passed}/{total} 通过" + (f", {failed} 失败" if failed else "")
    elif step_name == "launch":
        return f"状态: {r.get('status', '?')}"
    return ""


# ══════════════════════════════════════════════════════════
#  命令: info
# ══════════════════════════════════════════════════════════

@cli.command()
@_shelf_dir_option
@click.argument("cap_id")
@click.option("--json", "-j", "json_output", is_flag=True,
              help="JSON 格式输出")
def info(
    shelf_dir: str | None,
    cap_id: str,
    json_output: bool,
) -> None:
    """查看能力的详细信息"""
    store, registry = _get_store_and_registry(shelf_dir)
    state = registry.state

    # 查找能力
    if cap_id in state.atomic_components:
        comp = state.atomic_components[cap_id]
        data = comp.model_dump()
        data["_type"] = "atomic"
    elif cap_id in state.composite_skills:
        skill = state.composite_skills[cap_id]
        data = skill.model_dump()
        data["_type"] = "composite"
    elif cap_id in state.scenario_solutions:
        scenario = state.scenario_solutions[cap_id]
        data = scenario.model_dump()
        data["_type"] = "scenario"
    else:
        click.echo(f"✗ 能力 '{cap_id}' 未在货架中找到", err=True)
        sys.exit(1)

    # 管控策略
    policy = state.governance_policies.get(cap_id)
    if policy:
        data["_governance"] = policy.model_dump()

    if json_output:
        click.echo(_pretty_json(data))
        return

    # 人类可读输出
    type_labels = {
        "atomic": "原子组件",
        "composite": "组合技能",
        "scenario": "场景方案",
    }
    click.echo(f"\\n── {type_labels.get(data.get('_type', 'unknown'), data.get('_type', '?'))} — {data.get('id', '?')} ──")
    click.echo(f"  名称:        {data.get('name', '?')}")
    click.echo(f"  版本:        {data.get('version', '?')}")
    click.echo(f"  状态:        {data.get('status', '?')}")

    if "category" in data:
        click.echo(f"  分类:        {data.get('category', '?')}")
    if "description" in data:
        click.echo(f"  描述:        {data.get('description', '?')[:80]}")

    if data.get('_type') == "atomic":
        click.echo(f"  调用协议:    {data.get('invoke', '?')}")
        click.echo(f"  标签:        {', '.join(data.get('tags', [])) or '无'}")

    if data.get('_type') == "composite":
        steps = data.get("steps", [])
        click.echo(f"  工作流步骤:  {len(steps)}")
        for step in steps:
            click.echo(f"    {step.get('order', '?')}. {step.get('label', '?')} "
                       f"→ {step.get('component_id', '?')}")

    if data.get('_type') == "scenario":
        deps = data.get("required_capabilities", [])
        click.echo(f"  依赖能力:    {len(deps)}")
        for dep in deps:
            click.echo(f"    - {dep}")

    if "_governance" in data:
        g = data["_governance"]
        click.echo(f"  管控策略:")
        click.echo(f"    超时:      {g.get('timeout_seconds', '?')}s")
        click.echo(f"    限流:      {g.get('rate_limit_rps', '?')} rps")
        click.echo(f"    熔断阈值:  {g.get('circuit_breaker_threshold', '?')}")
        click.echo(f"    允许角色:  {', '.join(g.get('required_roles', []))}")


# ══════════════════════════════════════════════════════════
#  入口点
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    cli()
