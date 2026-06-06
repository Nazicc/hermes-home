---
name: dspy
description: "Use when building complex AI systems with declarative programming, optimizing prompts automatically, or creating modular RAG systems and agents with DSPy (Stanford NLP's framework for systematic LM programming). Also use when you need to automatically optimize prompts or model weights from data, build multi-stage pipelines with typed signatures, or create self-improving AI systems. NOT for: simple prompting, non-declarative workflows, or when LangChain is preferred for simple chains."
category: mlops/research
version: 2.1.0
author: Stanford NLP + Orchestra Research
dependencies: [dspy-ai, openai, anthropic]
---

# DSPy - Declarative Language Model Programming

DSPy is Stanford NLP's framework for systematic LM programming. It separates programs (declarative flow) from parameters (LM prompts, weights), enabling automatic optimization of prompts and weights from data.

**GitHub Stars**: 22,000+ | **Created By**: Stanford NLP

## When to Use This Skill

Use DSPy when you need to:
- **Build complex AI systems** with multiple components and workflows
- **Program LMs declaratively** instead of manual prompt engineering
- **Optimize prompts automatically** using data-driven methods
- **Create modular AI pipelines** that are maintainable and portable
- **Improve model outputs systematically** with optimizers
- **Build RAG systems, agents, or classifiers** with better reliability

## Installation

```bash
# Stable release
pip install dspy-ai

# Or via dspy package name
pip install dspy

# Latest development version
pip install git+https://github.com/stanfordnlp/dspy.git

# With specific LM providers
pip install dspy-ai[openai]        # OpenAI
pip install dspy-ai[anthropic]    # Anthropic Claude
pip install dspy-ai[all]           # All providers
```

## Quick Start

### Basic Example: Question Answering

```python
import dspy

# Configure your language model
lm = dspy.Claude(model="claude-sonnet-4-5-20250929")
dspy.settings.configure(lm=lm)

# Define a signature (input => output)
class QA(dspy.Signature):
    """Answer questions with short factual answers."""
    question = dspy.InputField()
    answer = dspy.OutputField(desc="often between 1 and 5 words")

# Create a module
qa = dspy.Predict(QA)

# Use it
response = qa(question="What is the capital of France?")
print(response.answer)  # "Paris"
```

### Chain of Thought Reasoning

```python
import dspy

lm = dspy.Claude(model="claude-sonnet-4-5-20250929")
dspy.settings.configure(lm=lm)

class MathProblem(dspy.Signature):
    """Solve math word problems."""
    problem = dspy.InputField()
    answer = dspy.OutputField(desc="numerical answer")

cot = dspy.ChainOfThought(MathProblem)
response = cot(problem="If John has 5 apples and gives 2 to Mary, how many does he have?")
print(response.rationale)  # Shows reasoning steps
print(response.answer)     # "3"
```

## Core Concepts

### 1. Signatures

```python
# Inline signature (simple)
qa = dspy.Predict("question -> answer")

# Class signature (detailed)
class Summarize(dspy.Signature):
    """Summarize text into key points."""
    text = dspy.InputField()
    summary = dspy.OutputField(desc="bullet points, 3-5 items")
```

### 2. Modules

- **dspy.Predict** - Basic prediction
- **dspy.ChainOfThought** - Reasoning steps before answering
- **dspy.ReAct** - Agent-like reasoning with tools
- **dspy.ProgramOfThought / dspy.PAL** - Code-based reasoning
- **dspy.MultiChainComparison** - Compare multiple reasoning traces
- **dspy.Retrieve** - RAG retrieval

### 3. Optimizers (Teleprompters)

- **BootstrapFewShot** - Learn from examples
- **MIPRO** - Iterative prompt improvement
- **LabeledFewShot** - Direct example injection
- **COPRO** - Evolutionary prompt optimization
- **BootstrapFinetune** - Creates fine-tuning datasets
- **MIPROv2** - Improved MIPRO with better val set handling
- **GEPA** - Genetic programming optimizer

## Optimization Pipeline Debugging

Four class-level pitfalls that occur when running DSPy optimizers (especially GEPA, MIPROv2) with synthetic data.

### Pitfall 1: Synthetic Dataset Attrition

The LLM rarely returns the requested number of test cases. Three compound lossy steps:

1. **LLM under-delivers** — producing ~20-30 from a `num_cases=60` request
2. **Parser attrition** — JSON/repaired JSON/Markdown list cascade drops parse failures
3. **Empty-field filtering** — entries with null `task_input` or `expected_behavior` get dropped

**Result**: config says 60, reality is ~20 (e.g., 10 train / 5 val / 5 holdout) — too few for effective optimization.

**Fix**: batch generation and merge:
```python
all_examples = []
batch_size = 30
num_batches = max(1, n // batch_size)
for _ in range(num_batches):
    batch = llm_generate(prompt_with_count=batch_size)
    parsed = parse_and_filter(batch)
    all_examples.extend(parsed)
all_examples = all_examples[:n]
```

### Pitfall 2: Flat Fitness Metric (No Gradient)

Keyword overlap heuristics produce flat scores when `expected_behavior` is abstract:
```python
def cheap_metric(example, pred, trace=None):
    words_expected = set(example.expected_behavior.lower().split())
    words_output = set(pred.output.lower().split())
    overlap = len(words_expected & words_output) / max(len(words_expected), 1)
    return 0.3 + (0.7 * overlap)
```

All candidates score ~0.3 — the optimizer random-walks. **Fix**: verify gradient by comparing 5 baseline vs 5 perturbed scores. If within +/-0.05, upgrade to LLM-as-judge.

### Pitfall 3: Validation Set — Passed But Unrecorded

GEPA uses valset internally but **does not expose** its best validation score. MIPROv2's `.compile()` **does not accept valset** — it's silently dropped. **Fix** — explicit post-opt evaluation:
```python
val_scores = [metric(ex, optimized(**ex.inputs())) for ex in valset]
metrics["best_val_score"] = sum(val_scores) / len(val_scores)
```

### Pitfall 4: LLM Judge Is Dead Code

An `LLMJudge` class is defined with three-axis scoring but the DSPy `metric=` parameter points to a separate cheap function that never calls the Judge. **Verify**: trace what function the optimizer actually uses vs what evaluates holdout.

### Verification Checklist

Before declaring an evolution run successful:
1. Count actual generated examples (not configured count)
2. Test metric gradient — does it produce variation or all ~0.3?
3. Is `best_val_score` recorded in metrics.json or null?
4. Are holdout evaluator and optimizer metric different functions?

## See Also

- `references/modules.md` — Detailed module guide (Predict, ChainOfThought, ReAct, ProgramOfThought)
- `references/optimizers.md` — Optimization algorithms (BootstrapFewShot, MIPRO, BootstrapFinetune)
- `references/examples.md` — Real-world examples (RAG, agents, classifiers)
- `references/optimization-pipeline-debugging.md` — Full root-cause analysis from active debugging session covering synthetic data attrition, flat metric traps, and GEPA val set gaps