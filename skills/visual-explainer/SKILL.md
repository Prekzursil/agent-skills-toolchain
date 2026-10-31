---
name: visual-explainer
description: Use when a visual explanation beats prose — diagrams, architecture overviews,
  diff or plan reviews, project recaps, comparison tables, dashboards, timelines,
  or HTML slide decks. Generates one self-contained HTML page (embedded CSS/JS, interactive
  Mermaid) that explains systems, code changes, plans, data, or technical concepts.
permalink: dqverify-repo-20261013/skills/visual-explainer/skill
---

<!-- Source: cherry-picked from https://github.com/coco-research/coco (skills/visual-explainer, MIT, author nicobailon, v0.8.1) on 27.08.2026 per grill decision G-11/11B. Adapted to house format; coco template/reference files not ported — all invariants needed to build pages from scratch are inlined below. -->

# Visual Explainer

Generate self-contained HTML pages that explain systems, code changes, plans, data, and technical concepts visually.

## Trigger and delivery rules

- Prefer an HTML page over terminal ASCII when the output is inherently visual.
- If a table would have 4+ rows or 3+ columns, render it as HTML and give only a short chat summary.
- Write files to the active project's `docs/` or `output/` folder (or an explicitly requested path). Use descriptive filenames.
- Open generated pages in the browser when running normally.
- The final page must be a complete self-contained HTML document, including embedded CSS and any needed JS.

## Choose the representation

| Content | Default representation |
|---|---|
| Flowchart, pipeline, state machine, decision tree | Mermaid |
| Sequence, ER/schema, class, C4, topology-focused architecture | Mermaid |
| Text-heavy architecture, module internals, implementation plans | CSS grid cards, optionally with a Mermaid overview |
| 15+ element architecture | Hybrid: small Mermaid overview + CSS detail cards |
| Comparison/audit/status matrix | Semantic HTML `<table>` |
| Timeline/roadmap | CSS timeline |
| Dashboard/metrics | CSS grid + charts/KPIs |
| Slide deck | `100dvh` slides |

## Mermaid invariants

- Use `theme: 'base'` with custom `themeVariables` matching the page palette.
- For complex diagrams use ELK layout when available.
- Wrap every diagram in a shell: `.diagram-shell` > `.mermaid-wrap` > `.zoom-controls` + `.mermaid-viewport` > `.mermaid-canvas`.
- Every Mermaid diagram needs zoom in/out/reset/expand controls, Ctrl/Cmd+scroll zoom, drag panning, and click-to-expand.
- Prefer `flowchart TD` for complex diagrams. Use `LR` only for simple 3–4 node linear flows.
- Use `<br/>` in quoted flowchart labels. Do not use escaped `\n` labels.
- Never define page-level `.node`; Mermaid uses it internally. Use namespaced page classes such as `.ve-card`.
- For 15+ elements, do not cram everything into one Mermaid diagram. Use the hybrid overview + cards pattern.

## Layout and style invariants

- Use semantic HTML where it helps accessibility and copy/paste: headings, lists, `<table>`, captions.
- Use CSS custom properties for palette: `--bg`, `--surface`, `--border`, `--text`, `--text-dim`, and 3–5 accents.
- Pick a clear aesthetic direction before writing: blueprint, editorial, paper/ink, terminal, IDE-inspired, or data-dense.
- Avoid generic defaults: no body font that is only Inter, Roboto, Arial, Helvetica, or system-ui; no violet/fuchsia Tailwind-default accents as the main palette (`#8b5cf6`, `#7c3aed`, `#a78bfa`, `#d946ef`); no cyan+magenta+purple neon dashboard; no gradient-mesh blobs.
- Good font pair families: DM Sans + Fira Code; Instrument Serif + JetBrains Mono; IBM Plex Sans + IBM Plex Mono; Bricolage Grotesque + Fragment Mono; Plus Jakarta Sans + Azeret Mono.
- Good accent directions: terracotta+sage, teal+slate, rose+cranberry, amber+emerald, deep blue+gold.
- Prevent overflow: `min-width: 0` on grid/flex children, `overflow-wrap: break-word` for long text, and scroll containers for wide tables/code.
- Do not set `display: flex` directly on `<ul>`/`<ol>` when list markers matter.
- Use depth sparingly: hero/elevated only for primary sections; flat/recessed for reference material.
- Use entrance/hover animation only when it clarifies hierarchy. Respect `prefers-reduced-motion`. No continuous glow, pulse, or breathing effects on static content.
- Pages with 4+ major sections get a sticky/side navigation.

## Slide deck mode

Use slides only when explicitly requested. Slides are a different medium, not a paginated article:

- Each slide is one viewport (`100dvh`) with no page-level scrolling.
- Larger type, fewer objects per slide, varied compositions, visible navigation.
- Include slide nav chrome: prev/next controls, slide count, keyboard navigation, and carousel dots/indicators.
- Before writing HTML, inventory the source and map every source item to slides.
- Do not drop content to fit a fixed slide count. Add slides instead.
- Slide types to vary between: Title, Section Divider, Content, Split, Diagram, Dashboard, Table, Code, Quote, Full-Bleed.

## Final checklist

Before delivery, verify:

- complete HTML document, written to the requested path;
- no console errors when opened; no horizontal overflow at normal desktop width;
- fonts load with fallbacks; tables preserve rows/columns and wrap long text;
- Mermaid diagrams use the diagram shell with zoom/pan/expand;
- slides fit one viewport, include carousel dots, and preserve source coverage;
- visual hierarchy makes the main idea obvious in the first viewport;
- styling would still be recognizable if compared against a generic dark/violet template.