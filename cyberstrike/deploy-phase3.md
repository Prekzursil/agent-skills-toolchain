# deploy-phase3.md — Phase-3 switch plan (owner-triggered; run nothing before owner GO)

Phase-3 artifacts (this change set) are DRAFTS: `AGENTS.new.md`, `CONTEXT.new.md` (generated),
`MIGRATION-TABLE.md`, `HOME-ELEVATION-PROPOSAL.md`, `plugin/manifest-writer.ts`,
`scripts/{gen_context.py,gen_migration.py,build_migration_map.py,migration_map.json,manifest_merge.py}`.
Nothing live has been touched; TUI PID at authoring time (19684) was left running untouched.
Budget assert at authoring: AGENTS.new.md 6435 B + CONTEXT.new.md 1015 B = 7450 B ≤ 7500 B.

## Preconditions
1. Owner GO for Phase-3 (grill roadmap step 3) + the four G-7 edges adjudicated or explicitly
   deferred (AGENTS.new §2 carries them as OWNER-PENDING; §2 freeze requires rulings).
2. TUI restart window: fixes + rewire apply at next start anyway.
3. Working tree clean vs `b7ab510` (`git -C ~/.config/cyberstrike status --porcelain` empty).

## Steps (in order; owner or owner-delegated session executes)
1. **Backup** — `backups/phase3_<YYYYMMDD-HHMM>/`: copy AGENTS.md, config.md, CONTEXT.md,
   instructions-recon.md, instructions-fullpower-estate.md, cyberstrike.json. Also
   `git tag pre-phase3` (or rely on `b7ab510` + the Phase-3 commit being separate).
2. **Switch files** —
   - `AGENTS.new.md` → replace `AGENTS.md` (native loader path, Global.Path.config — Phase-1
     proved the native load; keep exactly ONE copy);
   - regenerate `CONTEXT.md` from `CONTEXT.new.md` pipeline: `python scripts/gen_context.py`
     writes `CONTEXT.new.md`; copy it to `CONTEXT.md` (or repoint instructions[] to
     CONTEXT.new.md and delete the copy step — pick ONE, do not load both);
   - rewire `cyberstrike.json` `instructions[]` to exactly `["{file:~/.config/cyberstrike/CONTEXT.md}"]`
     (config.md, instructions-recon.md, instructions-fullpower-estate.md superseded — their 175
     clauses are mapped in MIGRATION-TABLE.md; keep the files read-only in-tree for history).
3. **Wire the manifest plugin** — add to `cyberstrike.json`: `"plugin":
   ["~/.config/cyberstrike/plugin/manifest-writer.ts"]`. Event names verified in-binary
   (vehicle verdict stage 4); exact hook input shape is UNVERIFIED — first start is the
   experiment: if no `manifest/sessions/*.ndjson` appears after one session starts and goes
   idle, dump the actual payload shape (log `Object.keys(input)` once in a debug copy) and
   adjust `sessionFrom()`. Fallback if the plugin lane fails entirely: poll-based
   `scripts/manifest_poll.py` (design: tail the TUI log/db for session rows, append the same
   shard lines) — event-driven version then marked PARKED-needs-vehicle-change.
4. **Post-switch checks (T-1/T-2/T-13 from the audit battery, both-states controls)**:
   - **T-1 injection-count**: dump a fresh session's assembled system prompt; the AGENTS.md
     body must appear EXACTLY ONCE and CONTEXT.md once. Control: pre-switch dump showed the
     old double-load — a probe silent in both states measures nothing.
   - **T-2 budget + stale-payload**: `wc -c AGENTS.md CONTEXT.md` total ≤ 7500; prompt dump
     greps zero hits for `ses_f9c9ab90`, `FINAL-REPORT_2026-09-03`, `Daybreak Red`.
   - **T-13 redundancy regression**: NEVER-ROTATE count == 1, research-surface list == 1,
     org-925 count == 0 (moved to HOME pointer) across the two live files.
   - Drift gates: `python scripts/gen_context.py --check` (PASS) and
     `python scripts/gen_migration.py` (exit 0 = live instruction files unchanged since map
     build — NOTE: after step 2 replaces them, re-run `build_migration_map.py` once against
     the OLD copies in the backup dir to regenerate the frozen map, or archive the current
     map as the Phase-2→3 record; the assert's job ends at switch time).
5. **First-session smoke**: one session start → idle → `python scripts/manifest_merge.py`
   shows the session row; `--status <id>` reports `dead_two_signal=false` while alive.
6. **Rollback**: restore step-1 backups over the live names, revert instructions[], remove the
   `plugin` key, restart TUI. Everything is git-reversible to `b7ab510` + the Phase-3 commit.

## Out of scope for this deploy
HOME AGENTS.md edit (gated on HOME-ELEVATION-PROPOSAL.md owner review), the G-9 MCP gateway,
G-10 callID binary patch, G-11 inject-only hooks (dispatcher experiment first).
