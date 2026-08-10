---
name: figma
description: Thin PROJECT overlay on the official Figma MCP skill pack. Use when fetching Figma design context, screenshots, variables, or assets, when writing/generating designs INTO Figma, when mapping components with Code Connect, or when setting up and troubleshooting the Figma MCP connection. The canonical HOW lives in the pack skills (figma-use, figma-design-to-code, figma-generate-design, figma-code-connect); this overlay only carries the mandatory pack-skill gate plus this workspace's implementation conventions and seat caveats.
---

# Figma MCP — project overlay

This is a THIN OVERLAY, not the primary reference. The official Figma MCP server ships a full skill pack (served as `skill://figma/*` MCP resources — verified live). Those pack skills are the source of truth for how to drive every Figma tool. This local skill exists only to:

1. Enforce the pack's **mandatory prerequisite gates** (our previous local skill never referenced `/figma-use`, so writes were driven blind — the exact cause of the "common, hard-to-debug failures" the official `figma-use` skill warns about).
2. Carry this **workspace's own implementation conventions** (design-token reuse, asset handling) that are NOT in the vendor pack.
3. Record this workspace's **seat/plan caveats** (Education Full seat).

> Advisory scope: a skill is prompt-level guidance — it cannot hard-block a tool call. The "MANDATORY" wording below mirrors the vendor pack's own wording and is enforced by discipline, not by a hook. This overlay is a pure advisory injector (zero-block, zero-irreversible), so per the council risk-tier ladder it ships at ADVISE — no shadow machinery required.

## MANDATORY prerequisite gate (load the pack skill BEFORE the tool)

Before calling any of these Figma MCP tools, FIRST load the paired pack skill. Prefer the installed `/figma-*` slash skill; if it is only served as an MCP resource, load the `skill://` URI AND prefix the name with `resource:` in the tool's `skillNames` parameter.

| Intent / tool you are about to call | Load this pack skill FIRST | Slash / resource URI |

### Read FROM Figma (design context) — project flow
### Project implementation conventions (overlay — not in the vendor pack)
### Asset handling
### Link-based prompting
### Seat / plan caveats (this workspace)
### References
