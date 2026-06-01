---
name: baoyu-infographic
description: "Generate professional infographics with 21 layout types and 21 visual styles. Analyzes content, recommends layout×style combinations, and generates publication-ready infographics. Use when user asks to create \"infographic\", \"visual summary\", \"信息图\", \"可视化\", or \"高密度信息大图\". Also use when you need to create visual diagrams, charts, concept maps, or graphic infographics, or convert text-based content into visual representations."
category: general
---

# Infographic & Visual Generation

## Overview

This skill handles the creation of visual diagrams, charts, concept maps, and graphic infographics. Analyzes content, recommends layout×style combinations, and generates publication-ready infographics with 21 layout types and 21 visual styles.

## Use When

- You need to create a visual diagram from text or data
- You need to convert structured information into a graphic representation
- You need concept maps, flowcharts, or visual summaries
- Asked to create "infographic", "visual summary", "信息图", "可视化", or "高密度信息大图"

## NOT for

- General-purpose shell scripting or file manipulation
- Agent health monitoring, cron job execution, or system maintenance
- Code generation, debugging, or repository exploration

## Supported Tools

- **Excalidraw**: Best for hand-drawn style diagrams and collaborative editing
- **Concept Diagrams**: Structured diagram generation from text descriptions
- **ASCII Art**: Text-based visual output for terminal environments
- **Meme Generation**: Humorous visual content from templates

## Common Workflow

1. Identify the information to visualize
2. Select the appropriate visual tool based on style and use case
3. Provide structured input (text, data, or description)
4. Generate and optionally save the output

## Diagnostic

### read_file returns empty content
If a `read_file` call returns empty content for a file you expect to exist:
1. Verify the file path is correct (check for typos, ~ expansion issues)
2. Use the terminal as a fallback: run `cat <path>` or `ls -la <parent-dir>`
3. If the file does not exist, the terminal output will confirm this explicitly
4. Do NOT keep re-calling read_file with the same path — switch to the terminal immediately

### Tool returns unexpected empty result
- Check that the input format matches the tool's expected schema
- Verify the tool is available in the current environment
- Try an alternative tool from the supported list above

## Purpose

Transform structured information, data, or concepts into professional, publication-ready infographics using 21 layout types × 21 visual styles. Baoyu analyzes the input content, recommends the optimal layout×style combination, and renders a high-density visual summary — bridging the gap between raw text/data and a polished one-page graphic that communicates at a glance.

## Why This Works

**Concept 1: Layout × style combinatorial matrix.** With 21 layout types (timeline, flowchart, comparison, hierarchy, grid, radial, etc.) × 21 visual styles (minimalist, hand-drawn, cyberpunk, corporate, watercolor, isometric, etc.), Baoyu can match virtually any content type to an appropriate visual treatment without requiring the user to be a designer.

**Concept 2: Content-aware recommendation.** Baoyu doesn't apply a one-size-fits-all template — it first classifies the input (chronological data → timeline, comparative data → split layout, hierarchical data → tree/radial) and then recommends the top 3 layout×style combinations ranked by suitability score. This removes decision fatigue.

**Concept 3: Multi-tool backend.** Baoyu dispatches to Excalidraw (hand-drawn, collaborative), Concept Diagrams (structured, text-driven), ASCII Art (terminal-friendly), or Meme Generation (humorous) depending on the use case and output format needed. This prevents being locked into one rendering engine.

## Examples

**Good: Timeline infographic for project milestones**
```python
# Input: structured milestone data
milestones = [
    ("Jan 2025", "Research phase — 3 user studies"),
    ("Mar 2025", "MVP prototype — 2-week sprint"),
    ("Jun 2025", "Beta launch — 500 users"),
    ("Sep 2025", "Public release — 10K users"),
]
# Baoyu detects timeline data → recommends Layout: Timeline + Style: Minimalist
# → Generates horizontal timeline with milestone markers and annotations
```

**Bad: Dumping an unstructured paragraph and expecting magic**
```python
# WRONG: One massive paragraph
input_text = "We started in January 2025 doing research with 3 user studies and then in March we built an MVP in 2 weeks..."
```
**Bad:** No structure extracted. Baoyu cannot infer which dates are milestones, which events are significant, or what the hierarchy is. Pre-process dense paragraphs into key-value pairs, tables, or bullet lists first.

---

**Good: Comparison infographic for product features**
```python
# Input: comparative data
comparison = {
    "title": "Free vs Pro Plan",
    "rows": [
        ("Storage", "5 GB", "100 GB"),
        ("Users", "1", "Unlimited"),
        ("API Calls", "1K/day", "100K/day"),
        ("Support", "Email", "24/7 Phone"),
    ]
}
# Baoyu detects comparison data → Layout: Split Comparison + Style: Corporate
# → Side-by-side feature matrix with visual indicators (check/cross)
```

**Bad: 10-table comparison with 50 rows each**
```python
# WRONG: Overloading a single comparison layout
comparison = {"title": "20 SaaS Tools", "rows": [(tool, *features) for tool in 20_tools]}
```
**Bad:** A single comparison grid with 20 rows and 30 columns is too dense. Baoyu's output becomes unreadable. Split into category-specific infographics (e.g., "Analytics Tools," "Design Tools") each with 5–8 rows.

---

**Good: Concept map for a technical topic**
```
# Input: text description of "How Docker Works"
# Baoyu extracts entities and relationships:
# Containers → share host OS kernel → isolated processes
# Images → layers → read-only filesystem
# Dockerfile → build → image registry → pull → run
# → Layout: Concept Map (radial) + Style: Hand-drawn via Excalidraw
```

**Bad: "Cyberpunk" style for a corporate quarterly report**
```
# WRONG: Style mismatch with audience
# Layout: Timeline + Style: Cyberpunk
# → Generated for a board of directors presentation
```
**Bad:** The neon, glitch aesthetic of Cyberpunk directly contradicts the conservative context of a board meeting. Baoyu's recommendation should be overridden to Corporate or Minimalist when audience context demands it.

---

**Good: Data-driven infographic from CSV/JSON**
```
# Baoyu reads structured data file
# → Detects 5 data dimensions
# → Recommends Layout: Grid Dashboard + Style: Dark Mode
# → Generates multi-panel infographic with charts, KPIs, annotations
```

## Anti-Patterns

**Anti-Pattern 1: Dumping raw text without structure.** Passing an unstructured paragraph and expecting a perfect infographic. Baoyu works best with structured input (bullets, tables, JSON, key-value pairs). Pre-process dense paragraphs by extracting entities, relationships, and hierarchies first.

**Anti-Pattern 2: Overloading a single layout.** Forcing a timeline layout to show 50 milestones with 200-word descriptions each. Infographics are about density with clarity — if the content exceeds one page, split into multiple infographics or use a flowchart layout that supports deep hierarchies.

**Anti-Pattern 3: Ignoring the style-to-audience match.** Using "Cyberpunk" style for a corporate quarterly report or "Watercolor" for a technical architecture diagram. The style must reinforce the content's purpose. Baoyu's recommendation engine ranks by suitability, but the agent should override if the audience context demands a different tone.

**Anti-Pattern 4: Expecting pixel-perfect typography.** While Baoyu generates polished layouts, it is not a vector editing tool (Illustrator, Figma). For final polish — custom fonts, exact kerning, brand-specific colors — export and refine in a dedicated design tool.

## When NOT to Use

- **Vector illustration or custom artwork** — infographics are data-driven layouts. For original illustration, use an illustration tool (Illustrator, Procreate, Midjourney).
- **Interactive data dashboards** — Baoyu generates static images. For interactive exploration, use Tableau, Power BI, or Observable D3.
- **Animation or motion graphics** — the output is a static PNG/SVG. For animated infographics, use After Effects, Lottie, or HTML/CSS animations.
- **Raw data analysis** — if the user needs to explore, filter, or compute statistics, use a data analysis tool (pandas, Excel) first. Feed Baoyu the *conclusions*, not the raw dataset.
- **Code architecture diagrams** — for system architecture, networking diagrams, or UML, use dedicated tools (Draw.io, Mermaid, PlantUML) that support formal notation and auto-layout.
- **Real-time collaborative whiteboarding** — Baoyu generates one-off graphics. For live brainstorming with a team, use Miro, FigJam, or Excalidraw directly.
- **Pixel-perfect brand-compliant typography** — Baoyu uses system fonts and default styling. For exact brand font, custom kerning, or precise color hex alignment, export to Figma/Illustrator for final polish.
- **Single-line text formatting** — if the user only needs bold text, a bullet list, or a table in Markdown, use native Markdown formatting — not an infographic tool.

## Cross-References

- **meme-generation** (meme-generation/SKILL.md) — For humorous visual content and meme-style overlays when tone is comedic rather than informative
- **songsee** (media/songsee/SKILL.md) — Spectrogram/audio visualization output that can be embedded into baoyu infographic layouts
- **touchdesigner-mcp** (optional-skills/touchdesigner-mcp/SKILL.md) — Real-time creative coding output that can serve as visual elements in infographics
- [Excalidraw](https://excalidraw.com/) — Hand-drawn style diagrams, Baoyu's primary rendering backend
- [Mermaid.js](https://mermaid.js.org/) — Text-to-diagram engine for flowcharts, sequence diagrams, Gantt charts
- Edward Tufte, [*The Visual Display of Quantitative Information*](https://www.edwardtufte.com/tufte/books_vdqi) — Foundational principles for high-density data visualization
- [Canva Infographic Templates](https://www.canva.com/create/infographics/) — Reference design patterns for layout×style combinations
