---
name: hermes-atropos-environments
description: "Build RL environments for Atropos training via HermesAgentBaseEnv — agent loop integration, reward design, CLI modes, and inference setup."
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [atropos, rl, environments, training, reinforcement-learning, reward-functions]
    related_skills: [axolotl, fine-tuning-with-trl, lm-evaluation-harness]
---

# Hermes Agent Atropos Environments

Guide for building RL environments in the hermes-agent repo that integrate with the Atropos training framework.

## Purpose

Provide a structured reference for building RL environments that plug into the Atropos training framework via HermesAgentBaseEnv, covering the agent-loop integration, reward design, CLI modes, and inference configuration that makes Hermes-agent environments distinct from standard Atropos envs.

## Why This Works

**Concept 1: Multi-turn agent loop with tool calling is the core differentiator.** Hermes environments do not score single-turn completions. The base env orchestrates a full multi-turn agent conversation where the model can call terminal, file, and web tools. Your environment only implements the task logic (prompt, reward, evaluation) while the base class handles tool resolution, agent loop, and message orchestration.

**Concept 2: Inference setup is an explicit user-facing decision.** Atropos environments work with four fundamentally different inference backends (OpenRouter, VLLM, OpenAI-compatible, local server), each requiring different flags. The skill mandates asking the user before every inference session, preventing silent failures from mismatched server types or missing health endpoints.

**Concept 3: The AgentResult dataclass requires message iteration, not direct field access.** Newcomers often look for `result.final_response` or `result.tool_calls` — these don't exist. The skill teaches the correct pattern of extracting the last assistant message with content from `result.messages`, plus iterating tool calls with isinstance type-checking for dict vs object variance.

## Examples

**Good: LLM judge for an open-ended research question environment.** Context: Environment tests whether the model can research a novel question using web tools and return a cited answer. The reward function calls `self.server.chat_completion()` with a scoring prompt that evaluates correctness, citation quality, and reasoning depth, extracting a JSON float. A keyword-overlap heuristic fallback catches API failures.

```python
async def compute_reward(self, item, result, ctx):
    final = ""
    for msg in reversed(result.messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            final = msg["content"]
            break
    judge_prompt = f"Score this answer 0-1 for correctness:\nQ: {item['q']}\nA: {final}"
    resp = await self.server.chat_completion([{"role": "user", "content": judge_prompt}])
    try:
        return float(json.loads(resp)["score"])
    except Exception:
        return 0.3 if any(k in final.lower() for k in item.get("keywords", [])) else 0.0
```

**Good: Binary code verification for a code-generation environment.** Context: Environment asks the model to write a Python function and run tests. The reward function runs `pytest` via `ctx.terminal()` and returns 1.0 if all tests pass, 0.0 otherwise.

```python
async def compute_reward(self, item, result, ctx):
    test_result = ctx.terminal("pytest test_solution.py -q", timeout=30)
    return 1.0 if test_result["exit_code"] == 0 else 0.0
```

**Good: Multi-signal reward for a tool-using agent.** Context: Environment expects the model to use web research, file I/O, and terminal tools to complete a multi-step task. Reward weights correctness at 0.6, tool diversity at 0.2, and efficiency (turns used) at 0.2.

```python
async def compute_reward(self, item, result, ctx):
    final = self._extract_final(result.messages)
    tools_used = set()
    for msg in result.messages:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                tools_used.add(tc.get("function", {}).get("name"))
    correctness = await self._llm_judge(item, final)
    diversity = min(1.0, len(tools_used) / 3)
    efficiency = max(0.0, 1.0 - (result.turns_used / self.config.max_agent_turns))
    return min(1.0, 0.6 * correctness + 0.2 * diversity + 0.2 * efficiency)
```

**Good: Evaluate method with tool resolution and iteration.** Context: A complete `evaluate()` implementation that loops over eval items, creates a fresh `HermesAgentLoop` per item, scores with `compute_reward`, and logs results.

```python
async def evaluate(self, *args, **kwargs):
    import time, uuid
    from environments.agent_loop import HermesAgentLoop
    from environments.tool_context import ToolContext
    start, tools, valids = time.time(), *self._resolve_tools_for_group()
    samples = []
    for item in self._eval_items[:self.config.eval_size]:
        task_id = str(uuid.uuid4())
        agent = HermesAgentLoop(self.server, tools, valids, max_turns=10, task_id=task_id)
        result = await agent.run([{"role": "user", "content": self.format_prompt(item)}])
        ctx = ToolContext(task_id)
        try:
            reward = await self.compute_reward(item, result, ctx)
        finally:
            ctx.cleanup()
        samples.append({"reward": reward})
    await self.evaluate_log(metrics={"eval/mean": sum(s["reward"] for s in samples)/len(samples)},
                            samples=samples, start_time=start, end_time=time.time())
```

## Anti-Patterns

**Anti-Pattern 1: Treating AgentResult as a simple dict.** Writing `result.final_response` or `result.tool_calls` produces silent None/AttributeError. The result dataclass has `.messages`, `.turns_used`, `.finished_naturally`, and `.tool_errors` — everything else requires iterating `.messages`.

**Anti-Pattern 2: Using chat_completion instead of HermesAgentLoop in evaluate().** Calling `self.server.chat_completion()` directly in evaluate means no tools are available. The whole purpose of Hermes-agent environments is agentic evaluation where the model can search, run code, and read files. Always instantiate `HermesAgentLoop` with resolved tool schemas.

**Anti-Pattern 3: Hardcoding inference provider and skipping the user prompt.** Assuming OpenRouter with claude-sonnet when the user wants a local VLLM deployment leads to connection errors and API key issues. The mandatory "ask the user first" step prevents this class of failure.

**Anti-Pattern 4: Calling _llm_judge twice (in compute_reward and evaluate).** If `compute_reward` already calls `_llm_judge`, calling it again in `evaluate()` doubles API costs and may produce inconsistent scores. Instead, extract the score from the reward buffer or accept the previously computed reward.

**Anti-Pattern 5: Not calling ToolContext.cleanup() in a finally block.** ToolContext spawns sandbox containers or temporary directories. Without `finally: ctx.cleanup()`, an exception in `compute_reward` leaks resources and may saturate disk or container limits.

## When NOT to Use

- **For single-turn inference benchmarks** — If your task doesn't require tool calling (terminal, file, web), a standard Atropos BaseEnv (not HermesAgentBaseEnv) is simpler and faster.
- **For tuning model prompt formats or chat templates** — Atropos environments are for RL training. Use `lm-evaluation-harness` or direct inference scripts for prompt engineering.
- **When you don't have an inference backend available** — If there's no running VLLM, no OpenRouter key, and no local API server, the environment cannot run. Use offline data-only validation first.
- **For tasks requiring only binary pass/fail with no multi-turn interaction** — A simple pytest-based eval harness is more appropriate than a full agent loop environment.
- **When the dataset is too large to load in setup()** — Environments load the full dataset into memory at startup. For datasets >10GB, use a streaming DataLoader or pre-process offline.
- **For debugging reward function math in isolation** — Use a standalone Python script with mock AgentResult objects. Don't spin up the full agent loop just to debug reward logic.

## Cross-References

- **axolotl** — Fine-tuning pipeline that consumes processed JSONL from Atropos process mode; pairs with environment data generation.
- **fine-tuning-with-trl** — TRL-based RL training that uses environments; configure reward normalization and PPO hyperparameters to match your env's score range.
- **lm-evaluation-harness** — Standardized benchmark eval; use for non-agentic tasks that don't need the HermesAgentLoop multi-turn evaluation.
- **hermes-agent-architecture** — Underlying agent loop, tool resolution, and credential pool that the base env orchestrates; understand the full routing stack.
- **hermes-agent-skill-standards** — General skill authoring conventions; RL environment skills are a specialization with mandatory inference setup, CLI mode documentation, and reward function patterns.

---

## Architecture Overview

```
Atropos BaseEnv (atroposlib/envs/base.py)
    └── HermesAgentBaseEnv (environments/hermes_base_env.py)
            ├── Handles agent loop orchestration
            ├── Handles tool resolution per group
            ├── Handles ToolContext for reward verification
            └── YOUR ENVIRONMENT (environments/your_env.py)
                    Only implements: setup, get_next_item, format_prompt,
                                    compute_reward, evaluate, wandb_log
```

Hermes environments are special because they run a **multi-turn agent loop with tool calling** — not just single-turn completions. The base env handles the loop; you implement the task and scoring.

## File Locations

| File | Purpose |
|------|---------|
| `environments/hermes_base_env.py` | Base class with agent loop + tool resolution |
| `environments/agent_loop.py` | `HermesAgentLoop` + `AgentResult` dataclass |
| `environments/tool_context.py` | `ToolContext` for reward verification |
| `environments/tool_call_parsers.py` | Phase 2 tool call parsers (hermes, mistral, etc.) |
| `environments/your_env.py` | Your environment implementation |

## Inference Setup — Ask the User First

**IMPORTANT:** Before running any test, evaluation, or data generation command, always ask the user how they want to handle inference. Do NOT assume OpenRouter or any specific endpoint. Present these options:

1. **OpenRouter** — Ask which model they want to use (e.g., `anthropic/claude-sonnet-4.5`, `google/gemini-2.5-pro`, `meta-llama/llama-3.3-70b-instruct`, etc.). Requires `OPENROUTER_API_KEY` in environment.
2. **Self-hosted VLLM endpoint** — Ask for their base URL (e.g., `http://localhost:8000/v1`) and model name. Set `--openai.server_type vllm`.
3. **Other OpenAI-compatible API** — Ask for the base URL, model name, and any required API key. Set `--openai.server_type openai` and `--openai.health_check false`.
4. **Local Atropos training server** — For `serve` mode with a live training loop. Default `http://localhost:8000/v1`.

Once the user tells you their setup, use those values in all CLI commands for that session. Example prompts:

> "Before I run this, how would you like to handle inference?
> 1. OpenRouter (I'll need your preferred model, e.g. claude-sonnet-4.5)
> 2. A self-hosted VLLM endpoint (give me the URL and model name)
> 3. Another OpenAI-compatible API (give me the URL, model, and any auth details)
> 4. Local Atropos training server (serve mode)"

### Key flags by provider:

| Provider | `--openai.server_type` | `--openai.health_check` | `--openai.api_key` |
|----------|----------------------|------------------------|-------------------|
| OpenRouter | `openai` | `false` | `$OPENROUTER_API_KEY` |
| VLLM (self-hosted) | `vllm` | (default) | (not needed) |
| Other OpenAI-compatible | `openai` | `false` | As needed |
| Local Atropos | (default) | (default) | (not needed) |

## Required Methods

### 1. `setup()` — Load dataset and initialize state

```python
async def setup(self) -> None:
    """Called once at startup. Load datasets, initialize state."""
    try:
        from datasets import load_dataset
        ds = load_dataset("your/dataset", split="test")
        self._items = [...]
    except Exception:
        self._items = BUILTIN_SAMPLES

    random.shuffle(self._items)
    eval_size = max(20, int(len(self._items) * 0.1))
    self._eval_items = self._items[:eval_size]
    self._items = self._items[eval_size:]
```

### 2. `get_next_item()` — Return next training item

```python
async def get_next_item(self) -> dict:
    item = self._items[self._index % len(self._items)]
    self._index += 1
    return item
```

### 3. `format_prompt(item)` — Convert item to user message

```python
def format_prompt(self, item: dict) -> str:
    return f"Research this question: {item['question']}"
```

### 4. `compute_reward(item, result, ctx)` — Score the rollout

**CRITICAL**: `result` is an `AgentResult`, NOT a dict. It has these attributes:
- `result.messages` — List of message dicts (OpenAI format)
- `result.turns_used` — Number of LLM calls made
- `result.finished_naturally` — True if model stopped voluntarily
- `result.tool_errors` — List of ToolError objects

**AgentResult does NOT have**: `final_response`, `tool_calls`, `tools_used`.
You must extract these from `result.messages`:

```python
async def compute_reward(self, item, result: AgentResult, ctx: ToolContext) -> float:
    final_response = ""
    tools_used = []
    for msg in reversed(result.messages):
        if msg.get("role") == "assistant" and msg.get("content") and not final_response:
            final_response = msg["content"]
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                name = fn.get("name", "")
                if name:
                    tools_used.append(name)

    correctness = await self._llm_judge(item, final_response)
    return correctness
```

`ctx` (ToolContext) gives you terminal/file access to the agent's sandbox for verification:
```python
result = ctx.terminal("pytest /workspace/test.py")
return 1.0 if result["exit_code"] == 0 else 0.0
```

### 5. `evaluate()` — Periodic evaluation with full agent loop

**MUST use the full agent loop with tools**, not single-turn chat_completion:

```python
async def evaluate(self, *args, **kwargs) -> None:
    import time, uuid
    from environments.agent_loop import HermesAgentLoop
    from environments.tool_context import ToolContext

    start_time = time.time()
    tools, valid_names = self._resolve_tools_for_group()
    samples = []

    for item in self._eval_items[:self.config.eval_size]:
        task_id = str(uuid.uuid4())
        messages = []
        if self.config.system_prompt:
            messages.append({"role": "system", "content": self.config.system_prompt})
        messages.append({"role": "user", "content": self.format_prompt(item)})

        agent = HermesAgentLoop(
            server=self.server,
            tool_schemas=tools,
            valid_tool_names=valid_names,
            max_turns=self.config.max_agent_turns,
            task_id=task_id,
            temperature=0.0,
            max_tokens=self.config.max_token_length,
            extra_body=self.config.extra_body,
        )
        result = await agent.run(messages)

        ctx = ToolContext(task_id)
        try:
            reward = await self.compute_reward(item, result, ctx)
        finally:
            ctx.cleanup()

        samples.append({"prompt": ..., "response": ..., "reward": reward})

    eval_metrics = {"eval/mean_reward": ...}
    await self.evaluate_log(metrics=eval_metrics, samples=samples,
                            start_time=start_time, end_time=time.time())
```

### 6. `wandb_log()` — Custom metrics logging

Always call `super().wandb_log()` at the end:

```python
async def wandb_log(self, wandb_metrics=None):
    if wandb_metrics is None:
        wandb_metrics = {}
    if self._reward_buffer:
        n = len(self._reward_buffer)
        wandb_metrics["train/mean_reward"] = sum(self._reward_buffer) / n
        self._reward_buffer.clear()
    await super().wandb_log(wandb_metrics)  # MUST call super
```

## Config Class

Always create a custom config subclass with Pydantic Field descriptors. Key inherited fields you can tune: `enabled_toolsets`, `max_agent_turns`, `agent_temperature`, `system_prompt`, `terminal_backend`, `group_size`, `steps_per_eval`, `total_steps`.

## config_init() — Default Configuration

Classmethod returning `(YourEnvConfig, [APIServerConfig(...)])`. Set server_type to "openai" for OpenRouter/external APIs. Load API key from environment variable.

## Three CLI Modes

```bash
# SERVE — Full training loop (connects to Atropos API server)
python environments/my_env.py serve --openai.base_url http://localhost:8000/v1

# PROCESS — Offline data generation (saves JSONL)
python environments/my_env.py process --env.total_steps 10 --env.group_size 1 \
    --env.use_wandb false --env.data_path_to_save_groups output.jsonl \
    --openai.base_url "<USER_BASE_URL>" \
    --openai.model_name "<USER_MODEL>" \
    --openai.server_type <USER_SERVER_TYPE> --openai.health_check false

# EVALUATE — Standalone eval (runs setup + evaluate only)
python environments/my_env.py evaluate --env.eval_size 20 \
    --env.data_dir_to_save_evals /tmp/eval_results \
    --openai.base_url "<USER_BASE_URL>" \
    --openai.model_name "<USER_MODEL>" \
    --openai.server_type <USER_SERVER_TYPE> --openai.health_check false
```

Config priority: CLI args > YAML file > config_init() defaults.

## Common Pitfalls

1. **AgentResult has .messages, not .final_response** — Extract the final response by iterating reversed(result.messages).
2. **evaluate() must use HermesAgentLoop, not chat_completion** — Single-turn chat_completion has no tools.
3. **Don't call _llm_judge twice** — If compute_reward already calls it, extract the score from the buffer instead.
4. **Eval pollutes training buffers** — compute_reward appends to metric buffers. During eval, roll back buffer entries.
5. **Always set health_check=false for OpenRouter** — OpenRouter has no /health endpoint.
6. **Set data_dir_to_save_evals in evaluate mode** — Without it, results aren't saved.
7. **default_toolsets class variable vs enabled_toolsets config** — The class variable is a hint; the config field controls tool resolution.
8. **Tool call parsing in messages** — Tool calls are dicts with `{"function": {"name": ..., "arguments": ...}}`.
9. **ToolContext.cleanup()** — Always call in a finally block to release sandbox resources.
10. **server_type must be "openai" for external APIs** — Without it, Atropos assumes a local VLLM server.
11. **Always ask the user for their inference setup** — Never hardcode or assume a specific provider/model.

## Reward Function Patterns

### LLM Judge (for open-ended tasks)
Use `self.server.chat_completion()` with a scoring prompt. Parse JSON response for score float. Always include a heuristic fallback (keyword overlap) for when the judge call fails.

### Binary Verification (for code/terminal tasks)
Use `ctx.terminal("pytest test.py -q")` to run tests in the agent's sandbox. Return 1.0 for pass, 0.0 for fail.

### Multi-Signal (combine multiple indicators)
Weight correctness (0.6) + tool usage (0.2) + efficiency (0.2) + optional bonuses. Clamp to [0, 1].

## Testing Your Environment

1. **Import test**: `python -c "from environments.my_env import MyEnv; print('OK')"`
2. **Ask the user for inference setup**
3. **Process mode** (1 item): Verify JSONL output has valid tokens, masks, scores
4. **Evaluate mode**: Verify full agent loop runs with tools, metrics logged correctly
5. **Check reward range**: Scores should be in [0, 1], not all identical

## Minimum Implementation Checklist

```python
class MyEnv(HermesAgentBaseEnv):
    name = "my-env"
    env_config_cls = MyEnvConfig

    @classmethod
    def config_init(cls): ...          # Default server + env config
    async def setup(self): ...         # Load dataset + train/eval split
    async def get_next_item(self): ... # Cycle through training items
    def format_prompt(self, item): ... # Item → user message string
    async def compute_reward(self, item, result, ctx): ...  # Score rollout
    async def evaluate(self, *args, **kwargs): ...  # Full agent loop eval
    async def wandb_log(self, metrics=None): ...    # Custom metrics + super()

if __name__ == "__main__":
    MyEnv.cli()
```
