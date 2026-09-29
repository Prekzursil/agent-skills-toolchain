# L-22: wf_ac30a9af-0a9 journal read (MEGAWAVE-E, Lane E)

Date: 2026-09-28 · Lane: E · Status: **JOURNAL-ABSENT — no per-agent results recoverable from this host**

## Target

`C:/Users/Prekzursil/.claude/projects/*/682da5f0*/subagents/workflows/wf_ac30a9af-0a9/journal.jsonl`
Fallback shape: `C:/Users/Prekzursil/.claude/projects/*/subagents/workflows/wf_ac30a9af-0a9/`

**Verdict: ABSENT (VERIFIED).** The workflow directory does not exist anywhere on this host.

## Search evidence (all run 2026-09-28, this lane)

| # | Probe | Command shape | Result |
|---|---|---|---|
| 1 | Task's literal glob | `Get-Item ...\projects\*\682da5f0*\subagents\workflows\wf_ac30a9af-0a9\journal.jsonl` | no match (VERIFIED) |
| 2 | Task's fallback glob | `Get-Item ...\projects\*\subagents\workflows\wf_ac30a9af-0a9\journal.jsonl` | no match (VERIFIED) |
| 3 | Full projects-tree recurse | `Get-ChildItem ...\projects -Recurse -Depth 4 -Filter *workflows*` + membership test (ran to completion, exit 0) | no `wf_ac30a9af*` anywhere (VERIFIED) |
| 4 | Two-level sweep, all projects | per project: `<proj>\subagents\workflows` and `<proj>\<session>\subagents\workflows`, dirs matching `wf_ac30a9af*` | zero hits (VERIFIED) |
| 5 | Session 682da5f0 inventory | listed `projects\C--Users-Prekzursil\682da5f0-62c5-4c76-826b-fdf5508e20a9\subagents\workflows` | contains only wf_4c7f6644-d3f, wf_a58fff1f-a52, wf_bde1bf15-e0d, wf_c8e4c79c-1c8 (VERIFIED) |
| 6 | Workflow-cwd project dirs | projects dirs named `*subagents-workflows-wf-*` | exactly ONE exists: `...wf-c8e4c79c-1c8` — no project dir was ever created for a wf_ac30a9af agent cwd, i.e. no agent of that workflow ever instantiated here (VERIFIED, load-bearing) |
| 7 | Transcript grep for the id | Select-String `wf_ac30a9af` over every session JSONL ≥100KB modified 2026-09-22..09-28 (all projects, ~150 files) | hits ONLY in OPEN-LOOPS quotations (sessions 027fa5cb and b8fe6671 quote the register); zero launch records (VERIFIED, load-bearing) |
| 8 | Whole-.claude .NET search | `[IO.Directory]::EnumerateFileSystemEntries("C:\Users\Prekzursil\.claude","*ac30a9af*",AllDirectories)` | no output before lane end (background task blrbpyqpw; projects-tree result in probe 3 is dispositive) |
| 9 | Knowledge dir grep | Select-String over `C:\Users\Prekzursil\.agents\knowledge\**` | only `OPEN-LOOPS.md` (VERIFIED) |
| 10 | basic-memory | `search_notes "wf_ac30a9af ..."` | server ECONNRESET — UNVERIFIED, not load-bearing |

A prior session (b8fe6671, earlier today) attempted the identical recovery (`ls .../wf_ac30a9af-0a9/journal.jsonl`) and failed the same way — quoted in its transcript (VERIFIED).

## What the 16 agents were (from OPEN-LOOPS L-22 — INFERRED provenance, register text VERIFIED)

Composition per the register: **2 investigations, 3 executions, 3 preparations, 8 adversarial verifiers** (CV lane; output included edits to `cv/profile.yaml` not yet reconciled with same-day owner answers; re-run zerofab after).

## Per-agent verdict lines

No agent-level identity (lane ids, prompts) survives anywhere on this host — only the role counts above. Verdicts are therefore all the same honest value; NONE are fabricated:

| Agent | Role class | Verdict |
|---|---|---|
| wf_ac30a9af-0a9 #1 | investigation | UNKNOWN — journal absent |
| wf_ac30a9af-0a9 #2 | investigation | UNKNOWN — journal absent |
| wf_ac30a9af-0a9 #3 | execution | UNKNOWN — journal absent |
| wf_ac30a9af-0a9 #4 | execution | UNKNOWN — journal absent |
| wf_ac30a9af-0a9 #5 | execution | UNKNOWN — journal absent |
| wf_ac30a9af-0a9 #6 | preparation | UNKNOWN — journal absent |
| wf_ac30a9af-0a9 #7 | preparation | UNKNOWN — journal absent |
| wf_ac30a9af-0a9 #8 | preparation | UNKNOWN — journal absent |
| wf_ac30a9af-0a9 #9..#16 | adversarial verifier (8) | UNKNOWN — journal absent |

### L-07 (momentstudio.ro — 63,116 cursor/* branches, 89 rescue/* tags)

- Register posture: measurement-only, NO deletion; prune instruction RETRACTED as UNVERIFIED (owner 2026-09-24: branches "had insane amount of progress and werent pushed and now are lost"). (VERIFIED quote)
- Required evidence the workflow was supposed to produce: per-branch `ahead_by` via `gh api .../compare/{base}...{head}` over a real sample + ratio holding unique commits.
- **Verdict: EVIDENCE NOT PRODUCED / NOT RECOVERABLE on this host. L-07 stays OPEN, measurement-only, no deletion.** (INFERRED from absence; confidence: HIGH — absence proven by probes 1-7.)

### L-08 (agent-skills-toolchain — 403 MB, red CI, browser-profile binaries)

- Register posture: measurement-only, NO purge; profiles not established as residue; "no LICENSE" sub-blocker DEAD (private repo). (VERIFIED quote)
- Required evidence: what references the profiles, what auto-writes them, what is lost on removal.
- **Verdict: EVIDENCE NOT PRODUCED / NOT RECOVERABLE on this host. L-08 stays OPEN, measurement-only, no purge.** (INFERRED from absence; confidence: HIGH.)

## Root-cause hypotheses for the absence (all INFERRED — none proven)

1. The workflow ran on the other host (offload-w2025, the disposable VM) — MEDIUM confidence. Nothing on the VM is safe until pushed; if it ran there and was not pushed, it may already be gone.
2. The launching session was purged/archived before its transcript survived — LOW-MEDIUM confidence (session-bundle.tgz from 09-26 was not readable by tar here; id appears in no surviving transcript).
3. The id in the register was recorded before a failed launch (aspirational) and the workflow never started — LOW confidence (the register phrasing "Investigation running" plus the 16-agent role breakdown suggests a real launch was observed).

## Disposition (recommended, owner-gated — nothing executed by this lane)

1. KEEP L-22 OPEN; update its owner-note to "journal unrecoverable on home host 2026-09-28; evidence search documented in this file."
2. Re-run the two investigations (L-07 ahead_by sampler, L-08 profile-purpose map) as fresh, small, scripted lanes — deterministic scripts, not agent batches, so the results land in files not volatile workflow state.
3. Before re-running, one check on offload-w2025 for `wf_ac30a9af*` (5-minute probe) to avoid redoing work that survived there.
4. The `cv/profile.yaml` reconciliation half of L-22 (apply owner answers, re-run zerofab) is independent of the journal and can proceed on home — the owner answers of 2026-09-24 are in the register/session record, not only in the lost journal (INFERRED, MEDIUM confidence — verify before applying).
