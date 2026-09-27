# Lane: context-prefix — Context / always-on prefix

**Status:** COMPLETE — all 4 items done, proven, both-states where applicable.
**Host:** OFFLOAD-W2025 (Windows Server 2025), profile `C:/Users/prekzursil`, Python `C:\Python314\python.exe`.
**Rule 6:** nothing committed. Changes left unstaged for the orchestrator (see Files changed).
**Rule 11:** every claim below is VERIFIED (exact cmd+output) or INFERRED, with a confidence band.

---

## (a) `# Compact instructions` block in `~/.claude/CLAUDE.md` — DONE

**Premise (VERIFIED, ~99%):** `rules/common/context-reduction.md` rule 2 mandates a
`# Compact instructions` block; it was ABSENT from every always-on file.
- Cmd: `Select-String '(?i)^#+\s*Compact instructions'` over `.claude/CLAUDE.md`, `~/CLAUDE.md`,
  `.claude/AGENTS-RUNTIME.md`, `~/AGENTS.md`, `.claude/AGENTS.md` → all `ABSENT` (pre-state).

**Action:** inserted a 17-line `# Compact instructions` block after the `@`-imports in
`~/.claude/CLAUDE.md`. It deterministically tells auto/manual compaction to preserve, drop-last:
(1) **Decisions made** + rejected options, (2) **Diffs / files changed** (paths, SHAs, branches),
(3) the **OPEN-LOOPS register** (`~/.agents/knowledge/OPEN-LOOPS.md`) + in-flight TASKBOX +
unenforced DIRECTIVEs — with the AGENTS-RUNTIME §1c "a dropped loop is an abandoned loop" hook.

**Post-state (VERIFIED, ~99%):**
- `Select-String` → `claude/CLAUDE.md block: PRESENT L7`; total lines 146 (was 129, +17 ≤ 25 cap); 10,404 B.
- Mirror: `~/.agents/CLAUDE.md` was byte-identical to `~/.claude/CLAUDE.md` (`diff -q` → IDENTICAL).
  I applied the SAME block to it; `Get-FileHash` → both mirrors IDENTICAL again (in sync).
  Rationale: `sync-from-live.ps1` references CLAUDE.md only in a comment (no auto-sync), so the two
  are hand-maintained mirrors; editing both prevents drift whichever is treated as canonical.

**Both-states:** N/A — a doc/instruction block is not a gate/check/lint/hook (rule 7 scope). The
falsifiable evidence is the before(ABSENT)/after(PRESENT L7) probe + line count, shown above.

**Net-negative (rule 10):** ADDS ~17 lines (~180 tok) × 2 mirror files to the always-on prefix;
retires NOTHING textual. Justified: rule-mandated, and its purpose is to retire the far larger
*re-derivation* cost after compaction — cache_lens measured 82.6M tok of cold-prefix rewrites
estate-wide, the cost this block exists to cut.

## (b) Prompt-cache hit-rate lens → `~/.agents/scripts/cache_lens.py` — DONE

**Prototype found (VERIFIED):** task path had a digit transposition (`57350` vs real `57530`);
`cache_audit.py` exists at `…/027fa5cb-1562-482e-a2e1-6a2f57530cb6/scratchpad/cache_audit.py`
(the current session's scratchpad). It was hardcoded to ONE session id and did **no dedupe**.

**Dedupe premise (VERIFIED, ~97%) — and refined:** the "~3x per assistant message" claim is real
but is a DISTRIBUTION, not a flat 3x. `probe_dupes.py` over the 3 largest transcripts:
- mean lines/message.id = 2.05 / 2.28 / 2.71; tail up to 25–30x; and the IDENTICAL usage block is
  copied onto every duplicate line (distinct usage tuples per id = 1). So dedupe by `message.id`
  is safe + lossless. The estate's own ground-truth "547,163 x4" IS this duplication showing.

**Built `cache_lens.py`:** walks `~/.claude/projects/**/*.jsonl`, dedupes by `message.id`
(fallback key when id missing), reports hit rate, counts cold prefix rewrites
(`cache_creation > 20k AND cache_read == 0`), flags sessions whose cold cost exceeds a threshold.

**Both-states proof (VERIFIED, ~99%)** — `python cache_lens.py --selftest` → `SUCCESS`, EXIT 0:
- BROKEN (naive sum) cache_creation = 90,001 for a 3x-logged message; CORRECT (deduped) = 30,001
  → dedupe inflation 3.00x. An inert dedupe would make these equal and FAIL check 4.
- Cold detector: 0 rewrites when `cache_read>0` (good input) / 1 when `cache_read==0` (broken
  input) → fires on broken, silent on good.

**Real run (VERIFIED):** `python cache_lens.py` over 1,895 transcripts:
- dedupe: 103,387 raw usage lines → 35,449 unique messages (**2.92x** inflation avoided).
- HIT rate 94.72%; cold prefix rewrites 347, total 82,617,810 tok; 18 sessions flagged (>500k cold).
- Worst: `3fb11978…` cold=35,528,135 / 68 rewrites. This session `027fa5cb…` cold=1,372,337 / 5 /
  98.6% hit — consistent with the task's ground truth for this transcript.

**Net-negative (rule 10):** RETIRES the single-session, no-dedupe prototype
`scratchpad/cache_audit.py` (task said "promote it"). cache_lens.py supersedes it.

## (c) Skill-listing truncation visibility → `~/.agents/scripts/skill_listing_audit.py` — DONE

**Built:** parses SKILL.md frontmatter (name+description, incl. folded/block scalars), sums bytes,
estimates tokens (bytes/4 — the estate heuristic: 136,778 B → 34,194 tok is exactly /4), and for
each `--window` shows whether the `0.04` cap BINDS for LOCAL-only vs LOCAL+PLUGIN.
Traversal uses `os.walk` not `glob('**')`: glob silently skips junction dirs under
`~/.claude/plugins` (measured 2,057 vs os.walk/find **2,167**) — a real undercount bug, fixed.

**Both-states proof (VERIFIED, ~99%)** — `--selftest` → `SUCCESS`, EXIT 0: tiny listing / huge
window → `NON-BINDING`; huge listing / tiny window → `BINDS`; parser extracts name+desc on a good
file and contributes 0 (no crash) on a file with no frontmatter.

**Real audit (VERIFIED):** `python skill_listing_audit.py`:
- LOCAL 468 SKILL.md → 160,933 B → **40,233 tok**; PLUGIN 2,167 → 944,041 B → **236,010 tok**;
  TOTAL 2,635 → 1,104,974 B → **276,243 tok**.
- @1M window (cap 40,000): LOCAL-only **BINDS by +233**; LOCAL+PLUGIN BINDS by +236,243 (6.9x).
- @200k window (cap 8,000): BINDS massively both.

**REFUTED PREMISE (VERIFIED, ~90%):** the task's worked example ("34,194-tok LOCAL listing =
non-binding on 1M") no longer holds — LOCAL is now **40,233 tok (468 skills)**, 233 tok OVER the
40,000 cap. The 34,194/415 figure was measured on fewer skills (grown 415→468 since). Conclusion
the task wanted is emphatic: including plugins does flip it — 276k vs 40k, listing truncated to
~14.5% of demand.

**Recommendation for `skillListingBudgetFraction` (A/B, NOT changed — task ban honored):**
- Decisive number: LOCAL 40,233 tok vs cap 40,000 @0.04×1M → 0.04 no longer fits even the curated
  LOCAL set (by 233 tok); at a 200k window it is 5x over.
- Do **NOT lower** 0.04 — it already truncates local; lowering worsens it. The fraction is the
  wrong lever (showing all 2,635 would need 0.276 = 27.6% of window). Per context-reduction
  doctrine the real lever is CURATING the 2,167-entry plugin cache (236k tok competing for the
  budget as mostly-noise; Tool Search already de-fangs their token cost).
- If the owner wants the LOCAL set fully visible without truncation: A/B a MINIMAL bump to ~0.045
  (cap 45,000 @1M covers 40,233 with headroom, ~+5k always-on tok), judged by whether
  skill-mispick / "skill not found" incidents drop. Confidence this is the right framing: ~75%.

## (d) Stable-prefix (KV-cache) lint → `~/.agents/scripts/stable_prefix_lint.py` — DONE (report-only)

**Built:** enumerates always-on memory files by resolving `@`-imports recursively from
`~/.claude/CLAUDE.md` + `~/CLAUDE.md`, reports each file's bytes, flags per-turn-varying content
(datetime, clock-time, generation markers, PIDs, epoch secs) that would break the cached prefix,
and flags DANGLING `@`-imports. Changes nothing (report-only, per task).

**Both-states proof (VERIFIED, ~99%)** — `--selftest` → `SUCCESS`, EXIT 0: a fixture WITH a
regeneration timestamp is FLAGGED (datetime/clock-time/gen-marker); a fixture with only a bare
date is CLEAN (bare dates counted, not flagged); a dangling `@`-import is detected and a valid one
resolves.

**Real lint (VERIFIED):** `python stable_prefix_lint.py`:
- Always-on FILE chain (5 enumerated, 4 present): `~/.claude/CLAUDE.md` 10,404 B, `~/CLAUDE.md`
  9,406 B, `~/.claude/AGENTS-RUNTIME.md` 21,962 B, `~/AGENTS.md` 1,132 B — total **42,904 B ≈
  10,726 tok**, ALL `stable` (no per-turn-varying content).
- **VERDICT:** no always-on FILE breaks the cached prefix. Any prefix-cache thrash (cache_lens:
  347 cold rewrites) comes from tool-def/order changes, model/thinking swaps, or HOOK output
  injection — NOT these files.
- **1 DANGLING `@`-import:** `~/.claude/AGENTS.md` (referenced by `~/.claude/CLAUDE.md`). Prefix
  hygiene, not cache-breaking — but note `agents.md` rule wants an `~/.claude/AGENTS.md` (§5
  handoff contract); it resolves in the `.agents` mirror, not the loaded `.claude` one. Proposed
  fix (NOT applied — out of lane scope, propose-only): create/symlink `~/.claude/AGENTS.md`.

**Net-negative (rule 10):** new capability, retires nothing (no prior always-on-prefix volatility
lint existed). Justified: fills a measurement gap; report-only, adds no runtime cost.

---

## Files changed (rule 6 — left for orchestrator, NOT committed)

- `M  ~/.agents/CLAUDE.md` — compact-instructions block (git-tracked; `git status` shows ` M`).
- `M  ~/.claude/CLAUDE.md` — compact-instructions block (NOT a git tree; live deploy copy).
- `?? ~/.agents/scripts/cache_lens.py` — new (untracked).
- `?? ~/.agents/scripts/skill_listing_audit.py` — new (untracked).
- `?? ~/.agents/scripts/stable_prefix_lint.py` — new (untracked).
- Scratchpad only (not for commit): `probe_dupes.py`, `cache_lens_out.txt`.

## Risks / open loops

- cache_lens hit-rate/token totals use the transcript `usage` fields as logged; if Claude Code
  ever logs usage only on the FIRST content-block line (not all), dedupe-by-id is still correct
  (keeps that one). Confidence dedupe is robust: ~95%.
- token estimates are bytes/4 (labeled estimates), matching the estate's own heuristic; a real
  tokenizer would shift absolute numbers but not the BINDS/NON-BINDING verdict (276k vs 40k).
- `skillListingBudgetFraction` recommendation is an A/B to run, not an assertion — NOT applied.
- Dangling `~/.claude/AGENTS.md` import is proposed-only, not fixed (out of lane scope).
- window size: analysis leads with 1M (estate's stated operating window); at 200k the local
  truncation is 5x worse — reported both.
