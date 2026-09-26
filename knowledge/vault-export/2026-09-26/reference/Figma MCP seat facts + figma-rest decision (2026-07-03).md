---
title: Figma MCP seat facts + figma-rest decision (2026-07-03)
type: note
permalink: main/reference/figma-mcp-seat-facts-figma-rest-decision-2026-07-03
tags:
- figma
- mcp
- rate-limits
- education
- correction
- decision
---

**Figma MCP capability facts (verified live 2026-07-03; corrects stale FIGMA-SETUP.md §2.4 via PR #23 → main b7dd295):**

- Rate limits track **SEAT type, NOT plan**. **View/Collab seat = ~6 tool calls/month** (any plan — a toy). **Dev/Full seat = 200/day, 10/min even on FREE Starter/Education** (Pro 15/min, Org 600/day+20/min). Writes (`generate_figma_design`/`use_figma`/`whoami`) are **rate-limit-EXEMPT**. Source: developers.figma.com/docs/figma-mcp-server/rate-limits-access/.
- ⭐ **User is on Figma for Education (FREE) with a FULL seat** (`andrei-mihai.visalon@s.unibuc.ro`, org Prekzursil). Verified: official MCP `whoami` → `seat:Full, tier:student`; live `get_design_context` returned the full source tree, NO throttle. The official Figma MCP (mcp.figma.com OAuth) is FULLY functional — NOT the "6/month toy" I wrongly claimed from the stale doc. User was RIGHT to push back.
- Code Connect requires the ORGANIZATION tier (not Education/Pro).

**DECISION: DROP `figma-rest`** (Framelink, user-scope). Official MCP supersedes it (reads 200/day + unlimited writes + download_assets). figma-rest's only edge = truly-headless (cron/gateway) PAT reads — niche, re-addable. Removal = Claude-CLOSED ~/.claude.json edit → QUEUED for next restart, bundled with `promote-mcp-userscope.ps1`.

⭐ LESSON: don't trust an internal doc's plan/seat/rate-limit claim without checking the PRIMARY source + an EMPIRICAL test (whoami + live read). Relates to [[Session learnings 2026-07-03 (MCP vendoring + harness)]], [[MCP fleet expansion 2026-07-03]].