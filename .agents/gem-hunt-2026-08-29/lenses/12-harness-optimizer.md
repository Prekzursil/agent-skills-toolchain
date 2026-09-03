# Lens 12 — Harness Optimizer (reliability · cost · throughput)

**Date:** 29.08.2026
**Mode:** audit + optimize proposals, **NO EDITS APPLIED** (read-only lens per instruction).
**Inputs read:** `~\AGENTS.md`, `.agents\agents.json`, `.claude\hooks\_dispatch\manifest.json`,
`CONSOLIDATED-GEM-DECISIONS_2026-08-27.md`, `WAVE-ABCD-EXECUTION_2026-08-27.md`,
`HARNESS-AUDIT_2026-08-27.md`, `LONG-HORIZON-CLOSURE_2026-08-29.md`,
`docs\incidents\2026-08-29-cursor-agent-mcp-orphan-ram.md`, plus live config/scripts/logs named below.
**Constraints honored:** no new resident daemon proposed; no second `cursor-agent`; basic-memory
remains the sole semantic writer; skills stay full-vault + on-demand bodies; nothing rotated;
no feature silently removed (tradeoffs are surfaced as owner decisions, not taken).

**Headline:** the harness's own airworthiness instrument detected a real guard-coverage regression on
**28.08 and again on 29.08**, wrote a `MEL-DEFERRAL` both times, and nothing read it. Three
destructive-command families that were blocked on 27.08 now pass the Cursor shell guard with
`verdict:"ok"`. The deterministic scorer still reports **107/120**, unchanged, because no scorer
category can see any of it.

---

## 1. Baseline scorecard (measured this lens, not asserted)

`node C:\Users\Prekzursil\.agents\scripts\harness-audit.js repo --format text` →

```
Harness Audit (repo): 107/120
Tool Coverage 10 · Context Efficiency 7 · Quality Gates 10 · Memory Persistence 10
Eval Coverage 10 · Security Guardrails 10 · Cost Efficiency 10 · GitHub 10
Vercel 10 · Netlify 10 · Cloudflare 10 · Fly 0
Failed: [Fly] vault skill fly-deploy absent · [Context Efficiency] AGENTS.md > 16 KB
```

Identical to the 27.08 first run. **Interpretation: not "no regression" — "no visibility".** Four
defects measured below all post-date 27.08 and none of them moves this number.

**Box state at audit time**

| Metric | Measured | Source |
|---|---|---|
| Free physical RAM | **1 832 MiB** of 32 390 MiB (5.7 %) | `Win32_OperatingSystem` |
| C: free | **13.3 GB** free / 939.4 GB used (98.6 % full) | `Get-PSDrive C` |
| `.agents\logs` total | **95.0 MiB** across 7 files | `Get-ChildItem` |
| Claude hook wiring | 16 shared-harness `dispatcher.py` entries + 4 `_dispatch\dispatch.py` entries | `settings.json` grep |

**Cursor hook telemetry** (`~\.cursor\hooks.json` live since 27.08; window 27.08 05:44 → 29.08 22:55)

| Log | Lines | Bytes | Notes |
|---|---|---|---|
| `cursor-shell-guard.jsonl` | 5 697 | 2.32 MB | `hook_ms` min 87 · **p50 347** · p90 805 · p95 1 107 · p99 2 241 · max 8 591 · avg 452.4 |
| `cursor-afterfileedit.jsonl` | 4 518 | **94 918 180 (90.5 MiB)** | avg **20 925 chars/line**; 123 lines > 100 K; 10 lines > 1 M; max **3 728 848** |
| `estate-deny-guard.jsonl` | 4 614 | 1.07 MB | — |
| `cursor-mcp-guard.jsonl` | 926 | 0.85 MB | last write 19:01 |
| `cursor-subagent-lifecycle.jsonl` | 148 | 0.46 MB | last write **16:12** — see M6 |
| `guard-tamper.log` | 9 | 1 131 B | carries the unread alarms — see M1 |

Guard verdict distribution over 5 697 invocations: `ok` 5 684 · `would-deny` 8 · `force-push` 3 ·
`never-rotate` 2. **Zero organic deny-class hits** — all 13 non-`ok` entries are synthetic tracer
rounds or manual smokes.

---

## 2. Dedup — already built, NOT re-proposed

Verified live on disk this lens; any proposal to "do" these is a re-do.

| Item | Verified state |
|---|---|
| TIER-0 #1 registry/deny fix | `agents.json`: `markitdown` **and** `meta-tool` both `"enabled": false` with dated park notes |
| TIER-0 #2 Stop-event rebalance | `_dispatch\manifest.json`: Stop = **7** checks; `wire-check` (25 s) + `git-hygiene` (30 s) now under SessionStart with `settings_timeout: 35` and a `rebalance_note` |
| TIER-0 #5 budget pacing | statusline fields wired; prose corrected in all three rules files |
| TIER-0 #6 execpolicy git-write delta | `.codex\rules\default.rules` appended (drift receipt in `guard-tamper.log` 28.08) |
| B5 deterministic scorer | `harness-audit.js` exists and runs (107/120 reproduced above) |
| B1 Cursor hooks | `~\.cursor\hooks.json` live, 6 event families, `failClosed:false`, timeouts 15 s (before\*) / 10 s / 5 s |
| C1/C2 fail-closed doctrine + provenance | text present in `~\AGENTS.md` |
| D1 MEL registry + tracer round | `.agents\mel.md`, `guard-tracer-round.ps1`, tasks `GuardTamperTracer` 08:15 / `GuardTracerRound` 08:30 — **both firing daily, receipts in `guard-tamper.log`** |
| 29.08 remote-transport containment | `agents.json`: `context7` + `firecrawl` are `transport: http` at official remote URLs |
| Cursor MCP scope duplication | root-caused (home-as-workspace), **document-don't-edit** — unchanged, and now reinforced by M2 |

**Still genuinely open** from the prior waves: C3 enforcement (deliberately gated), D1's
`mcp-liveness` not yet reading `mel.md`, rectification-clock timers, the ISR telemetry substrate,
and the Wave-B flip decision (M4 changes what blocks it).

---

## 3. Measured findings

### M1 — Guard coverage regressed 5/5 → 2/5; the alarm fired twice and nobody read it — **CONFIRMED**

`C:\Users\Prekzursil\.agents\logs\guard-tamper.log`, verbatim:

```
2026-08-27T09:19:50+03:00 TRACER OK 5/5 contraband rounds flagged would-deny
2026-08-28T08:30:02+03:00 TRACER MEL-DEFERRAL guard failed to trip on: git push --force origin main | git reset --hard HEAD~3 | git clean -fdx | cat .env
2026-08-29T08:30:10+03:00 TRACER MEL-DEFERRAL guard failed to trip on: git push --force origin main | git reset --hard HEAD~3 | git clean -fdx | cat .env
```

Corroborated independently in `cursor-shell-guard.jsonl` (mechanically separate source — the guard's
own log, not the tracer's):

```
2026-08-27T06:20:22Z verdict="would-deny" git reset --hard HEAD~3
2026-08-28T05:30:02Z verdict="ok"         git reset --hard HEAD~3
2026-08-29T05:30:11Z verdict="ok"         git reset --hard HEAD~3
   (same 27→28→29 would-deny→ok→ok pattern for `git clean -fdx` and `cat .env`)
```

Cause, read from `shell-guard.ps1`: the 28.08 "P0 fix" rewrite replaced the classifier with
`Test-EstateDeny()` (lines 44–85) plus a 5-entry `$denyObserve` array (lines 96–102) containing only
`diskpart`, `format <drive>:`, `reg delete`, `bcdedit /delete`, `cipher /w`. **`git reset --hard`,
`git clean -fdx`, and `.env` reads are in no branch at all.** All three remain forbidden in
`~\.codex\rules\default.rules` → Codex is guarded, Cursor is not. That asymmetry did not exist on 27.08.

**One of the four reported misses is a tracer bug, not a guard gap:** `git push --force` *is* caught,
and harder than before (`Test-EstateDeny` → `verdict:"force-push"` → `{"permission":"deny"}`, an
upgrade from observe-only). The tracer asserts only `'"verdict":"would-deny"'`
(`guard-tracer-round.ps1:37`) and does not recognise the new AUTO-DENY verdict names
(`force-push`, `never-rotate`, `repo-public`, `no-verify`, `secret-file`). So the alarm is **3 real
misses + 1 false alarm** — and the false alarm is precisely what makes the whole line easy to dismiss.

This is the `alarm stewardship` / airworthiness case the 27.08 hunt predicted (lens 1 #4, lens 6 #2),
occurring for real: an instrument that works, reports to a sink with no reader, for two days.

### M2 — Cursor hooks fire ~2× per event — **MEASURED, mechanism MEDIUM confidence**

Consecutive byte-identical log lines after stripping `ts` and `hook_ms`:

| Log | Pairs identical to predecessor | Rate |
|---|---|---|
| `cursor-shell-guard.jsonl` | 2 964 / 5 696 | **52.0 %** |
| `cursor-mcp-guard.jsonl` | 305 / 925 | 33.0 % |
| `cursor-subagent-lifecycle.jsonl` | 50 / 147 | 34.0 % |

Three independent event families, all far above zero → this is a `hooks.json`-level property, not a
per-script quirk. Duplicate pairs are **3–10 ms apart** with identical `stdin_u16head` prefixes
(same `conversation_id` head), which is too fast and too correlated for two agents independently
issuing byte-identical commands.

Leading hypothesis: `~\.cursor\hooks.json` is loaded as **both** user-scope and project-scope because
the Cursor workspace root **is** `C:\Users\Prekzursil` — the identical mechanism already VERIFIED for
`~\.cursor\mcp.json` (`HARNESS-AUDIT_2026-08-27` Finding A: `user-*` **and**
`project-0-Prekzursil-*` namespaces from one file).

Cost, if confirmed: every shell command pays the guard twice — **~694 ms at p50, ~2.2 s at p95** —
and spawns two `powershell.exe` processes instead of one (~1 055 extra spawns/day at observed
volume) on the box whose binding constraint is RAM. It also doubles all log growth in M3.

Not excluded: Cursor may legitimately invoke `beforeShellExecution` twice (permission probe +
execution), and the 29.08 incident measured **six** concurrent Cursor Agent sessions. Settling
experiment in §5.

### M3 — `cursor-afterfileedit.jsonl` is an unbounded full-payload log — **CONFIRMED**

90.5 MiB / 4 518 lines in 2.68 days ≈ **33.8 MiB/day ≈ 1.03 GiB per 30 days**, and **95.3 % of all
`.agents\logs` volume**.

Cause is exact: `cursor-hook-log.ps1:26` serialises the *entire* hook stdin
(`ConvertTo-Json -Compress -Depth 8`) into a `"payload"` field, and Cursor's `afterFileEdit` payload
carries file content/edits. There is no size cap, no field projection, and no rotation anywhere in
the script. Result: avg 20 925 chars/line, 123 lines > 100 KB, 10 lines > 1 MB, max 3.73 MB.

Second-order cost, felt in this very lens: every analytical pass over that file costs a 90 MB scan
(**measured 55–74 s per shell pass** under current RAM pressure), so the log actively deters the
telemetry review it exists to enable.

### M4 — the recorded flip-gate blocker is stale; the real blockers are different — **CONFIRMED**

`WAVE-ABCD-EXECUTION_2026-08-27.md` B1 records: *"guard body took 4806ms under RAM pressure → the 2s
hook timeout will kill some invocations — this is exactly the flip-decision evidence."*

Measured now: that 4 806 ms sample is the **27.08 05:44** tracer round, pre-P0-fix. The
`beforeShellExecution` timeout is **15 s** since the 28.08 P0 fix (`hooks.json` `_readme`). Max
`hook_ms` across all 5 697 invocations is **8 591 ms** (also 27.08); post-fix latencies for the same
commands are **87–515 ms**. Under the live 15 s cap, **zero invocations exceeded budget**.

Against the three recorded FLIP CRITERIA:

| Criterion | Verdict |
|---|---|
| (1) latency / timeout rate acceptable | **MET** — p50 347 ms, p99 2 241 ms, 0 over the 15 s cap |
| (3) non-empty command excerpts (BOM-parse proven) | **MET** — commands present in every sampled line |
| (2) would-deny hit list shows no false positives | **NOT MET** — see M5, and M1 shows the hit list is itself incomplete |

So the flip is no longer latency-blocked. It is blocked by **coverage** (M1) and a **live deny
collision** (M5). Recording that correctly matters more than the flip itself.

### M5 — a live `permission:deny` rule fired on the estate's own MCP validator — **CONFIRMED, owner decision**

`cursor-shell-guard.jsonl`, 2026-08-29T08:27:43 (twice, 373 ms apart — M2 again):

```
verdict="never-rotate" command="cd '...\.agents\scripts'; python validate_mcp_control_plane.py
  --agents-config '...\agents.json' --rotation-manifest '...\credential_rotation_manifest.json'; ..."
```

Matched `shell-guard.ps1:46` — `if ($c -match 'credential[_-]?rotation[_-]?manifest')` — which is a
bare substring test over the whole command line with no mutation-verb requirement. Because
`never-rotate` is in the AUTO-DENY class, this emitted `{"permission":"deny"}` and blocked the
command. The blocked script is the read-only control-plane validator that the 29.08 incident report
cites for `SUCCESS:mcp-control-plane-validate`.

**I am deliberately NOT calling this a bug to be patched.** The estate lock reads *"do not rotate, do
not propose rotation, do not touch any credential-rotation manifest"* — under the letter of that
rule, denying a command that names the manifest is arguably correct behaviour. Two readings exist and
the choice is the owner's. My recommendation (D4) fixes the **caller**, not the guard, so the
NEVER-ROTATE surface is not weakened by one byte.

**Related, predicted but NOT yet observed** — the `secret-file` arm (`shell-guard.ps1:79–82`) matches
the bare word `token` in any `git add|commit|rm|update-index` command:
`(^|[\\/ ])(?!.*tokeniz)[^\\/\s]*token[^\\/\s]*`. Confirmed live FP surface in the vault:

```
.agents\skills\design-tokens-pipeline\fixtures\{before,after}.tokens.json
.agents\skills\design-tokens-pipeline\{extract_tokens,token_diff,validate_tokens}.mjs
.agents\skills\design-tokens-pipeline\tests\tokens.test.mjs
```

Any `git add` of those, **and any commit message containing the word "token"**, is denied. Zero
organic occurrences in 3 days of logs (background agents never commit, G-68), so this lands on the
**owner**, interactively, at commit time. The same lookahead is also a narrow bypass: appending
`tokeniz` anywhere in the command disables that arm (the `*.pem/*.key/local.json` arms still hold).

### M6 — the subagent-lifecycle instrument may be dark since 16:12 — **UNRESOLVED, flagged**

`cursor-subagent-lifecycle.jsonl` last write **2026-08-29T16:12**, while `cursor-shell-guard.jsonl`
wrote at **22:55** and `cursor-afterfileedit.jsonl` at **22:04** in the same session window. 148
lines in 3 days, and the file is **dual-purpose** — it also receives manual `"source":"deep-research"`
phase notes, so the count of genuinely hook-emitted lifecycle events is smaller than 148 and not
separable without a label. This is the instrument the harness built specifically for the standing
"subagents appear canceled / cut off mid-work" failure mode and for the deep-research 42 % hypothesis;
if it is dark, both remain unmeasurable. Not concluded — probe in §5.

### M7 — the scorer cannot see any of M1–M6

107/120 with all four confirmed defects live. The scorer exists (good) and is deterministic (good) but
its 12 categories are structural (files exist / parse / size / freshness). No category reads
`guard-tamper.log`, log volume, hook duplicate rate, or organic deny counts. Turning the existing
scorer into the reader for the existing alarms is the cheapest available reliability win — additive
checks, no new process, no new file.

---

## 4. Ranked deltas

Ranked by value × (1/effort), risk-adjusted. **Nothing below has been applied.**

| # | Delta | Value | Effort | Risk | Conf. |
|---|---|---|---|---|---|
| D1 | Restore Cursor guard coverage for the 3 real misses | **H** | L | L | high |
| D2 | Teach the tracer the AUTO-DENY verdict names | **H** | XS | L | high |
| D3 | Make the scorer read `guard-tamper.log` (alarm gets a reader) | **H** | L | L | high |
| D4 | Resolve the `rotation-manifest` deny collision **at the caller** | **H** | L | M | high |
| D5 | Cap + project + rotate hook payload logs | **H** | L | L | high |
| D6 | Settle the double-fire (experiment, then behavioural fix) | M-H | L (probe) | L | medium |
| D7 | Re-base the flip decision on current evidence (do **not** flip yet) | M | XS | M | high |
| D8 | Tracer-round the predicted `token`-word FP + `tokeniz` bypass before touching the regex | M | L | L | high |
| D9 | AGENTS.md > 16 KB — owner decision on what moves to `guides/` | M | L | L | high |
| D10 | Fly 0/10 — accept the row or delist the category; do not author a skill to satisfy a scorer | L | XS | L | high |

### D1 — Restore the 3 lost deny families
- **Target:** `C:\Users\Prekzursil\.agents\scripts\cursor-hooks\shell-guard.ps1`, `$denyObserve` array (lines 96–102).
- **Change:** add observe-mode patterns for `git\s+reset\s+--hard`, `git\s+clean\s+-(fdx|xdf|fd|fx)`, and `.env` reads (`\b(cat|type|Get-Content|more)\b.*\.env\b`). Mirror the wording already in `~\.codex\rules\default.rules` so the two runtimes agree. Keep them in `$denyObserve` (observe-only `would-deny`) — **not** in `Test-EstateDeny` — so nothing new starts blocking.
- **Test:** `powershell -File .agents\scripts\guard-tracer-round.ps1` then read `guard-tamper.log`; expect `TRACER OK 5/5` **after D2** also lands.
- **Rollback:** copy back from `.agents\backups\` (take a dated copy first); guard is fail-open by construction (`exit 0` on every path) so a broken edit degrades to "no guard", not "no shell".
- **Strongest evidence against:** if the owner deliberately dropped these three on 28.08 (e.g. `git reset --hard` is routine in this estate), then restoring them re-adds noise. Nothing in `WAVE-ABCD` or `hooks.json` `_readme` records such a decision, and `default.rules` still forbids them — so the balance of evidence is "regression", not "choice". Ask before assuming.

### D2 — Fix the tracer assertion
- **Target:** `guard-tracer-round.ps1:37` — `$after -match '"verdict":"would-deny"'`.
- **Change:** accept any non-`ok` verdict: `'"verdict":"(would-deny|force-push|never-rotate|repo-public|no-verify|secret-file)"'`.
- **Why it ranks above almost everything:** without it, D1's fix still emits a `MEL-DEFERRAL` naming `git push --force`, and a partially-false alarm is an alarm that gets ignored — which is the exact failure M1 documents.
- **Test:** run the tracer twice (once before D1, once after) and diff the `guard-tamper.log` lines.
- **Rollback:** one-line revert.

### D3 — Give the alarm a reader (no new process)
- **Target:** `C:\Users\Prekzursil\.agents\scripts\harness-audit.js` — add deterministic checks to the existing rubric.
- **Checks:** (a) FAIL if `guard-tamper.log` contains a `MEL-DEFERRAL` line with a timestamp newer than 48 h; (b) FAIL if `.agents\logs` total bytes exceed a threshold (propose 256 MiB) or any single log exceeds 32 MiB; (c) WARN on hook duplicate-fire rate > 10 % sampled over the last N lines of `cursor-shell-guard.jsonl`; (d) report organic (non-tracer) deny-verdict count.
- **Constraint fit:** the scorer is invoked on demand and by `sync_shared_state.ps1` as a post-sync check — **no daemon, no scheduled task added**.
- **Test:** run before/after D1; the MEL check must go FAIL → PASS, and (b) must be FAIL today (95 MiB is under 256 MiB but `cursor-afterfileedit.jsonl` at 90.5 MiB trips the per-file rule) → PASS after D5.
- **Rollback:** the scorer is additive and read-only; revert the file.
- **Strongest evidence against:** a scorer that fails on transient log growth becomes a nag and gets ignored like every other alarm. Mitigation: per-file cap only, thresholds set well above steady state after D5.

### D4 — Resolve the rotation-manifest collision without weakening the guard
- **Owner decision, two readings stated in M5.** Recommended path (zero guard change): stop passing the manifest path on the command line — have `validate_mcp_control_plane.py` read it from `agents.json`/config, or run the validator without `--rotation-manifest`. Target: the **caller**, `.agents\scripts\validate_mcp_control_plane.py` invocation sites.
- **Alternative (requires explicit owner sign-off):** narrow `shell-guard.ps1:46` to mutation contexts only. I do **not** recommend an agent making this edit unilaterally — it weakens a NEVER-ROTATE surface, which the estate locks put beyond agent discretion.
- **Test:** re-run the validator command; expect `verdict:"ok"` and a successful validate; then confirm a genuine rotation attempt still denies.
- **Rollback:** caller-side change only.

### D5 — Cap, project, and rotate the payload logs
- **Target:** `C:\Users\Prekzursil\.agents\scripts\cursor-hooks\cursor-hook-log.ps1` lines 24–36.
- **Change:** (a) cap the serialised payload (propose 4 096 chars, truncation marker retained); or better, project only the fields the analyses actually use (`hook`, `file_path`, `edit count`, `conversation_id`) instead of the whole stdin; (b) in-script size roll — if the target log exceeds N MiB, rename to `<name>.1` before appending. Both are inline in a script that already runs per event: **zero new processes**, honouring the no-new-daemon constraint.
- **Preserve, don't remove:** the `afterFileEdit` instrument stays on. If the full payload is genuinely wanted for forensics, propose a separate opt-in `-FullPayload` switch rather than deleting the capability — flagging this explicitly because "shrink the log" must not become "lose the evidence".
- **Test:** edit one file, confirm a new line appears, assert `line.Length < cap`; force a roll with a synthetic oversize write and confirm `<name>.1` appears.
- **Rollback:** restore the script from a dated backup; the existing 90.5 MiB file should be **moved to `.agents\backups\`, never deleted** (file-rules: no permanent deletion).
- **Strongest evidence against:** at 33.8 MiB/day against 13.3 GB free, disk exhaustion is roughly a year away — so the *disk* argument alone is weak. The real, measured cost is scan latency (55–74 s per pass) and RAM during any telemetry review. Ranked on that, not on scaremongering.

### D6 — Settle the double-fire
- **Probe A (decisive, read-only, no config change):** open a **non-home** folder as the Cursor workspace, run 10 identical benign shell commands, count new lines in `cursor-shell-guard.jsonl`. 20 ⇒ double-fire is intrinsic; 10 ⇒ home-as-workspace scope duplication confirmed.
- **Probe B (cheap, offline):** widen `stdin_u16head` capture (currently 24 code units, `shell-guard.ps1:118`) to ~64 so the full `conversation_id` is visible; then duplicate pairs sharing an id prove double registration rather than two sessions.
- **If confirmed, the fix is already the documented recommendation** — stop opening `C:\Users\Prekzursil` as a workspace root (`HARNESS-AUDIT_2026-08-27` Top Action 1). This lens does not add a new item; it adds a **second, quantified justification** (hook latency + spawn count + log volume, on top of the known MCP-mount doubling), which should raise its priority.
- **Confidence:** measurement high, mechanism medium. Six concurrent sessions were measured on 29.08, so the competing explanation is live and must be excluded by Probe A.

### D7 — Re-base the flip decision
- **Target:** the FLIP CRITERIA text in `~\.cursor\hooks.json` `_readme` and the B2 row in `WAVE-ABCD-EXECUTION_2026-08-27.md`.
- **Change:** record that criterion (1) is MET (0/5 697 over the 15 s cap; the cited 4 806 ms is a stale pre-P0 sample) and that the live blockers are now D1/D2/D4. **Do not flip `would-deny`→`deny` or `failClosed:true` yet** — flipping while coverage is 2/5 and a deny rule has a known collision would enforce an incomplete, mis-calibrated ruleset.
- **Test:** none needed (documentation), but it must be a text change, not a config change.

### D8 — Measure the predicted `token` FP before editing the regex
- Add three rounds to `guard-tracer-round.ps1`: `git add .agents\skills\design-tokens-pipeline\fixtures\after.tokens.json`, `git commit -m "add design tokens pipeline"`, and `git add mytoken.txt # tokeniz` (bypass probe). Expect deny, deny, allow — which quantifies both the FP and the bypass before anyone touches a security regex. Measure first, then decide.

### D9 / D10 — the two scorer failures
- **D9:** AGENTS.md exceeds 16 KB and is paid every turn by every runtime. Owner decision on which sections move to `guides/` behind pointers. Candidates by size and staleness: the marker-delimited AgentBridge forensics block (retired capability, ~66 lines of 2026-08-08 measurement detail) and the estate-locks rationale, keeping the operative rules inline. **Do not** move any binding rule text out without owner approval — that would be a silent capability downgrade.
- **D10:** Fly 0/10. Authoring a `fly-deploy` skill purely to move a scorer row is Goodharting a metric nobody is using. Recommend either accepting the 0 with a documented reason or removing the category from the rubric — an explicit owner choice, not a build.

---

## 5. Settling experiments for what I did **not** measure

| Open question | Experiment | Cost |
|---|---|---|
| Is the double-fire scope duplication or intrinsic? | D6 Probe A / B | ~5 min, read-only |
| Are `subagentStart/Stop` hooks still firing? (M6) | Add a distinguishing `-Label lifecycle-hook` arg to the `cursor-hook-log.ps1` invocations in `hooks.json`, spawn one subagent, check for a labelled line; separates hook events from manual `deep-research` notes in the shared file | ~10 min |
| Claude-side per-tool-call process cost (16 shared-dispatcher + 4 `_dispatch` entries) | Time 20 identical trivial tool calls with the dispatchers enabled vs `HOOKS=off`, and count `python.exe` spawns via a sampled process snapshot. The 27.08 hunt graded this **PARTIALLY VERIFIED** (2 always) — it is still not quantified in ms | ~15 min, Claude runtime only |
| Do the 3 restored deny families produce organic noise? | After D1, count `would-deny` verdicts over 48 h; > ~5 organic/day means the pattern is too broad | passive |
| Is `estate-deny-guard.jsonl` (4 614 lines) a third writer with its own duplicate/volume profile? | Not opened this lens — same duplicate + volume analysis as M2/M3 | ~2 min |

---

## 6. Key Assumptions Check

| Assumption | Impact if wrong | Confidence | Basis / disconfirming evidence |
|---|---|---|---|
| The 3 tracer misses are a regression, not a deliberate 28.08 narrowing | D1 re-adds unwanted noise | **medium-high** | Two mechanically independent sources agree (tracer receipts + the guard's own verdict log); `default.rules` still forbids all three; but no explicit "we dropped these" record exists either way — **ask the owner** |
| `verdict:"ok"` in the guard log means the command was actually permitted | M1's severity | high | `shell-guard.ps1:106` emits `{"permission":"allow"}` on every non-`Test-EstateDeny` path — read directly |
| The 52 % duplicate rate reflects double invocation, not double logging | D6 targets the wrong layer | medium | Both duplicates carry distinct `hook_ms` values (254/259, 225/227), i.e. two independent script runs, not one run writing twice |
| Cursor's `afterFileEdit` payload is what makes lines 20 KB | D5's projection fix | high | `cursor-hook-log.ps1:26` serialises all of stdin at depth 8; measured max line 3.73 MB matches file-content scale |
| `never-rotate` on the validator is a rule-vs-intent collision, not a guard defect | D4 direction | high | Estate lock wording is literally "do not touch any credential-rotation manifest" — which is why D4 changes the caller, not the rule |
| The 15 s timeout is live for `beforeShellExecution` | M4's criterion-(1) verdict | high | Read directly from `hooks.json` (`"timeout": 15`), consistent with the 28.08 `_readme` P0 note |
| `harness-audit.js repo` scores the live harness | Baseline meaning | **medium** | The `repo` argument suggests a mode selector I did not inspect; the failed checks cite live paths (`C:\Users\Prekzursil\AGENTS.md`), so it reads live files — but I did not read the scorer source. Verify before trusting the number as a live gate |

**Highest-impact / lowest-confidence pair:** the double-fire mechanism (M2/D6). It carries the largest
throughput claim in this lens and rests on inference plus a documented precedent, not on a controlled
test. That is why D6 is written as a probe, not a fix.

---

## 7. Not proposed (and why)

- **No new resident daemon, watcher, or service** — D3 and D5 are deliberately built into scripts that already run on demand or per event.
- **No second `cursor-agent`, no parallel agent fan-out** — free RAM measured 1 832 MiB; `agent worker start` stays forbidden below 8 GB (G-26).
- **No credential rotation, no rotation-manifest edit, no rotation proposal** — D4 routes around it entirely.
- **No basic-memory change, no vector layer, no second memory writer** — out of lens scope and locked (G-81).
- **No skill pruning / family merges / active-cap** — carried as PLANNED-UNBUILT with a NEEDS-OWNER-DECISION list since 27.08; nothing measured today changes that, and renaming skills agents already know is not a reliability win.
- **No `failClosed:true` and no `would-deny`→`deny` flip** — M4: evidence now permits it on latency, but D1/D2/D4 must land first.
- **No deletion of the 90.5 MiB log** — it moves to `.agents\backups\` if D5 is taken.
- **No edits of any kind this lens** — instructed read-only; every delta above is a proposal with a named target, test, and rollback.

---

## 8. Bottom line

The harness's reliability problem today is **not missing instruments — it is unread ones.** The tracer
round, the tamper tracer, the guard log, and the deterministic scorer all exist and all run. Two of
them recorded a real regression and a real deny collision within the last 48 hours, and the scorer
that is supposed to summarise harness health cannot see either, so it reported an unchanged 107/120
while coverage silently fell to 2/5.

D1 + D2 + D3 are one sitting's work, all reversible, all additive, no new processes — they restore the
lost coverage, make the alarm trustworthy, and connect it to the one number anyone actually reads.
D4 and D5 remove a live false block and 95 % of log volume. Everything past that should wait for the
D6 probe, because the largest throughput claim in this report is still an inference.

UNIT-COMPLETE: lens-12
