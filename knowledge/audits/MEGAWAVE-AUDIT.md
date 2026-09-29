# MEGAWAVE ADVERSARIAL AUDIT — 2026-09-28

Auditor: independent workflow subagent (Opus 4.8, fresh context). Scope: lanes A-F artifacts under
C:/Users/Prekzursil/.agents/knowledge/audits/MEGAWAVE-{A,B,C,D,E,F}/, lane C scripts/state, PR #359.
Method per lane: (1) Test-Path every claimed artifact dir/file; (2) >=2 receipt spot-checks re-executed
against reality; (3) overclaim hunt (claims wider than evidence); (4) NO-DOWNGRADE gate check on the McpHub PR.
Label key: VERIFIED = exact command + output below. INFERRED = reasoning, with band.

## Verdict summary

| Lane | Verdict |
|---|---|
| A (classify + PR 359) | CONFIRMED |
| B (D2 dead-port + registry endgame, read-only) | CONFIRMED |
| C (supervise -ProcessNameFallback + bm re-pilot) | CONFIRMED |
| D (cache_lens compare + T5 defect) | CONFIRMED |
| E (PR verdict sheet + L-22 journal read) | CONFIRMED (1 timeline nuance, not an overclaim) |
| F (VM parity + home-stale runbook) | CONFIRMED (2 timeline notes from later lane-C events) |
| McpHub PR NO-DOWNGRADE gate | PASS — branch deletes NOTHING vs main; zero tests/gates/.github paths touched |

## Lane A — CONFIRMED

Artifact dir exists: 7 files (classify-input.txt 15,500B; drift-report.json 689,354B; lane-A-artifact.md 8,753B; pr-body.md; scoped-reconcile-list.txt; scoped_reconcile_copy.py; empty stderr). Digest claims -> receipts:

- PR 359 VERIFIED: gh pr view 359 -R Prekzursil/agent-skills-toolchain -> {"headRefName":"fix/mcp-hub-multi-client-sticky-20260924","isDraft":true,"number":359,"state":"OPEN","title":"McpHub multi-client consolidation (preserved + classified)"} — draft, correct branch, exact title.
- Commit 1 VERIFIED: git show --shortstat d9e1ce4b4 -> "30 files changed, 1935 insertions(+)", subject "mcphub consolidation: preserved working-tree feature work". Commit 2 VERIFIED: 468721204 -> "24 files changed, 954 insertions(+), 655 deletions(-)", subject matches. Both on branch; branch status -sb shows no ahead/behind (in sync with upstream) — matches M5.
- M1 VERIFIED: wc -l classify-input.txt = 214.
- M8 VERIFIED: git rev-list --count --branches --not --remotes = 120 (the artifact's 56-tip attribution NOT re-counted tip-by-tip — INFERRED high, arithmetic consistent).
- Overclaim hunt: NONE. The artifact self-labels COMMIT2 SKIPPED with rationale and states the PR merge-gate is documented-not-executed — honest scoping. Secret-scan and index-lock removal claims are transcript-scoped (not re-runnable; absence of locks on disk is consistent).

## Lane B — CONFIRMED

Artifact dir exists (endgame-plan.md 24,274B). The lane is explicitly read-only (proposals only) — and nothing was applied: VERIFIED semgrep still enabled:true in agents.json (its proposed P1 flip is NOT applied, consistent with its own claim).

Receipt spot-checks (re-executed):
- Port re-probe (TcpClient): :31119 CLOSED (claimed CLOSED — the P1 defect), :24680 OPEN (McpHub), :18765 OPEN (basic-memory), :31101 OPEN (sliver-full port-alive/MCP-dead; my own session's MCP banner shows sliver-full CONNECT_TIMEOUT — an independent second signal agreeing), bonus :7870 OPEN (biomni "now live" INFERRED-high in the doc — holds).
- Registry VERIFIED: mcp.servers count = 97; root mcpServers keys = biomni only; semgrep enabled = True; McpHub enabled = True.
- .mcphub/config.json VERIFIED: all 10 keep-list children present (codex/github_cli/ocr-suite/openmm-md/paper-search/perplexity/postgres/rdkit/sonarqube/codacy); "codacy": { at line 38 and "codex": { at line 401 — the doc's cited line refs are exact; codacy uses @codacy/codacy-mcp@latest (unpinned — P4 claim holds).
- Dead-band VERIFIED: grep -cE '314[0-9][0-9]|3138[0-9]' -> 0 hits in agents.json and .mcp.json.
- Fleet lib VERIFIED: sed -n 78p D:/opt/cyberstrike-mcp/cyberstrike-mcp-lib.ps1 -> "Name = 'semgrep'; Port = 31119; Band = 'Core'" — exact.
- Overclaim hunt: NONE. Docker-image presence and VM-state stay honestly marked UNVERIFIED in the doc itself.

## Lane C — CONFIRMED (strongest lane: every receipt re-executed)

Files exist: supervise.ps1 (38,041B), supervise.selftest.ps1 (28,875B), supervise.selftest marker.

Receipt spot-checks (re-executed):
- Selftest re-run VERIFIED: pwsh -NoProfile -File C:/Users/Prekzursil/.agents/scripts/supervise.selftest.ps1 -> "controls: 31  passed: 31  failed: 0" + "SUCCESS:supervise-selftest 31/31" (this audit's own run 2026-09-28 ~17:46; output preserved at MEGAWAVE-AUDIT-selftest-rerun.txt next to this file).
- Push receipt VERIFIED: git -C C:/Users/Prekzursil/.agents ls-remote origin refs/heads/live-capture/2026-09-02 -> 6a206a7e45d5daee97bb6d1cb6d9e3b39cc52198 — the claimed FF tip, second signal after the claimed push output.
- Code VERIFIED: supervise.ps1 has [switch]$ProcessNameFallback (:109), Get-SupFallbackNeedle (:304), rewritten Get-SupLivePid (:332), weak-needle WARN (:373) — semantics match the artifact.
- Runtime state VERIFIED: events log carries "FOUND-BY-FALLBACK pid=47324 (name /basic-memory/ + needle '18765')" and consecutive "tick verdict=HEALTHY alive=True pid=47324 readiness=READY/0 churn=26 latched=False" lines; state json = lastVerdict HEALTHY, latched False, churnTotal 26, ownPid 47324 — exact match to the artifact's kill-drill end-state. Direct probe bm_ready.py -> "READY via 172.19.16.1", exit 0.
- Overclaim hunt: NONE — the ~70% INFERRED band on chain-completeness and the disclosed operator incidents are honest. Note: local branch state is now ahead-1/behind-4 vs the post-push remote (artifact said behind-3 vs the then-fetched ref) — the registered OPEN-LOOP (clean-tree git pull --rebase) still stands, slightly grown.

## Lane D — CONFIRMED

Artifact dir exists (benchmark-compare.md). Baseline ref exists (E2E-BASELINE-2026-09-28/baseline.txt).

Receipt spot-checks (re-executed):
- Baseline VERIFIED: baseline.txt cache_lens block = files 18445, raw_usage_lines 1132915, deduped 463528, hit_rate 94.28, cold_rewrites 8266, cold_cost 1244871411, cc 5214538655 — every number in the artifact's table matches the on-disk baseline; flagged head (30bd50d4/99,770,965, dea94f05/75,043,646, d219bc39/73,478,726) matches.
- Current re-run VERIFIED: python cache_lens.py --json (this audit) -> cold_rewrites 8266, cold_cost 1244871411, cc 5214538655, hit_rate 94.29 — byte-identical to the artifact's cited current values on all stable metrics; files 18553 (+1) and raw lines +294 are ordinary corpus growth after the artifact's write, consistent with its own growth explanation. SUCCESS:cache_lens marker present (output preserved at MEGAWAVE-AUDIT-cachelens-rerun.json).
- T5 defect VERIFIED by re-run: node agentWithFallback.test.js (C:/Users/Prekzursil/.claude/workflows/snippets/) -> "7/8 PASS", "FAIL T5 ... 'REFUSAL' !== 'ERROR'" — exactly the claimed failure. Root cause confirmed at agentWithFallback.js:42: REFUSAL_RE = /refus|safeguard|usage[ _-]?policy|.../i — bare "refus" substring-matches ECONNREFUSED. The proposed fix (\brefus(?:ed|al)\b in BOTH snippet and test copy, per T8) is still NOT applied — defect is live, matching the no-papering claim.
- sota Tier 3 VERIFIED: "### Tier 3 — fleet/workflow resilience" at sota-2026-09.md:81.
- Overclaim hunt: NONE — harness-bench post-wave re-run honestly marked UNMEASURED (not claimed as done).

## Lane E — CONFIRMED (one timeline nuance)

Artifact dir exists (PR-VERDICT-SHEET.md 13,761B; L22-journal-read.md 6,570B).

Receipt spot-checks (re-executed):
- Journal VERIFIED: C:/Users/Prekzursil/.claude/projects/C--Users-Prekzursil/027fa5cb-1562-482e-a2e1-6a2f57530cb6/subagents/workflows/wf_e66e9b4d-330/journal.jsonl exists with exactly 16 type:result lines and 3 type:failed lines — matches the sheet's provenance claim. Agent a795223d3573e15ec -> label analyze:#355 -> action REBASE_THEN_MERGE — the #355 verdict is the agent's own on-disk record, not invention.
- PR metadata VERIFIED: spot rows today: #355 isDraft:false, mergeable MERGEABLE, mergeStateStatus BLOCKED; #325 isDraft:true, CONFLICTING/DIRTY; #310 CONFLICTING/DIRTY — all match the sheet. #316 CLOSED 2026-09-27T20:48:13Z, #319 CLOSED 2026-09-27T20:48:16Z — the sheet's "both CLOSED 2026-09-27T20:48" is exact.
- L-22 absence VERIFIED (re-probe): find .claude/projects -name *ac30a9af* -> zero hits — the journal-absent verdict re-confirmed on this host.
- Timeline nuance (NOT an overclaim): sheet title says "29 open PRs"; today the count is 30 — the delta is exactly PR #359 (created by lane A minutes before the sheet's mtime). The sheet never claims to include #359 and its 29 rows all verify; the list command evidently ran before #359 was visible (file mtimes bracket the ordering — INFERRED, high). Recommendation unchanged.
- Overclaim hunt: NONE. The sheet separates AGENT-CLAIMED vs VERIFIED-TODAY, asserts CI-green nowhere, and states fail-closed explicitly.

## Lane F — CONFIRMED (two timeline notes from later events)

Artifact dir exists (vm-parity.md 7,835B).

Receipt spot-checks (re-executed):
- Home git VERIFIED: C:/Users/Prekzursil/.agents is a git repo on live-capture/2026-09-02; gh api repos/Prekzursil/agent-skills-toolchain/compare/5894ce61...ee21a2fb -> {"ahead_by":3,"behind_by":0,"status":"ahead"} — the "home is the stale side, 3 FF-able commits" bonus finding is exact.
- Impl paths VERIFIED: D:/ReverseTools/mcp/paper-search-mcp/venv/Scripts/paper-search-mcp.exe exists, Length 108,366 — byte-exact to the claim; agents.json Length 87,938, LastWriteTime 01:55:51 — exact to the claim (incl. its probe-time mtime).
- VM ports re-probed VERIFIED: 100.117.115.55 -> 22 CLOSED/TIMEOUT, 3389 OPEN, 5985 OPEN — identical to the lane's measurements; its sshd-BLOCKED verdict rests on a real, still-current condition.
- Timeline notes: (1) home HEAD is now a17951775 (lane C committed after lane F snapshotted at 5894ce61); (2) origin live-capture tip is now 6a206a7e4 (lane C's push). Both post-date the artifact; its values were true at run time. Consequence: the FF-only restore runbook is stale-by-events (local carries lane C's own commit; remote carries its cherry-pick) — fold into lane C's registered rebase open-loop rather than executing the runbook verbatim. VM-parity "VM == ee21a2fb0" is likewise now "VM 1 behind" — stale, not wrong.
- Overclaim hunt: NONE — rail failures (McpHub exec, cursor-bridge wedge) disclosed rather than hidden; credential directive honored.

## McpHub PR 359 — NO-DOWNGRADE gate: PASS

VERIFIED (repo C:/Users/Prekzursil/source/agent-skills-toolchain, branch fix/mcp-hub-multi-client-sticky-20260924):
- git diff origin/main...HEAD --stat | grep -E 'tests/|gates/|\.github/' -> EMPTY (no test/gate/CI path touched at all).
- git diff origin/main...HEAD --name-status | grep ^D -> EMPTY — the branch deletes NOTHING vs main (total diff: 66 files, +4,006/-615, additive/modified under feature+docs areas).
- Answer to the gate question: the branch does NOT delete tests/gates/capability vs main. Gate inputs are clean.

## Residuals / open loops surfaced by this audit

1. Lane C's registered open-loop (local .agents branch clean-tree git pull --rebase) is now ahead-1/behind-4 — same loop, bigger; keep registered.
2. Lane D's T5 defect is LIVE on disk (agentWithFallback.js:42) and re-proven — the proposed \brefus(?:ed|al)\b tightening (snippet + test copy together, per T8) remains the correct follow-up.
3. Lane B's P1 (semgrep front :31119 down while enabled=true) remains live — re-verified CLOSED this audit; owner choice (restart hub fleet vs flip+sticky) still pending.
4. Lane E's sheet should carry a one-line note: "29 open" predates #359; current open = 30.
5. Lane F's FF restore runbook is stale-by-events; supersede with lane C's rebase loop (item 1) — do NOT run merge --ff-only blindly.

## Per-lane terminal markers

SUCCESS:lane-A · SUCCESS:lane-B · SUCCESS:lane-C · SUCCESS:lane-D · SUCCESS:lane-E · SUCCESS:lane-F · SUCCESS:no-downgrade-gate
