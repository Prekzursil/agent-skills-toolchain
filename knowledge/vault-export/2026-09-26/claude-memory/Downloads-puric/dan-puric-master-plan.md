---
name: dan-puric-master-plan
description: Dan Puric Media Ecosystem Master Plan 2026–2028 — deliverable location,
  build system, and canonical numbers source
metadata:
  node_type: memory
  type: project
  originSessionId: 7b04a4d9-8286-4028-989d-572fc86e4f23
permalink: main/claude-memory/downloads-puric/dan-puric-master-plan
---

The board-level rebuild of the Dan Puric media strategy lives at `C:\Users\Prekzursil\Downloads\puric\dan_puric_master_plan_2026-2028.html` (~6,980 lines, Romanian, 25 sections, self-contained HTML in the original v1.0 gold/dark editorial design). The original `dan_puric_strategy.html` (v1.0) was preserved untouched.

**Why:** The user (June 2026) asked to upgrade v1.0 into an executive master plan: YouTube re-centered as primary platform (not TikTok), 5-tier platform hierarchy, new WhatsApp/Substack/Patreon/Website chapters, 3-scenario realistic projections, 24-month roadmap, lean 3-person team.

**How to apply:** The document is assembled by concatenating `build/sections/*.html` in lexical order (00-head … 99-footer). To edit a chapter, edit its fragment and re-run `cat build/sections/*.html > dan_puric_master_plan_2026-2028.html`. `build/BRIEF.md` is the single source of truth for all canonical numbers (audience C/R/O projections, revenue, Patreon tiers, team phase thresholds €1.200/€3.500) — keep it in sync if numbers change. `build/SECTIONS.md` holds per-section specs. Key verified facts baked in (June 2026): FB page ~24K, @danpuric YouTube handle unclaimed, third-party videos 173K–1.3M views, RO RPM 4–6 lei/1000, WhatsApp announcement cap 5.000/community.