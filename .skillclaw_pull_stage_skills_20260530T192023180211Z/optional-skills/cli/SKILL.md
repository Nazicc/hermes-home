---
name: cli
description: "Run 150+ AI apps via inference.sh CLI (infsh) — image generation, video creation, LLMs, search, 3D, social automation. Uses the terminal tool. Triggers: inference.sh, infsh, ai apps, flux, veo, image generation, video generation, seedream, seedance, tavily"
category: optional-skills
version: 1.0.0
...
author: okaris
...
license: MIT
...
metadata: {hermes: {related_skills: [], tags: [AI, image-generation, video, LLM, search, inference,
      FLUX, Veo, Claude]}}
---

# CLI Skill

Run 150+ AI apps via the `inference.sh` CLI (`infsh`).

## Core Commands

### Image Generation (Flux/SD)

infsh flux Schnell [--prompt "..."] [--aspect 1:1|16:9|9:16] [--seed N]
infsh flux Dev [--prompt "..."] [--steps N] [--aspect ...]


### Video Generation (Veo/Seedance)

infsh veo [--prompt "..."] [--aspect ...] [--duration 4|8]
infsh seedance [--prompt "..."] [--seed N]


### LLM Inference

infsh ollama <model> [--prompt "..."] [--system "..."]
infsh openai <model> [--prompt "..."] [--temp 0.7]


### Search

infsh tavily search [--query "..."] [--max 5]


## Tool Use

Use the `terminal` tool for all `infsh` commands.

## Skill Maintenance Workflow

When updating SKILL.md files (e.g., adding "Use when..." / "NOT for..." descriptions):

1. **Read with `read_file`** — always read the full file first, no limit, to capture exact content including YAML block scalars (`>`, `>-`, `|`)
2. **Handle empty reads** — if `read_file` returns empty content, the file may be inaccessible or empty. Do NOT attempt a patch. Instead:
   - Verify the file path is correct
   - Try reading with a higher limit
   - If still empty, skip the file and note it as needs-review
3. **Use `write_file` for persistence** — the `patch` tool may report success but not persist changes. Always verify with a follow-up read, and prefer `write_file` for critical updates
4. **Handle multiline descriptions** — YAML block scalars (`>`, `>-`) contain multiline content. Read carefully and preserve the block scalar format when modifying
