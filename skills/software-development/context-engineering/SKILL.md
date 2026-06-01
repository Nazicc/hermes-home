---
name: context-engineering
description: "Optimizes agent context setup using structured context management techniques. Use when starting a new session, when agent output quality degrades, when switching between tasks, or when configuring rules files and project context."
category: general
---

## Purpose

Context Engineering is the practice of deliberately structuring, pruning, and refreshing the agent's working context to maintain output quality across long sessions. Context is not about volume — it is about relevance, accuracy, and timely injection. This skill provides a systematic framework (detect → audit → repair → prevent) for keeping the agent's context window clean and effective.

Use this skill when:
- You start a new session and want the agent to hit the ground running
- Agent output quality degrades mid-session (repetition, forgotten constraints, incoherence)
- You switch between tasks and need to reset the agent's focus
- You discover the agent is working with stale or inaccurate information
- You are configuring project rules files for team consistency

## Context

The agent operates within a finite context window. As the conversation grows, earlier information is compressed or lost. Without deliberate context management, the agent will:

- **Repeat itself** — because it no longer knows what was already said
- **Forget constraints** — because they scrolled out of the window
- **Ignore parts of the request** — because the task got buried in history
- **Contradict itself** — because conflicting rules or assumptions exist in different parts of the context

**Context Layers (outermost to innermost)**

1. **System prompt** — static identity, capabilities, hard rules
2. **Session rules** (`~/.hermes/rules/`) — project-specific overrides
3. **Conversation history** — full transcript, compressed when >50 messages
4. **Working memory** — agent's active focus, todo list, current task
5. **Task context** — specific files, docs, URLs relevant to current task

**Loading Order**

System prompt → Session rules → Conversation history → Working memory → Task context

## Candidates

Choose the right intervention based on what you observe:

| Symptom | Root Cause | Best Intervention |
|---------|-----------|------------------|
| Agent repeats itself | History too long or compressed badly | Summarize and restart subtopic |
| Agent forgets constraints | Rules not loaded or overridden | Re-state rules explicitly |
| Agent loses track of task | Context switched without summary | Inject task summary |
| Output quality drops | Context window near limit | Compress or prune history |
| Agent contradicts itself | Conflicting rules loaded | Audit and deduplicate rules |

## Guidance

**Phase 1 — Detect Context Degradation**

Before adding more context, verify the problem is actually context-related:

1. Check the agent's last response — does it show awareness of ALL provided context?
2. **If yes** — the issue is NOT context (proceed with task execution)
3. **If no** — context degradation confirmed (proceed to Phase 2)

**Phase 2 — Audit Context Quality**

Strip non-essentials before adding more:

1. Remove outdated project state references
2. Remove completed sub-task history irrelevant to current decisions
3. Remove generic preamble that doesn't constrain behavior
4. **Keep**: current goal, active constraints, relevant code patterns, error state
5. **Limit**: retain at most 20 historical messages in the active window

**Phase 3 — Inject Targeted Context**

| Gap | Context to Add |
|-----|----------------|
| Agent doesn't know project structure | `find . -name "*.py" | head -20` + key file summaries |
| Agent ignores a constraint | State it as a concrete rule |
| Agent repeats failed approaches | Log what was tried + why it failed |
| Agent misunderstands the goal | One-sentence restatement of desired outcome |

**Injection Techniques:**

- **Explicit framing** — state task, success criteria, constraints, relevant context upfront
- **Task framing template**: `Task: <goal> | Success: <criteria> | Constraints: <limits> | Context: <key info>`
- **Conversation summarization** — when history >30 messages, summarize in 3-5 bullet points: keep goal + key decisions + open questions; discard failed attempts and off-topic detours

**Phase 4 — Rules Files**

For recurring projects, create persistent rules in `~/.hermes/rules/<project>/`:

- `system.md` — project-specific system prompt additions
- `ignore.md` — patterns to skip (e.g., `node_modules`, `.git`)
- `preferences.md` — user preferences (language, style, tools)

Rules files should be loaded at session start, not mid-task.

**BDI Mental Models (Multi-Agent Context)**

When the agent proxies for other agents or services:
- **Beliefs** — what the agent believes about the world (from context)
- **Desires** — what the agent wants to achieve (from task + user goals)
- **Intentions** — what the agent decides to do next (from planning)

Re-evaluate BDI state when new info contradicts a belief, a sub-goal completes, or the user changes the task.

## Why This Works

Context Engineering works because it exploits a fundamental property of transformer-based agents: **attention is a finite resource**. Every token in the context window competes for the agent's attention. Irrelevant tokens dilute relevant signals, causing the agent to miss critical constraints, repeat itself, or produce incoherent output.

**The Core Mechanism: Signal-to-Noise Ratio (SNR) in the Attention Window**

An agent's context window is effectively a fixed-size attention buffer. When it fills with noise (off-topic history, stale state, redundant preamble), the SNR drops and output quality degrades. Context Engineering systematically:

1. **Removes noise** — pruning stale history, deduplicating rules, discarding irrelevant detail
2. **Amplifies signal** — framing the task explicitly, injecting targeted context, loading project rules at startup
3. **Prevents re-pollution** — creating permanent rules files, summarizing before switching tasks

**Why summarization beats raw history:** A 50-message conversation about debugging might contain 30 messages of failed attempts the agent already knows failed, interspersed with 3 key findings. Raw history forces the agent to re-attend to all 50 messages; a 5-bullet summary preserves the 3 findings at 10% of the token cost. The agent gets all the signal without the noise.

**Why rule files outperform inline instructions:** Inline instructions compete with the task for attention and are easily buried. Rule files loaded at session start are treated as system-level context, giving them higher priority in the agent's attention ordering. They persist across task switches without being repeated.

**Why the BDI model helps multi-agent workflows:** When one agent delegates to another, beliefs and intentions must transfer cleanly. An explicit BDI dump prevents the "telephone game" — each downstream agent reconstructs the correct world state instead of inferring it from a conversation summary that may have lost critical context.

## Examples

**Good:** Starting a new session with full context setup

Situation: You're starting a new Hermes session to fix a PyPI publication bug.
```
Task: Fix PyPI publication failing on 403 Invalid Auth
Success: `twine upload dist/*` exits 0
Constraints: Must use TestPyPI first. API token in env var TWINE_PASSWORD.
Context: /Users/can/projects/hermes-agent, pyproject.toml
```
Result: Agent produces correct output from the first response — knows the project, the constraint (TestPyPI first), and the auth mechanism. No back-and-forth needed to explain basic context.

---

**Bad:** Jumping straight to technical details without context setup

Situation: You say "Fix the PyPI 403 error" and paste the traceback.
Result: Agent tries six different approaches (API key format, .pypirc config, token scope, ~/.netrc, OIDC, warehouse permissions) before you mention "oh, use TestPyPI first — and the token is in TWINE_PASSWORD." The first four approaches wasted 20+ messages of context.

---

**Good:** Mid-session context recovery when quality degrades

Situation: After 40+ messages of debugging, the agent starts forgetting constraints.
```
Summarize: We've been debugging the PyPI 403 error.
Key findings:
- TestPyPI accepts the token fine
- Prod PyPI rejects it with 403
- Token has the `pypi-api` scope confirmed
Next step: regenerate the token on PyPI admin panel and retry.
```
Result: Agent continues with a clean mental model. The 3 findings are preserved, the 30+ failed attempts are discarded.

---

**Bad:** Piling on more context without pruning

Situation: Quality degraded, so you paste in more logs, more config files, and more error messages.
Result: Agent's context window fills further. SNR drops worse. Output becomes more confused. You've made the problem worse by adding signal AND noise in equal measure.

---

**Good:** Creating permanent rules files

Situation: You work on 3 projects regularly — a Django web app, a FastAPI microservice, and a CLI tool in Go.
```
# ~/.hermes/rules/django-app/system.md
Project: Django e-commerce API
Conventions: DRF serializers, pytest with factory_boy, pre-commit hooks
Auth: JWT via django-rest-framework-simplejwt
DB: PostgreSQL with django-tenants for multi-tenancy
```
Result: Every session on this project starts with correct conventions. No need to remind the agent about Django or DRF patterns.

---

**Bad:** Relying on system prompt + raw conversation for project knowledge

Situation: No rules files. You tell the agent "we use DRF serializers" in message 3, then "pytest with factory_boy" in message 10, then "django-tenants for multi-tenancy" in message 25.
Result: By message 30, the agent has seen each convention once and has no structured way to recall them. It defaults to generic Django patterns and produces non-standard code.

---

**Good:** BDI dump before delegating to a subagent

Situation: You're delegating a subtask to a DeerFlow research agent.
```
Beliefs: The PyPI 403 error is a scope/permission issue, not a credential format issue. Token works on TestPyPI.
Desires: Publish the package to prod PyPI using the existing token or a new one.
Intentions: Regenerate the token with correct scopes, retry publish.
```
Result: DeerFlow understands the exact state without reading 50 messages of history. No context loss in delegation.

## When NOT to Use

- **Trivial one-off tasks** (single file edit, simple query) — context setup overhead exceeds benefit
- **Already well-scoped implementations** — if the task fits in one response, context engineering adds delay
- **Agent already has all necessary context** — running the full detect→audit→repair cycle when context is already clean wastes time
- **Emergency production fixes** — pause context optimization, fix the immediate issue, clean up later
- **Memory-only systems** — if you're using a stateless prompt (e.g., single API call), context engineering does not apply

## Anti-Patterns

**"Context is fine as-is"** — If output quality has degraded, audit and clean. Assuming it's fine is the number one cause of context-induced failure. Verify with the Phase 1 detect cycle, don't assume.

**"More context is better"** — Every irrelevant token dilutes relevant signals. Quality beats quantity. A 20-message clean context outperforms a 50-message bloated one.

**"I'll just dump all files in context"** — Token limits are real. Selectively add only the files and sections relevant to the current task. Dumping the whole codebase costs tokens with no benefit.

**"The agent should know the project by now"** — Each session starts fresh. What you told the agent in session 1 is not available in session 10. Persistent rules files are the solution, not assumptions.

**"I told it once, it should remember"** — The agent's context window is limited. Repetition of critical constraints at strategic points (session start, task switch, before delegation) is necessary and productive.

**"I can infer the project structure"** — Inference is error-prone. Explicit rules are faster and more accurate. A 3-line rule file beats 10 messages of back-and-forth clarifying conventions.

**"I'll add context as I go"** — Proactive context setup at session start avoids mid-task degradation. Reactively adding context after quality drops wastes the messages between the drop and the fix.

**"I'll just restart the session"** — Restarting loses working context. Session restoration through summarization preserves what matters. Only restart when pollution is severe (window completely filled with noise).

**"Context management is the user's job"** — The agent should proactively maintain its own context quality: summarize when history grows, detect when context degrades, and suggest context improvements when output quality drops.

## Cross-References

- **`spec-driven-development`** (`skills/spec-driven-development/SKILL.md`) — Specs are a form of task context; load them early in the context setup phase.
- **`systematic-debugging`** (`skills/systematic-debugging/SKILL.md`) — When context degradation causes bugs, debug the context first before debugging the code.
- **`deerflow-commander`** (`skills/deerflow-commander/SKILL.md`) — Use context engineering to prepare clean context before delegating research to DeerFlow.
- **`writing-plans`** (`skills/writing-plans/SKILL.md`) — Plans serve as structured task context; load them into the agent's context at session start.
- **`planning-with-files`** (`skills/planning-with-files/SKILL.md`) — Use file-based planning for complex multi-session tasks that need persistent context across sessions.
