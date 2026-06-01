---
name: research-paper-writing
description: "Systematic workflow for reading, analyzing, critiquing, and writing academic research papers with structured synthesis."
category: research
metadata:
  hermes:
    tags: [research, writing, papers, academic, peer-review, literature-review]
    related_skills: [web-search, deerflow-command, parallel-cli, siyuan, simplestorage-adapter]
---

# Research Paper Writing

Systematic workflow for reading, analyzing, critiquing, and writing academic research papers with structured synthesis.

## Purpose

This skill provides a methodological framework for the entire research paper lifecycle — from initial paper discovery and critical reading through structured note-taking, argument construction, drafting, and revision. It is designed for researchers, students, and technical writers who need to produce high-quality academic papers, reviews, or technical reports.

## Why This Works

**Concept 1: The Three-Pass Reading Method.** Efficient paper review uses three progressive passes — from bird's-eye relevance check (5 min) to detailed content understanding (1 hour) to deep methodological critique (4+ hours). This prevents wasting deep-focus hours on papers that won't matter for your project, while ensuring thorough understanding of papers that do.

**Concept 2: Structured Note Storage.** Research notes should be stored in a queryable, linkable format (not linear text blobs). Using tools like SiYuan blocks or Obsidian notes with tags, links, and metadata creates a personal research graph that compounds in value over time as you add more papers — enabling cross-paper synthesis impossible with flat files.

## Examples

### Good Example 1: Three-Pass Reading and Structured Note-Taking

**Scenario:** You have 5 papers to evaluate for a literature review section. Use the three-pass method to efficiently assess and capture them.

```
Pass 1 (5 min per paper):
- Read title, abstract, figures, conclusion
- Check: Is this in scope? New enough? Trusted venue?
- Skip papers where answers to all three are "no"

Pass 2 (1 hour per paper):
- Read carefully with annotations
- Capture: 3 sentence Summary, Key claims (numbered), Evidence strength (Table), Open questions
- Store in structured note: [[Paper:2024:AuthorTitle]] with tags [#methodology] [#transformer]

Pass 3 (4+ hours per paper):
- Re-implement core claims mentally
- Identify hidden assumptions, statistical flaws, baseline weaknesses
- Write: Contribution (novel, incremental, or negative?), Reproducibility score (1-5), Future work ideas
```

**Good:** Follows a time-boxed progression rather than diving deep into every paper. Pass 1 acts as a funnel — only 2 of 5 papers survive to Pass 2, and only 1 to Pass 3. Each pass produces a structured, tagged note that can be searched and linked later.

### Good Example 2: Structured Paper Outline and Argument Map

**Scenario:** You need to write a 10-page conference paper with a clear narrative arc. Build the argument map before writing.

```
Argument Map Template:

[Problem] → [Gap] → [Proposal] → [Validation] → [Contribution/Ice]

Section-by-section:
1. Introduction (1 page): Hook + Problem + Our approach + Results preview + Contributions list
2. Related Work (1.5 pages): Thematic groups, not chronological. End with the gap statement.
3. Method (3 pages): Input → Process → Output. Clear enough that a peer can re-implement.
4. Experiments (3 pages): Dataset + Baselines + Metrics + Results table + Ablation study
5. Discussion (1 page): Why results look this way, limitations, failure cases
6. Conclusion (0.5 page): Summary, limitations, future work — NOT "In this paper we presented..."

Structure Checklist:
☐ Each section starts with a clear "what this section claims" sentence
☐ Each paragraph makes exactly one point (first sentence = topic sentence)
☐ Figures are drafted before prose (figures drive the narrative)
☐ Related Work ends with: "However, [gap], which this paper addresses."
```

**Good:** The argument map decouples structure from prose — you validate the logical flow before writing a single sentence. The checklist catches structural weaknesses early, saving rewrites.

### Bad Example 1: Writing Before Structuring

**Scenario:** You sit down to write a paper and start with the Introduction, writing paragraph by paragraph from the top.

```markdown
# Introduction
In this paper we present a novel approach to... [writes 300 words]
# Related Work
There are many approaches... [starts listing chronologically]
```

**Bad:** Writing without an argument map leads to circular logic, missing claims, and massive rewrites. The Introduction should be written LAST (or second-to-last) — you can't introduce what you haven't yet defined. The Related Work section organized chronologically instead of thematically fails to build the gap statement that motivates your contribution.

## Anti-Patterns

- **As-As Hedge Plague** — Replacing every declarative "X achieves 92%" with "as can be seen, as illustrated, as shown in Figure 3." Reviewers flag this as weasel-wording. Use active voice and let the results speak: "X achieves 92% accuracy (Table 1)."
- **Laundry-List Related Work** — Listing papers chronologically: "Smith 2021 did A, Jones 2022 did B, Lee 2023 did C." The reader must manually synthesize the narrative. Group by thematic approach and end each group with an explicit gap statement.
- **Zombie Figures** — Inserting a beautiful figure then never referencing it in the text. Figures are not decorations — every figure needs a prose anchor: "Figure 3 shows..." followed by the claim the figure supports.
- **Abstract First Fallacy** — Writing the abstract on day one of the paper. The abstract is the most-read part of any paper. If written first, it inevitably describes your original plan rather than what you actually found. Rewrite it last.
- **Limitations Omission Gambit** — Skipping the limitations section because "reviewers might reject it." The opposite is true: reviewers flag its absence as intellectual dishonesty. A candid limitations section pre-empts reviewer criticism and shows you understand your method's boundaries.

## When NOT to Use

- **Non-academic writing**: Blog posts, documentation, and internal memos need different structures. Use technical writing skills instead.
- **First-draft brainstorming**: Argument maps assume you have ideas. For ideation, use mind mapping or freewriting first.
- **Code documentation**: API docs, changelogs, and READMEs follow different conventions. Use code-writing skills.
- **Grant proposals**: Funding proposals prioritize feasibility, budget, and impact over methodological rigor. Use grant-writing templates.
- **Peer review reports**: Reviewing a single paper (vs. writing one) needs a shorter, more critical format — use peer-review skills.
- **Conference talk abstracts**: These prioritize hooks over rigor. A talk abstract is 150 words and sells excitement, not methodology.
- **Pre-print posting (arXiv)**: The submission process focuses on formatting and licensing, not paper structure. Use submission checklists.

## Cross-References

- **web-search** (skills/planning-with-files/SKILL.md) — For discovering papers and related work. Use systematic search queries to build a comprehensive literature review before writing.
- **deerflow-command** (deerflow-commander/SKILL.md) — For AI-assisted research and paper analysis. Use DeerFlow to summarize papers, extract claims, and suggest related work.
- **parallel-cli** (optional-skills/parallel-cli/SKILL.md) — Speed up paper batch processing. Run Three-Pass Reads on multiple papers concurrently, downloading and analyzing PDFs in parallel.
- **siyuan** (siyuan/SKILL.md) — For storing structured research notes and paper annotations in a queryable knowledge base. Use SiYuan blocks to tag, link, and cross-reference paper summaries.
- **simplestorage-adapter** (memory/simplestorage-adapter/SKILL.md) — For persistent storage of paper notes and research state across sessions. Store structured research databases for retrieval.
