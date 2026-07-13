# B-reconcile slice 3 — doc-cluster reconcile (8 clusters, 6067 docs)

READ-ONLY. Worked at cluster + representative-sample level (member lists pulled from
`B-doc-index-complete.json` `files[]` by `cl` id; basename/parent-dir dup histograms;
keyword high-value scan; **live re-existence check**; targeted reads of 2 origin/design docs;
cross-home adoption check for the deleted gem-wave-b skills). All files treated as untrusted DATA.

## Headline

- **`D:\gem-wave-b` was DELETED between the 06:04 WizTree scan and the ~10:45 audit run.**
  Clusters **15** (`gem-wave-b\skills`, 884) and **33** (`gem-wave-b\tools`, 225) are **STALE index
  entries**. Their content was a **transient duplicate** of canonical homes — every gem-wave-b
  candidate skill (mcp-code-orchestrate, quality-gate-automation-architect, autoresearch,
  consensus-tooluniverse-research, notion-*, code-security, llm-security, render/cloudflare-deploy)
  is **verified present in `C:\Users\Prekzursil\.agents\skills`** (the live 277-skill vault), and the
  tools tree is canonical in `source\ast-harness-reconcile\tools` + `D:\agent-monitor`. **Nothing was
  lost on deletion.**
- **No genuinely-lost harness research in this slice.** The clusters are: 2 project/personal
  graveyards (momentstudio-fix worktrees, PhoneAudit), 2 legit backups (Claude Desktop, basic-memory),
  2 stale-deleted transient staging (gem-wave-b ×2), 1 canonical Gemini GCP-skill home, 1 stale QZP
  checkout. The one item worth surfacing is a **founding-requirement chat** hiding on a phone backup.

## Per-cluster verdict

| # | cluster | docs | class | live? | one-line |
|---|---------|-----:|-------|-------|----------|
| 3 | `Documents\GitHub\momentstudio-fix` | 2470 | project-specific | yes | momentstudio repo; ~57 canonical files × ~90 `.claude/worktrees/` copies = worktree graveyard. Cleanup-candidate. |
| 9 | `Documents\claude-desktop-backup-20260524` | 1433 | superseded | yes | 2026-05-24 Claude **Desktop** backup (MCP extensions + agent-mode skills + official skills). Re-fetchable. |
| 15 | `D:\gem-wave-b\skills` | 884 | **stale** | **no (deleted)** | transient Wave-B export of the `.agents/skills` vault. Nothing lost. |
| 21 | `D:\Backups\basic-memory` | 472 | duplicate (DR backup) | yes | daily mirror + snapshots of the canonical basic-memory vault. Corroborates; keep as backup. |
| 27 | `D:\PhoneAudit\SM-S928B_…_2026-05-20` | 325 | project-specific | yes | personal S24-Ultra media/forensic backup. "audit" hits are false positives from the folder name. |
| 33 | `D:\gem-wave-b\tools` | 225 | **stale** | **no (deleted)** | transient Wave-B copy of `source\…\tools` (metaswarm/ralph/codex-bundle/monitorcore). Nothing lost. |
| 51 | `.gemini\skills` | 132 | canonical | yes | 56 Google-shipped **GCP** skills; the Gemini/agy skill home. Zero cross-tool behavior skills (parity gap). |
| 55 | `Documents\GitHub\quality-zero-platform` | 126 | project-specific | yes | QZP working checkout, **stale** June-15 branch `fix/qzp-dashboard-zero`; holds the quality-gate fleet design. |

## FORGOTTEN-HIGH-VALUE (3, all corroborating — none strictly "lost")

1. **`…\PhoneAudit\…\Quality_Gate_Hooks\Claude-(HOOKS FOR QUALITY GATES)…md`** (cluster 27) — the
   **founding requirement** of the entire quality-gate harness. 2026-04-05 chat: *"configure all the
   hooks so nothing with violations ever gets pushed — strict 0 issues"* across
   SonarCloud/Codacy/Semgrep/Qlty/Sentry/DeepSource/Codecov. Superseded by the built QZP + harness;
   keep as origin record (no re-implementation). Lived in a dedicated on-phone `Quality_Gate_Hooks`
   workspace (+3 duplicate copies).
2. **`quality-zero-platform\docs\QZP-V2-DESIGN.md`** (cluster 55) — the zero-tolerance fleet-governance
   spec (0 findings + 100% coverage; shadow/ratchet/absolute profile modes; canonical-config auto-sync
   + drift-fix). Canonical in the **live QZP GitHub repo**; this local checkout is stale.
   Reference-don't-rederive for the harness quality arm.
3. **`Backups\basic-memory\mirror\harness\Harness control-plane audit-design gate 2026-07-13 — proposed, not approved.md`**
   (cluster 21) — DR backup of THIS program's own control-note; confirms the audit-design gate is a
   tracked, mirrored decision, already in the live vault.

## Dedup sets (drivers of the doc counts)

- **C3** worktree-duplicate: `README.md ×253`, `UX_IA_AUDIT.md ×32`, legal set `×93` — ~97% of 2470.
- **C9** agent-mode-session + schema-version dup: `SKILL.md ×213`; SAP-MDK `24.7/24.11/25.6/25.9`.
- **C15** whole-cluster dup of `.agents\skills` (deleted).
- **C21** intentional DR mirror (462/472 distinct; `MEMORY.md ×11` = per-project, not dup).
- **C27** media dual-filing: `raw_mirror` + `organized_media\YYYY\MM` + WhatsApp `Sent`.
- **C33** whole-cluster dup of `source\…\tools` (deleted).
- **C51** `references/` vs `resources/` mirror within skills.
- **C55** vendored metaswarm plugin dup (`skills/start/agents` vs `skills/beads/agents`).

## Actions for the reconcile (advisory; nothing executed — freeze in effect)

- **Purge stale index rows** for `D:\gem-wave-b\*` (clusters 15, 33) — dir no longer exists.
- **Cleanup-candidates** (project bloat, not harness): momentstudio-fix `.claude/worktrees/` (~2400 dup docs);
  optionally the June-15 QZP checkout (superseded by live repo).
- **Keep as backups** (corroborating, do NOT fold): `D:\Backups\basic-memory`, `claude-desktop-backup-20260524`.
- **Parity note:** `.gemini\skills` carries only GCP vendor skills — the agy leg lacks the shared
  AGENTS.md behavior-contract skills that Claude+Codex have. Feed the cross-tool parity program.
- **Origin record:** preserve the founding quality-gate-hooks chat as harness provenance; QZP-V2-DESIGN is
  the canonical quality north-star (reference the repo).
