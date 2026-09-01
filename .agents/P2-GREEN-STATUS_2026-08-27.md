# P2 `p2-g1-until-green-3` — green-status report (27.08.2026)

**Terminal state: `BLOCKED-ON-BUDGET` — current true count `PARTIAL 1043/2007`.**
Not green. Never was green. The fail-closed gate held: no `complete()` was ever emitted.

## 1. What "2007/2007 verified twice" means and where it stands

The workflow `p2-g1-until-green-3` (definition: `~\.grok\workflows\p2-g1-until-green.rhai`; run
instance `wf_01a03af2589b7701bef51815a4373884` inside Grok session
`019fe1f3-4229-7eb1-b698-716130cd7669` "P2 2007 leftover harvest and G-1 remesure") measures all
2007 catalog work-units of `C:\Users\Prekzursil\source\ast-integrate` with
`command-center/p2-wave/_measure_one_delivered.py` (WSL-only) and may only `complete()` when a full
census reads **n=2007, ok=2007, fail=0** AND an independent confirm agent re-reads the files and
re-measures 12 live IDs (`both_green`). That never happened.

**Run-state truth (from the run's `state.json`, revision 142):**
- `status: "infra_paused"`, `current_phase: "Gate"`,
  `pause_message: "Entire 30-wide repair panel failed (often Grok Build 402). Resume after quota."`
- Wave 1 (25.08 22:02Z → 26.08 03:12Z): 30-agent repair panel ran; started from `remaining_n=1354`.
- Gate census after wave 1 (26.08 04:08:30Z): **n=2007, ok=1053, fail=954** — recorded in
  `g1-until-green-census.md` ("Status: **NOT GREEN**") + `g1-until-green-handoff.json`
  (`green: false`, dual-signal recount inside).
- Wave 2 (26.08 04:22Z): 30 repair agents launched; **all 30 `state: "failed"`** — 14 of them died
  in 7–20 s with 0 tokens (the 402 aborts). Workflow paused 04:56:10Z; the session died with it.
- The prior census itself (1053/954) was dual-signal verified at the time (jsonl recount, SHA256 of
  `remaining_ids.txt` = fingerprint match). So the last *known* state was honestly non-green, and
  the recovery doc's caution was warranted.

## 2. What I executed today (all local, fail-closed, no repo edits)

The full G-1 measure is pure local WSL Python — no Grok compute needed for *counting*. Steps:

1. **Backed up** the 26.08 census artifacts (never-overwrite):
   `g1-local-full.json|jsonl|heartbeat → *.bak-census-20260826` in `…\p2-wave\ovh-monitor\`.
2. **Delta-synced the WSL mirror** `~/p2-g1` (baseline verified by the 26.08 census): enumerated
   3,768 files changed since 25.08 21:00Z on the NTFS side
   (`ovh-monitor\_changed_since_wave1.txt`), rsynced exactly those (error log empty). Full-tree
   `--checksum` rsync was abandoned after three silent kills (WSL VM restarts under this box's
   memory pressure — PID counter reset observed).
3. **Schema-ID rewrite** on the mirror: `rewrite_schema_file_ids.py` →
   `SUCCESS:schema-file-ids files=246 replacements=816` (identical to the 26.08 census run).
4. **Full 2007-unit remeasure**: `g1_remeasure_all.py` then `g1_remeasure_resume.py` in a
   Windows-side respawn loop (clients get OOM/VM-killed on this box; the resume script appends
   without wiping). Completed 27.08 12:12:29Z, `G1_WORKERS=10`.
   Log: `ovh-monitor\g1-resume_2026-08-27.log`.
5. **Independent second verification (count verified twice):**
   `ovh-monitor\_g1_recount_20260827.py` → `ovh-monitor\g1-recount_2026-08-27.json`:
   catalog=2007, jsonl lines=2007, unique=2007, missing=0, extra=0, **ok=1043, fail=964**,
   matches summary file; jsonl SHA256
   `1dc46119287db571441a6705489a80d1475e1ee501d6cc7e0ba3496c564f69c5`.
6. **Live spot-checks** (detector is live, not silent): re-ran `_measure_one_delivered.py` on
   ADV-0001 → `SUCCESS:delivered`, ARC-0003 → `SUCCESS:delivered`,
   ADV-0002 → `FAILED:delivered … probe-exit:1`, ARC-0001 → `FAILED:delivered … probe-exit:1` —
   all four agree with the jsonl.
7. **Minimal Grok Build probe** (single-turn `grok -p`, low effort, no subagents — one prompt, not
   a batch): **still blocked** —
   `API error (status 402 Payment Required): Grok Build usage balance exhausted` (27.08 ~15:30 EEST).

## 3. Current true count and drift vs 26.08

| | 26.08 census | 27.08 remeasure (this run) |
|---|---|---|
| ok | 1053 | **1043** |
| fail | 954 | **964** |
| probe-exit | 924 | 936 |
| ModuleNotFoundError | 17 | 16 |
| probe-file-missing | 4 | 8 |
| schema-ref | 4 | **0** |
| manifest-sha-mismatch | 3 | 4 |
| predicate | 2 | 0 |

Reading: wave 2 landed *some* fixes before dying (schema-ref and predicate classes cleared), but
the net count moved −10: a few units regressed to probe-file-missing / sha-mismatch / probe-exit —
consistent with 30 repair agents being killed mid-edit by the 402. Some probe flakiness under load
cannot be excluded; the 964 fail set is the honest current baseline
(`fail_ids` head in `g1-local-full.json`; full set derivable from the jsonl).

## 4. Evidence paths

- `C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\ovh-monitor\`
  - `g1-local-full.json` (ts 2026-08-27T12:12:29Z, n=2007 ok=1043 fail=964, workers=10)
  - `g1-local-full.jsonl` (2007 rows, SHA256 `1dc46119…c564f69c5`)
  - `g1-recount_2026-08-27.json` (independent recount — verification #2)
  - `g1-resume_2026-08-27.log`, `g1-remeasure-run_2026-08-27*.log` (run logs)
  - `*.bak-census-20260826` (preserved 26.08 census), `g1-until-green-census.md`,
    `g1-until-green-handoff.json` (prior NOT-GREEN evidence)
- `C:\Users\Prekzursil\.grok\sessions\C%3A%5CUsers%5CPrekzursil\019fe1f3-4229-7eb1-b698-716130cd7669\workflows\wf_01a03af2589b7701bef51815a4373884\state.json`
  (workflow run state: `infra_paused`, wave-2 panel all-failed)

## 5. Exact remaining blocker + user action

- **Blocker:** repairing the 964 failing units requires the workflow's 30-wide Grok Build agent
  panels; Grok Build returns **HTTP 402 "usage balance exhausted"** as of 27.08.2026 (probe above).
  Local compute can *measure* but cannot do the 964 repairs unattended without an agent runner.
- **User action (either):**
  1. Top up / wait out the **Grok Build usage balance** on the account behind `~\.grok\auth.json`,
     then resume the paused run in the Grok session (it resumes the same uncapped fail-closed loop:
     repair wave → gate census → confirm), or
  2. Re-point the gate/repair loop at a **non-metered runner** (e.g. Claude/Cursor subagents) —
     that is a new workflow decision, not attempted here (out of scope for this go).
- **Do not** mark P2 green until a census + independent confirm both read 2007/2007 on disk.
  Today's count (1043/2007, verified twice) is the baseline to resume from; `skip_census=1,
  remaining_n=964` would be the honest resume args, or just let the census phase re-derive it.

*No secrets reproduced. Phenibut research data untouched. MIRCEA/ECC/BPMD left gated as ordered.*
