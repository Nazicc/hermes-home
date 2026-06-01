---
name: parallel-cli
category: optional-skills
metadata:
  hermes:
    tags: [parallel, cli, sub-agent, task-decomposition, concurrent]
    related_skills:
      - hermes-agent
      - deep-research
      - research-paper-writing
---

# Parallel CLI Agent

A command-line interface for spawning parallel sub-agents, each solving a self-contained subtask with real-time progress reporting and configurable concurrency. Converts "do this complex thing" into "do these N smaller things in parallel."

## Why This Works

**Concept 1: Divide-and-Conquer with Sub-Agent Autonomy.** The Parallel CLI Agent decomposes a complex task into independent subtasks and spawns one sub-agent per subtask. Each sub-agent receives its own goal, context, and tool set — it operates autonomously without blocking or waiting for siblings. This mirrors the classic divide-and-conquer algorithm: a task that takes 30 minutes sequentially becomes a 3-minute batch when split into 10 parallel subtasks (on a system with sufficient resources).

**Concept 2: Real-Time Progress Dashboard with Dynamic Allocation.** The CLI provides a live-updating table of all sub-agents showing status (running/completed/failed), execution time, and output preview. If a sub-agent fails, its slot can be retried or reassigned without restarting the entire batch. Completed sub-agents free up slots immediately — the orchestrator dynamically assigns queued subtasks to freed slots, keeping utilization high even when subtasks have wildly different durations.

## Core Commands

```bash
# Run sub-agents with a definition file
parallel-cli run --file tasks.yaml

# Run inline sub-agents
parallel-cli run --agents 5 --prompt "Analyze these 20 papers: @papers.txt"

# Monitor running agents
parallel-cli status

# Cancel a running agent batch (Ctrl+C or)
parallel-cli cancel <batch-id>

# View results for a completed batch
parallel-cli result <batch-id>
```

## Task Definition Format (YAML)

```yaml
name: "Literature Review"
tasks:
  - id: "task-1"
    name: "Summarize Paper A"
    prompt: "Read and summarize the key contributions of paper linked at URL_A"
    tools: ["web-search", "read-url"]
  - id: "task-2"
    name: "Summarize Paper B"
    prompt: "Read and summarize the key contributions of paper linked at URL_B"
    tools: ["web-search", "read-url"]
  - id: "task-3"
    name: "Synthesize Findings"
    prompt: "Given summaries from task-1 and task-2, identify common themes and contradictions"
    tools: ["read-file"]
    depends_on: ["task-1", "task-2"]  # Runs after dependencies complete
concurrency: 2  # Max parallel agents
```

## Concurrency Model

- `concurrency: N` — up to N agents running simultaneously
- Agents with `depends_on` wait until all dependency IDs complete before starting
- Free slots are dynamically reallocated: if task-1 takes 10s and task-2 takes 60s, task-3 starts while task-2 is still running (assuming only 1 slot free)
- Default concurrency: CPU core count, capped at 8
- Sub-agents share no state — results must be explicitly passed via `depends_on` or file writes

## Examples

**Good: Batch literature review.** You have 15 PDFs to summarize and a synthesis to write. Define 15 "summarize paper" tasks (each independent) plus 1 "synthesize" task that depends on all 15. Set `concurrency: 4`. The 15 summaries run in waves (4 at a time), and the synthesis starts automatically when all summaries complete. Total time: ~5 minutes instead of 30+ minutes doing them one-by-one.

**Good: Multi-repository code audit.** You need to check 8 GitHub repos for common security issues (hardcoded secrets, exposed API keys, outdated dependencies). Each repo gets its own sub-agent with tools `["sirchmunk", "web-search", "read-file"]`. Each sub-agent searches its repo independently. The parallel CLI runs them all simultaneously; in 2 minutes you have 8 independent audit reports instead of 16 minutes of sequential work.

## Anti-Patterns

**Anti-Pattern 1: Creating dependent tasks that could be parallel.** If task-A and task-B both read the same file and produce summaries, they should be parallel — not sequential. Only use `depends_on` when a task literally needs the output of another task (e.g., synthesis needs all summaries). Unnecessary serialization kills the parallelism benefit.

**Anti-Pattern 2: Overloading concurrency beyond available resources.** Setting `concurrency: 100` on a machine with 4 cores causes massive context-switching overhead, slowing every sub-agent. The practical cap is 2-3× CPU cores; beyond that, each agent gets so little time-slice that total wall-clock time increases despite more parallelism.

**Anti-Pattern 3: Writing tasks with shared mutable state.** Sub-agents cannot safely write to the same file or database. If two sub-agents both append to `results.json`, the file will be corrupted from concurrent writes. Each sub-agent should write to its own output file (e.g., `results/task-1.json`), and a final aggregator task can merge them.

## When NOT to Use

- **Tasks with tight interdependencies (each step depends on the previous)**: A 10-step sequential pipeline doesn't benefit from parallelism. Use a single agent or a sequential workflow.
- **Tasks needing shared state or real-time communication between sub-agents**: Sub-agents are isolated by design. For collaborative multi-agent scenarios, use a different coordination pattern.
- **Small batches (1-2 tasks)**: The overhead of spawning sub-agents, monitoring, and aggregating results exceeds the sequential runtime for trivial batch sizes. Use a direct agent call instead.
- **External rate-limited APIs**: If all sub-agents call the same rate-limited API simultaneously, they'll all get rate-limited. Add random delays (`jitter_ms`) to task prompts or reduce concurrency to stay under rate limits.

## Cross-References

- **hermes-agent**: The agent runtime that powers each sub-agent — a sub-agent is essentially a short-lived hermes-agent invocation
- **deep-research**: For tasks that need serial deep investigation rather than parallel breadth — complementary pattern
- **research-paper-writing**: Frequently benefits from parallel sub-agents during the literature review phase
