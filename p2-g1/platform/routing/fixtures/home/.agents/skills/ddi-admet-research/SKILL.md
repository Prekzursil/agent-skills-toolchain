---
name: ddi-admet-research
description: Use as the front-end/router for biomedical research via the tooluniverse MCP server (Harvard Zitnik lab, 2206 tools) - drug-drug interactions, ADMET/physchem prediction, CYP450 enzyme roles, target research, FDA drug labels, drug repurposing, and pharmacovigilance. Routes to the detailed installed tooluniverse-* skills; covers the uvx registration. Use when a question needs biomedical knowledge-base lookups rather than local structure computation.
---

# DDI / ADMET Research (ToolUniverse front-end)

## Overview

This skill is a THIN ROUTER over the `tooluniverse` MCP server and the already-installed `tooluniverse-*` deep skills. Do NOT re-implement DDI/ADMET reasoning here - dispatch to the specialized skill, then call ToolUniverse tools.

- Server: ToolUniverse (Apache-2.0, Harvard Zitnik lab), 2206 biomedical tools covering DDI, ADMET, CYP, targets, FDA labels, repurposing, and pharmacovigilance.
- Registration (verified, stdio): command `uvx`, args `tooluniverse==1.2.4`, env `PYTHONIOENCODING` = `utf-8`. The stdio entry point is `tooluniverse.smcp_server:run_default_stdio_server`.
- Cross-platform: `uvx` works on Windows and POSIX identically; no path edits needed.

## Route to the Right Installed Skill

Deep, ready-made skills already live at `~/.agents/skills` (on Windows: `C:\Users\agentuser\.agents\skills`). Pick by intent:

- Drug-drug interactions, polypharmacy, CYP/UGT mechanisms -> `tooluniverse-drug-drug-interaction`
- ADMET / physicochemical / drug-likeness prediction -> `tooluniverse-admet-prediction`
- Hazard, GHS, handling, exposure -> `tooluniverse-chemical-safety`
- Target identification / validation -> `tooluniverse-target-research`
- Repositioning / new indications -> `tooluniverse-drug-repurposing`
- Adverse events, signal detection, post-market safety -> `tooluniverse-pharmacovigilance`
- Mechanism of action -> `tooluniverse-drug-mechanism-research`

Invoke the matching skill first; this front-end only handles routing + the connection.

### Real ToolUniverse Tools (verified in use)
### Quick Workflow
### Common Mistakes
### Related Skills
