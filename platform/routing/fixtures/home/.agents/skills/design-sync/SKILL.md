---
name: design-sync
description: "Use when design sync is needed. Push a local component library to a claude.ai/design design-system project incrementally — one component at a time, never a wholesale replace. Builds self-contained @dsCard preview HTML bundles, validates the card manifest, then drives the DesignSync MCP push flow."
origin: forged (FORGE-DISCIPLINE 2026-06-30)
---

# design-sync — push a component library to claude.ai/design

Keep a local component library in sync with a **Claude Design** project (`claude.ai/design`)
through the **DesignSync** MCP tool. The unit of sync is a **preview card**: a self-contained
HTML file whose first line carries a `@dsCard` marker. The Design System pane builds its card
index from those markers (compiled into `_ds_manifest.json` by the app's self-check), so a
well-formed bundle uploads with no explicit asset registration.

> This is a **distilled, harness-local** version of Anthropic's built-in `/design-sync` skill
> (ships inside Claude Code >= 2.1.176, paired with the `DesignSync` tool). The full upstream
> skill adds a Storybook "fidelity oracle" compare loop and a converter that bundles a package's
> compiled `dist/` into `_ds_bundle.js`. Use this distilled version for hand-authored or
> framework-extracted bundles; reach for the upstream Storybook flow when you have a real
> Storybook to pixel-match against. See `component-extract` (companion skill) to GENERATE the
> bundle this skill uploads.

## When to use

- Sync a UI kit / component library / shadcn registry to a Claude Design design-system project.
- Refresh specific components in an existing design-system project (incremental, not replace).
- Mirror a Storybook or a live app's components as preview cards in Claude Design.

## The hard rules (from the tool contract)

1. **Required ordering:** `list/read` -> `finalize_plan` -> `write/delete`. Calling `write_files`,

### The `@dsCard` preview format
### Workflow
### 1. Build the bundle
### 2. Validate the cards (self-check, mirrors the app)
### 3. Pick the target project (READ — no plan needed)
### create one if none exists / user picks "new":
### 4. Build the diff + finalize the plan (permission prompt — human approves)
### -> returns planId
### 5. Write the files (requires the plan)
### 6. Cards register automatically
### Self-test
