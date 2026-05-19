---
name: fireworks-tech-graph
description: "Use when the user wants to create any technical diagram - architecture, data flow, flowchart, sequence, agent/memory, or concept map - and export as SVG+PNG. Trigger on: \"画图\" \"帮我画\" \"生成图\" \"做个图\" \"架构图\" \"流程图\" \"可视化一下\" \"出图\" \"generate diagram\" \"draw diagram\" \"visualize\" or any system/flow description the user wants illustrated. NOT for: artistic illustrations, non-technical diagrams, or UML class diagrams (use plantuml instead)."
category: diagrams
---

# fireworks-tech-graph

> Generate production-quality SVG technical diagrams from natural language descriptions. 7 built-in visual styles. Export to SVG + PNG.

## At a Glance

| | |
|---|---|
| **What** | SVG+PNG technical diagram generator driven by JSON fixture templates and style presets |
| **How** | `generate-from-template.py` renders a diagram from a fixture JSON using the selected style's visual language |
| **Output** | SVG (vector, editable) + PNG (1920px wide, via `rsvg-convert`) |
| **Styles** | 7: Flat Icon, Dark Terminal, Blueprint, Microservices, Memory Types, Glassmorphism, Claude Official, OpenAI Official |
| **Diagram Types** | system-architecture, api-flow, agent-memory, tool-call, multi-agent, mem0, microservices, etc. |

---

## Quick Start

bash
# 1. Ensure dependency
brew install librsvg   # provides rsvg-convert

# 2. Generate a diagram from a fixture (example: Mem0 architecture, style 1)
cd ~/.hermes/skills/diagrams/fireworks-tech-graph
python3 ./scripts/generate-from-template.py memory ./out.svg "$(cat fixtures/mem0-style1.json)"

# 3. Convert to PNG
rsvg-convert -w 1920 -h 1080 -f png ./out.svg -o ./out.png

# 4. Or use the batch test script to render all 7 style fixtures
./scripts/test-all-styles.sh


---

## Core Scripts

### generate-from-template.py

Renders a diagram from a JSON fixture using a named visual style. This is the primary generation entry point.

bash
python3 ./scripts/generate-from-template.py <template-type> <output-svg> [data-json-string]


**Arguments:**
- `template-type` — one of: `memory`, `system-architecture`, `api-flow`, `agent-memory`, `tool-call`, `multi-agent`, `microservices`
- `output-svg` — path to write the SVG file
- `data-json-string` — JSON payload (can be passed via process substitution as shown above)

**Environment:** runs from the skill directory (`~/.hermes/skills/diagrams/fireworks-tech-graph`).

### generate-diagram.sh

Shell wrapper that validates the SVG and exports PNG in one command.

bash
./scripts/generate-diagram.sh <input-svg> [output-png]
# Defaults: output-png = ${input-svg%.svg}.png


**Requirements:** `rsvg-convert` must be on PATH.

### validate-svg.sh

Checks SVG syntax and reports tag-balance, quote, and entity errors.

bash
./scripts/validate-svg.sh <svg-file>


### test-all-styles.sh

Batch regression test — renders all 7 style fixtures, validates each SVG, and exports PNG. Reports pass/fail per style.

bash
./scripts/test-all-styles.sh


---

## Available Styles

| # | Style Name | Visual Language |
|---|---|---|
| 1 | Flat Icon | Colored fills, subtle shadows, rounded corners, educational palette |
| 2 | Dark Terminal | Dark background (#0d1117), monospace font, green/cyan accents |
| 3 | Blueprint | Blueprint blue (#1e3a5f), dashed grids, serif title, technical feel |
| 4 | Memory Types | Color-coded by memory layer, clean sans-serif, architectural boxes |
| 5 | Glassmorphism | Translucent frosted-glass panels, blur, soft gradients |
| 6 | Claude Official | Warm minimalist, muted tones, clear hierarchy |
| 7 | OpenAI Official | White/light background, brand-aligned typography, clean lines |

---

## Fixture JSON Schema

Each fixture JSON defines `template_type`, `style`, `width`, `height`, `title`, `subtitle`, `containers[]`, `connections[]`.


{
  "template_type": "memory",
  "style": 1,
  "width": 1080,
  "height": 760,
  "title": "Mem0 Memory Architecture",
  "subtitle": "Personalized AI Memory Layer",
  "containers": [
    {
      "x": 30, "y": 84, "width": 1020, "height": 120,
      "label": "User Query", "type": "input", "style": {...}
    }
  ],
  "connections": [
    {
      "from_idx": 0, "to_idx": 1,
      "label": "Embed", "style": {...}
    }
  ]
}


See `fixtures/*.json` for complete examples (mem0, api-flow, tool-call, multi-agent, microservices, system-architecture, agent-memory-types).

---

## Deployment Checklist

After installing this skill, verify:

- [ ] `rsvg-convert` is installed: `which rsvg-convert` → `/opt/homebrew/bin/rsvg-convert`
- [ ] Skill directory landed: `ls ~/.hermes/skills/diagrams/fireworks-tech-graph/SKILL.md`
- [ ] Scripts are executable: `ls -l scripts/*.sh`
- [ ] Test pass: `cd ~/.hermes/skills/diagrams/fireworks-tech-graph && ./scripts/test-all-styles.sh`

**If `test-all-styles.sh` fails with "No such file or directory":**
- The skill directory may not have been copied correctly. Re-copy with:
  python
  import shutil, os
  shutil.copytree('/tmp/fireworks-tech-graph',
                  os.path.expanduser('~/.hermes/skills/diagrams/fireworks-tech-graph'),
                  dirs_exist_ok=True)
  
- Or re-clone: `gh repo clone yizhiyanhua-ai/fireworks-tech-graph /tmp/fireworks-tech-graph`

---

## Reference Files

| Path | Purpose |
|---|---|
| `SKILL.md` | This file |
| `README.md` / `README.zh.md` | Full documentation in English / Chinese |
| `references/*.md` | Style guide references |
| `templates/` | SVG template snippets |
| `agents/openai.yaml` | Agent config example |
| `fixtures/*.json` | Regression test fixtures |

---

## Related Skills

- `concept-diagrams` — flat minimal light/dark SVG diagrams as standalone HTML
- `excalidraw` — hand-drawn style collaborative diagrams
- `architecture-diagram` — generic architecture diagram generation

