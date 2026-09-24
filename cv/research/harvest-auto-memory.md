# Harvest: Claude auto-memory → resume evidence + professional character

Source mined: `C:\Users\prekzursil\.claude\projects\C--Users-prekzursil\memory\` (18 topic files + `MEMORY.md`, 83,044 bytes total).
Cross-referenced (read-only) against the vault `D:\basic-memory` and against public GitHub / Zenodo. Written 2026-09-23.

Label convention used throughout: **VERIFIED-LOCAL** (read in a local auto-memory file), **VERIFIED-VAULT** (read in a D:\basic-memory note), **VERIFIED-PUBLIC** (fetched from GitHub/Zenodo this session), **INDEX-ONLY** (exists only as a one-line entry in MEMORY.md; its detail file is missing locally and the number is absent from all 713 vault notes), **INFERRED** (my reading, not a checked fact).

---

## 0. Method, and two instrument failures worth recording

1. Read every one of the 18 local files in full, plus `MEMORY.md` (93 lines, 20,575 B, md5 `ce956380c774d8c2585b96da8c34d440`).
2. `MEMORY.md` links 75 distinct local filenames; **73 are missing from the local directory** (only `project_faers_v2_dedup_2026-09-15.md` and `reference_metaswarm_sessionstart_latency_2026-09-19.md` resolve). The estate-audit note explains why: on 2026-09-19 the index was trimmed "21.3→17.3KB, zero titles lost" and detail files were archived. Two entries point explicitly into basic-memory (`main/projects/program-r-autonomous-research-loop-2026-07-26`, `main/projects/prompt-two-waves-4-5-platform-ci-lane-2026-08-10`); both resolve in the vault.
3. The vault folder `D:\basic-memory\claude-memory\root\` holds an **older snapshot of the index** (`MEMORY.md`, 21,995 B, May-June 2026 era) plus ~50 archived auto-memory files, 11 of which are among the 73 missing targets (`feedback_full_rigor`, `feedback_peer_review`, `feedback_parallel_agent_worktree`, `feedback_workflow_orchestration`, `reference_agent_skills_toolchain`, `agent_monitor_tool`, `claude_code_401_auth_notes`, `claude_swap_install`, `disk_cleanup_c_drive`, `feedback_mcp_enabled_state`, `scholarly_access_mcp`). All read.
4. **Instrument failure #1:** a vault-wide `grep -r` aborted with exit 134 on one batch, and a later `grep -ril "codex audit"` returned nothing although `harness/Config-drift audit + auto-compact fix 2026-07-13.md` visibly contains that string. Every "absent from the vault" verdict below was therefore re-proven with a Python `os.walk` scan over all 713 `.md` files (`scratchpad/vault_scan.py`), which is grep-independent. That scan is the authority for the INDEX-ONLY labels.
5. **Instrument failure #2:** unauthenticated GitHub REST hit the 60/hour limit mid-probe (releases, PR #152, metaswarm PR #51 returned 403). Those facts were re-fetched from the public HTML pages instead. `gh` is not on PATH in either shell on this box.
6. Nothing in `D:\basic-memory` was modified. No credential value was printed; where a note mentions credentials, only the fact that it does is recorded.

---

## 1. The 18 local files — what each establishes

| File | Date | What it establishes (resume angle) |
|---|---|---|
| `user_author_identity.md` | 09-14 | Byline facts: Andrei Mihai VISALON, ORCID 0009-0001-8776-8498, `andrei-mihai.visalon@s.unibuc.ro`, University of Bucharest. States the official English faculty name is **"Faculty of Mathematics and Computer Science"** and that "Informatics" is a mistranslation to avoid. |
| `feedback_no_ai_disclosure_in_manuscripts.md` | 09-17 | Owner rule: never add AI-use disclosure to his manuscripts. (Relevant to how AI-assisted work is framed on a resume: the owner does not want AI attribution in academic outputs; a resume is a different document, see §5.) |
| `project_faers_v2_dedup_2026-09-15.md` | 09-15 | The strongest single research artifact in this source: an openFDA FAERS disproportionality re-analysis with receipts (see §3.E). |
| `project_webcoder_wave_delivered_2026-09-22.md` | 09-22 | WebCoder CRA→Next 15 modernization delivered as draft PR #152; test receipts; delegation program artifacts (see §3.H). |
| `project_estate_mcp_tui_audit_2026-09-19.md` | 09-19 | Estate-wide MCP/TUI audit: 81 servers / 14 surfaces, 34 agents, 3.9M tokens, 96 adversarial verifications (81 CONFIRMED / 13 REFUTED, 22 contradictions adjudicated); D1-D25 plan executed in phases 2/2b/2c/2d/2e; **upstream PR filed: dsifry/metaswarm#51**. |
| `reference_metaswarm_sessionstart_latency_2026-09-19.md` | 09-19 | Diagnosed a 140.5 s SessionStart hook from transcript telemetry, gated it to 0.305 s (identical output), packaged as an idempotent `reapply.py` patch; upstream PR drafted. |
| `project_biomni_local_install_2026-09-20.md` | 09-20 | Stanford Biomni installed in WSL2 with the full E1 environment (41 R packages, 7 CLI tools, 14 GB data lake); three compile/toolchain root causes fixed; acceptance run with plink2. |
| `project_biomni_mcp_browser_2026-09-20.md` | 09-20 | Built a FastMCP server for Biomni (3 tools, handshake-verified), proved Gradio 5.50's native MCP mount dead by reading `blocks.py`; 13-agent browser-extension research verdict. |
| `reference_cs_local_stdio_connector_2026-09-20.md` | 09-20/22 | Wired a local stdio MCP into Claude Science's bwrap sandbox: a 7-layer fix chain (https-only rule, CSRF header, `user_read_paths`, HOME remap, socksio, banner crash, `.env` nulled by design); tool-call-proven (`tools=224`). |
| `project_claude_science_glm_bridge_2026-09-20.md` | 09-20 | Recovered a broken Claude Science daemon through three stacked failure layers (missing `socat` → exit 127; logged-out daemon; wrong account) and built a two-plane local router so `/v1/messages` goes to a GLM endpoint while the OAuth plane stays on Anthropic. |
| `project_rvc_voice_changer_2026-09-20.md` | 09-20/22 | Built a real-time RVC voice changer (vendored RVC tag 2.3.260718, Gradio GUI, Modal H100 training, cloud WebSocket relay); measured RTF 0.80 @ 100 ms on an RTX 4050; found NaN-poisoned checkpoints from fp16 AMP; built resemblyzer timbre gate; concluded the local path could not deliver identity from dirty source audio and pivoted to ElevenLabs IVC (v2 clone mean sim 0.602→0.667). |
| `reference_partial_remediation_global_claim_2026-09-18.md` | 09-17 | The canonical "caught my own system lying" note: fixed 4 of 6 fail-open verification gates, then a README claimed all were fail-closed; two still `sys.exit(0)`; the false claim shipped in a Zenodo archive. Fix = `verify_gate_controls.py`, a harness that runs every gate on good input (must pass) and on an injected defect (must fail). |
| `reference_layered_gate_unmasking.md` | 09-19 | Serial `bash -e` CI steps hide one layer per push (five pushes, five layers); run the whole battery locally in CI order. |
| `reference_git_pathspec_commit_trap.md` | 09-19 | `git commit -- <paths>` snapshots working-tree state and silently restored 12 staged deletions; verify with `git ls-files` after the commit. |
| `reference_tool_absence_misattribution_2026-09-22.md` | 09-22 | A subagent claimed "no native tools" while its transcript showed successful native calls; countermeasure rule shipped same day. Also pins a real WebCoder defect (`permissions.py:82 obj.author` vs `.user`). |
| `reference_workflow_resume_semaphore_gotchas_2026-09-19.md` | 09-19 | Three measured orchestration defects: resume-after-edit cache miss (journal-salvage pattern), a while-loop semaphore deadlock, prefix-truncated cache keys causing 9 redundant re-runs. |
| `reference_workflow_tool_available.md` | 09-19 | Process note (tool-search pattern specificity). Low resume value. |
| `MEMORY.md` | 09-22 | The 93-line index; ~90 entries; dominated by verification lessons (see §4). |

---

## 2. The headline numbers: what is actually claimed, and where the evidence stops

| Index line (verbatim fragment) | Detail file present? | Vault has the number? | Status |
|---|---|---|---|
| "500-unit Codex fan-out; 2 exploit-proven defects" (Program R, 07-26) | no (points to basic-memory) | **yes** — `projects/Program R autonomous research loop 2026-07-26.md` | VERIFIED-VAULT |
| "1000-agent/12.1h audit died pre-synthesis; 42% of 225 findings REFUTED at 89% self-rated confidence" (07-30) | no | **no** (Python scan: 0 hits for 1000-agent, 12.1h, 42%, 225 findings) | INDEX-ONLY |
| "97-slice pure-CODEX audit (0-fail) → 1582 findings, 3 crit RCE + 5 systemic causes" (07-13) | no | **no** (0 hits for 1582 / 1,582 / 97-slice / pure-codex); the vault note `harness/Config-drift audit… 2026-07-13` wikilinks `[[Reframe codex audit 2026-07-13]]`, which does not exist as a note — a dangling link | INDEX-ONLY |
| "corpus 12,272 rec" (harness reconcile + corpus wave, 07-19) | no | **no** (0 hits for 12,272 / 12272) | INDEX-ONLY |
| "FAERS … N=20.69M vs LOC … N=20.33M" (09-15) | **yes** (local) | yes (`phenibut/Paper B placed…`, Zenodo description) | VERIFIED-LOCAL + PUBLIC |
| "26-repo fleet" (CLAUDE.md, fleet notes) | — | **yes** — decision brief 2026-07-11: "18 public + 8 private" GitHub repos; "a nightly ~26-repo sweep" | VERIFIED-VAULT |
| "Reframe v1.4.1 SHIPPED… 1.4.2 SHIPPED… v1.5 ultracode" | no | partial (v0.1.0 release note; 1.4.2 install/build notes) | VERIFIED-PUBLIC for tags v0.1.0…v1.4.1; **no public v1.4.2 tag exists** |
| "draft PR #152 (Next 15 port, 295 tests…)" (09-22) | **yes** (local) | session capture only | VERIFIED-PUBLIC (PR title carries "295-test suite") |

The three INDEX-ONLY items are exactly the three most quotable numbers. Nothing on this machine or in the vault can substantiate them beyond a one-line summary written by an assistant at compaction time. They should not go on a resume unless the owner can re-derive them from the workflow journals (`~/.claude/projects/.../subagents/workflows/wf_*/journal.jsonl`) or the Reframe repo history; the vault's own guidance says those journals are the ground truth and the summaries are not.

---

## 3. Program-by-program defensibility

For each: what the number means, evidence tier, third-party verifiability, whether the "AI agents did it" distinction matters for phrasing, and a recommended/forbidden phrasing.

### 3.A — Program R: 500-unit Codex fan-out (2026-07-26) — VERIFIED-VAULT; provenance-flagged

- **What it was:** a read-only research lane, `(target × lens)` units with 8 lenses, tiered budget (harness 12×8 + hooks 38×6 = 65% of 500), run as 11 shards of 48 on Databricks job clusters with `gpt-5.6-sol`. Artifacts: `harness/lanes/research.py`, `e2e/build_research_targets.py`, `e2e/run_research.py`, `e2e/watch_research.sh` in `~/source/csie-foundation-wt` @ `22ee2a5`.
- **Outcome that matters:** three defects **independently reproduced before fixing**, each with a PR: camelCase payload bypassing a destructive-command guard (#221), JSON-quoted credentials bypassing redaction (#222), cross-session compaction-context injection (#220); plus a refuted-then-corrected finding (#223). The note also records "~84% of units returned HIGH" (severity inflation) and a refuted premise ("goal-bleed … REFUTED").
- **Companion numbers:** the `codex-databricks-fanout` skill (`~/.agents/skills/…/SKILL.md`, 2026-08-09) states "**608 units** (mega-audit) and a **48-unit auth-research re-prove** completed this way" and that "of 180, exactly 120 failed" in one batch due to a measured corruption class. The vault's 2026-07-30 settlement note records **167 findings adjudicated 167/167, 117 patches landed, 40 FIXED-verdict findings not on the branch** — i.e. the owner counted what actually landed, not what was labelled fixed.
- **Verifiability:** no-private. The toolchain repo is public per the GitHub API today (`agent-skills-toolchain`, private=false) but the fan-out ran against harness internals and a Databricks workspace.
- **PROVENANCE FLAG (VERIFIED-VAULT, must shape phrasing):** the compute was the "Bolt Databricks" workspaces. The vault's authorization note (`decisions/Databricks account usage - OWNER AUTHORIZED no restrictions.md`, 2026-07-12) names "the owner (costin.ionescu)" — not Andrei Visalon — and the skill file itself says everything was "measured on workspace `bolt-datascience` (costin.ionescu@bolt.eu)". Two later vault notes (`decisions/bolt-cred-audit verdict 2026-09-04.md`, `decisions/incident agents-md policy inversion… 2026-09-03.md`) describe the Bolt tokens as credentials of named third-party employees "not the operator identity on record". I did not read further into those notes (user instruction: do not pull security writeups into the session). **Resume consequence:** the workspace, the company name, and "Databricks-scale" compute must not appear on a resume; the fan-out design (tiered plan, shard caps, monotonic-count trap, independent reproduction before fixing) can be described generically, and the Modal runs (RVC training on H100, phenibut ATM on Modal) are the clean compute claims.
- **Orchestration distinction:** the 500 units were Codex agents; the owner designed the lane, the tiering, the shard cap, the watch script, and the reproduction discipline. Phrase as "designed and ran a 500-unit parallel LLM research fan-out … three confirmed defects, each reproduced before the fix", never "found 500 issues".

### 3.B — "1000-agent / 12.1 h audit; 42% of 225 findings refuted" (2026-07-30) — INDEX-ONLY

- Nothing beyond the one-liner exists on this machine or in the vault. The line itself is a *negative* lesson ("volume ≠ evidence"): the audit "died pre-synthesis" and 42% of findings were refuted despite 89% self-rated confidence.
- The vault does hold two **smaller, fully documented** samples of the same phenomenon (see §4): Reframe v1.5 wave 1 — 6/6 lanes self-reported SUCCESS, **15/18 adversarial verdicts refuted** (83%); wave 2 — 8/8 SUCCESS, **18/24 refuted** (75%), all eight PRs green on 100% coverage at the moment the defects were found. These are the defensible versions of the "42%" story.
- **Phrasing:** do not use "1000-agent" or "225 findings". Use the measured 83%/75% base rates with their source if a number is wanted at all.

### 3.C — "97-slice pure-Codex audit → 1582 findings, 3 critical RCE" (2026-07-13) — INDEX-ONLY

- Same status. What the vault *does* corroborate for the same fortnight: a Reframe ultracode sweep on 2026-07-11 that "discovered + verified **89 real findings** (82 discovered, 24 false-positives dropped)", 74 fixed in-tree, then reconciled to "sidecar **5733 passed, 100% branch coverage**" (`projects/Reframe ultracode reconcile state 2026-07-11.md`); a 15-agent v1.5 audit (`reframe/Reframe v1.5 program…`); and PR #272 (ultracode sweep) + #273 (CodeQL sanitizer fixes) merged with "0 open CodeQL alerts (6 fixed + 16 FP dismissed)".
- **Phrasing:** "1582 findings" is unusable. "Ran multi-agent security/quality audits of a 5,700-test codebase and reconciled 74 verified fixes to a 100%-branch-coverage gate" is supportable from the vault.

### 3.D — "12,272-record corpus" (2026-07-19) — INDEX-ONLY

- The number is absent from the vault. INFERRED context only: the `ai-sessions-render` repo was created 2026-07-19 (GitHub API) and its vault note measures the Codex store alone at 2,024 rollout files / 1,069 session ids, so "12,272 rec" is most plausibly the conversation-export corpus ingested that day. Unverifiable as stated.
- What *is* verifiable for that project (VERIFIED-VAULT + PUBLIC): a confirmed data-loss defect where resumed Codex sessions silently overwrote earlier legs — **953 of 2,024 files (47.1%) dropped, 204,987 response items lost, 0 ingest errors reported** — measured on the live store with a passing control, fixed in three commits, and closed with all four stacks green (Python 1,342 tests @ 100% cov, TS 958, JS 418, Rust 27). Public repo: `Prekzursil/ai-sessions-render` ("Turn ChatGPT / Claude / Gemini data exports into browser-faithful HTML and clean portable Markdown. Fully offline").

### 3.E — FAERS pharmacovigilance at "20-million-record scale" (2026-09-15) — VERIFIED-LOCAL + VERIFIED-PUBLIC

- **What the numbers mean:** N = 20,692,690 is the openFDA FAERS **denominator** (total reports in the endpoint at lock time, 2026-09-14), not records the owner stored or processed. The actual work: 48 keyless openFDA calls; a **per-record census of 78,592 of 90,232 baclofen reports (87.1%)**, partitioned by `receivedate` to beat the 25,000 skip cap (bucket totals proven to sum exactly to 90,232), ~6 GB paged; disproportionality (PRR/ROR) with continuity correction only where appropriate; two independent runs reconciled (LOC ROR 27.09 vs prior 27.0).
- **Findings with method value:** drug-role restriction collapsed a confounded baclofen–depression signal (ROR 2.64 → 1.31, bracket [0.96, 1.50]) while the withdrawal axis strengthened (DWS 6.19 → 20.70); a **monotonicity bound** turned a partial census into a rigorous upper bound on ROR ("you rarely need 100%"); the nested-element overcount trap in openFDA (1.8×) was checked per record; duplicate inflation ruled out (distinct-case == raw for every phenibut cell); a MedDRA-version statement in the SI was corrected.
- **Public corroboration:** the Zenodo record description (v3, 2026-09-18) names "a FAERS disproportionality" analysis as part of Paper B (see 3.I).
- **Verifiability:** yes-on-request (script `faers_disproportionality.py`, `RESULT.md` + JSON under `D:\Research\projects\phenibut\compute\faers_v2_2026-09-15\`) and partly yes-public via the Zenodo zip (35.5 MB) — I did not open the zip to confirm the FAERS receipts are inside.
- **Orchestration distinction:** this is analysis the owner directed and re-checked arithmetically (the Paper B note records the owner "re-checked the Wald arithmetic" himself); phrase as first-person analysis. Do **not** say "analysed 20 million adverse-event reports"; say "disproportionality analysis against the full openFDA FAERS database (≈20.7 M reports) with a per-record drug-role census of 78,592 reports".

### 3.F — The 26-repo fleet, fleet governance and the 2026-07-25 dependency campaign — VERIFIED-VAULT + partly PUBLIC

- **26 = 18 public + 8 private** GitHub repos as of 2026-07-11 (decision brief). GitHub today shows 68 public repos, so "26" is a stale, campaign-scoped figure; use "a fleet of ~26 personal repos (2026-07)" or re-count.
- **Governance built (VERIFIED-VAULT, repo public):** `quality-zero-platform` — "strict-zero control plane for personal-account GitHub governance" (19 required gates per repo, rulesets, a truthful-gate subsystem; 15 governed repos in the 2026-06-01 worklist); fleet driven to 0-green with a 3-tier auto-green automation (Dependabot auto-merge, GitHub-Models autofix PRs, Copilot escalation) on 2026-06-30; **CodeQL default-setup enabled on 10 repos** on 2026-07-11; a private-host **Codex runner** (toolchain PRs #66/#67) that opens propose-only PRs across the fleet, with the public/private secret-exposure analysis that chose it.
- **Dependency-security campaign 2026-07-25 (READ-ONLY 10-agent triage, then fixes; every claim cites CI job IDs in the note):** ToolUniverse fork **276 → 3 open alerts** (267 closed, 96.7%, incl. a CVSS 10.0 RCE first mis-called "unfixable" from `first_patched_version: null` and then fixed); momentstudio 22 → 0; TanksFlashMobile 33 → 5 with main all-green and 18 → 1 open PRs; pbinfo-scrape 13 → 0; small-repo sweep 15 → 8 PRs, 10 → 3 alerts. Durable rules produced: bounded floors `>=patched <next-major` (a bare `>=` silently crossed two majors; an `=` pin blinded Dependabot), "a conflicted grouped Dependabot PR freezes its stream", "`.github/workflows/*` existing ≠ CI running on a fork", "check both `/branches/<b>/protection` and `/rulesets`".
- **Verifiability:** yes-public for QZP, ToolUniverse (fork), Reframe, ai-sessions-render; the private repos and the Codex runner host are yes-on-request.
- **Orchestration distinction:** agents did the per-repo work; the owner set the rails ("REAL fixes only, no thresholds lowered, no force-merge-red, no --no-verify"), adjudicated the one deliberate ignore (single GHSA, dated, justified, independently corroborated by Dependabot's own dev-scope dismissal), and verified the merged lockfiles himself. Phrase as "ran and verified", not "fixed 267 vulnerabilities by hand".

### 3.G — Reframe: shipped releases — VERIFIED-PUBLIC

- Public repo `Prekzursil/Reframe` (created 2025-12-06, Python, 4 stars, 1 fork): "Local-first AI media toolkit … 100% offline & open source."
- **Release tags that exist publicly:** `v0.1.0` (2026-06-25, NSIS installer 196 MB + portable zip 262 MB per the vault note), `v1.0.0`, `v1.1.0`, `v1.2.0`, `v1.3.0`, `v1.4.0` (releases page; dates on that page run 2026-06-25 → 2026-07-07), tag `v1.4.1` (2026-07-09 per the index), plus `desktop-v0.1.5…0.1.8` and a `snapshot-saas-2026-06-16` tag (the abandoned SaaS lineage). **There is no public `v1.4.2` tag** (checked tags pages 1–2 and releases pages 1–2). "1.4.2" is the app version string of local builds installed/produced on 2026-07-30 and 2026-08-08; the 2026-08-08 note explicitly says the newest build was "NOT installed" and "a video going end-to-end through the INSTALLED app … is not proven". So the index's "1.4.2 SHIPPED" means built, not released.
- **Quality numbers with vault receipts:** renderer "203 files / 3,448 tests all pass, coverage 100% lines/branches/functions/statements" (2026-07-12); sidecar "5,733 passed, 100% branch coverage" (2026-07-11); a v1.5 lane at "3,854 tests / 215 files, 100% on all four, SAST 0, osv 0" (2026-08-09); 16 PRs (#334–#349) merged in two days in August; remote branch backlog cleaned **121 → 3** with a reconcile-don't-drop audit (6 read-only forensic agents, one salvage cherry-pick).
- **Verifiability:** yes-public (releases, tags, CI history, coverage config in `app/vitest.config.ts`).
- **Orchestration distinction:** heavily agent-built (ultracode sweeps, 18 fixer agents, lane branches). The owner is the sole author of record and the release engineer. Phrase as "author and maintainer of Reframe (open source, 7 tagged releases 2026-06→07, 100%-coverage gates on a ~9,000-test Electron + Python codebase)". Avoid "1.4.2 shipped".

### 3.H — WebCoder draft PR #152 "295 tests" (2026-09-22) — VERIFIED-PUBLIC (draft)

- Public repo `Prekzursil/WebCoder` (created 2023-11-29, TypeScript). PR #152 title on GitHub: **"WebCoder modernization: CRA->Next 15 port, judge containerization, 295-test suite, CI gates, security hardening"** — draft, 11 commits, unmerged.
- **What "295" is:** the PR's own headline. The local memory's receipts do not reconcile to it: "backend 301 passed / 5 failed (pre-existing: 4× nullable-FK contract mismatch + 1 live-docker test) / 99% cov; frontend 229/229 vitest, ~91% cov; e2e 8/8 (bootstrapped this wave)". 301 + 229 + 8 ≠ 295. INFERRED: 295 may be a subset (e.g. tests added by the wave) or a stale count; it must be re-derived from the PR's CI before use. Also VERIFIED-LOCAL: a real defect fixed in the wave (`users/permissions.py obj.author → obj.user`), the untracked `backend/venv` (8,724 paths) purged, and "pending owner: PR merge, nullable-FK decision".
- **Verifiability:** yes-public (draft PR, CI checks).
- **Orchestration distinction:** delivered "across three workflows (25 / 8 / 11 agents, 0 errors)". Phrase as "led an AI-agent-driven CRA→Next 15 migration of my 2023 WebCoder project (draft PR, 538 passing backend+frontend+e2e tests per the wave receipts, one latent permissions bug found and fixed)"; keep "295" out until reconciled.

### 3.I — Items the index under-sells but which are the most third-party-verifiable

1. **Zenodo dataset deposit (VERIFIED-PUBLIC):** *"Data and code for two studies of the phenibut GABA-B axis: alchemical transfer free energies, and KCTD-subunit genetics with FAERS pharmacovigilance"*, DOI 10.5281/zenodo.22836832 (v3, published 2026-09-18), concept DOI 10.5281/zenodo.22819600, CC-BY-4.0, resource type Dataset, creator "Visalon, Andrei Mihai" with the ORCID, affiliation string "University of Bucharest, Faculty of Mathematics and Informatics" (note: the local identity file says the official English name is "…Computer Science"), one file `phenibut_deposit_2026-09-18_v3.zip` (35.5 MB), 11 views / 2 downloads. This is a sole-author, citable research artifact — the cleanest item on the whole list. Caveat: the `reference_partial_remediation…` note records that the archive's README carried a false "all gates fail-closed" sentence at one version; v3 may or may not have corrected it (not checked).
2. **Two manuscripts drafted (VERIFIED-VAULT, unpublished):** Paper 1/A — "Computational evidence that R-phenibut is the GABA-B eutomer: alchemical transfer free-energy validation and an honest failure report at α2δ-1" (ATM RBFE, seeds reported co-equally, non-convergence stated); Paper B — GABA-B auxiliary-subunit axis: KCTD16 coloc firmed by a MetaBrain cortex cis-eQTL Mendelian-randomization instrument (OR 1.197, p = 4.5e-6), plus the FAERS analysis; both with figures and self-contained HTML. Adversarially audited by 3-lens agent review; a CRITICAL "fabricated citation" verdict was itself refuted by grep. ORCID lists zero works and no preprint/submission evidence exists in the vault (Python scan: 0 hits for chemrxiv/medrxiv/preprint/submitted).
3. **Upstream open-source PRs (VERIFIED-PUBLIC via GitHub search, 18 total by the account):** `dsifry/metaswarm#51` "perf(hooks): skip BEADS dedup scan outside metaswarm projects" (open; the 140.5 s→0.3 s SessionStart fix); `OrfeasZ/ZHMModSDK` #239–#241 "Add TitaniumBullets mod (shoot through walls)" (HITMAN mod SDK; closed — merge state not determined); `victormura/event-link` #1–#12 incl. "Static Code Polishing + 100% Line + Branch Coverage" (a collaborator's repo); `ezluci/pbinfo-get-unsolved` #11–#14 incl. "release: userscript-first v2.0.0 major rewrite"; `jhj0517/Whisper-WebUI#633` (title "."). Merge states were not confirmed (rate limit); check before listing.
4. **PrimariRo (VERIFIED-VAULT + site live):** a Romanian localities/mayors atlas, live at https://prekzursil.github.io/PrimariRo/ (HTTP 200 today), v0.1.0-alpha, SIRUTA 3,187 UATs, official BEC/AEP provenance, SvelteKit static; the note also records a legal red-team finding the owner acted on ("publish the gap, not the guess"). Repo private (404).
5. **Estate MCP/TUI audit (VERIFIED-LOCAL):** 81 servers / 14 surfaces; 96 adversarial verifications; dead-port-band root cause for 11/19 startup failures; a proven config-injection path closed (`~/.mcp.json` 34 → 0 at HOME); the hermes surface revived 17/17; distillery gateway stall root-caused. No-private, but the methodology (deterministic resume from on-disk verdicts, rolling 10-slot pool, output-size discipline) is describable.

### 3.J — Other tooling with receipts (all no-private unless noted)

- **scholarly-access MCP** (older index snapshot, VERIFIED-VAULT): lawful OA-only FastMCP replacing a Sci-Hub MCP; 8 tools, 22 offline + 10 live tests; in `agent-skills-toolchain/tools/` (repo public today). A regression ("unrestricted mode") was caught and reverted.
- **Biomni**: local E1 install + FastMCP server + Claude Science sandbox wiring (3.above). **Claude Science GLM router** (two-plane). **RVC voice changer** app with measured latency, Modal H100 training (~7 min ≈ $0.5), a NaN-training root cause, a timbre-similarity acceptance gate, and an honest "local path CLOSED" verdict.
- **Harness efficiency (self-measured, older snapshot):** per-turn context load cut 64% (15.6k → 5.6k tokens); always-on plugin tokens cut 74% (102.6k → 26.2k); "45% Claude connections, 87% Codex servers reduced".
- **Reverse-engineering toolkit** (older snapshot; Battle Cats on rooted BlueStacks): Frida/LSPosed/IDA stack; `event_0.dat` AES-128-ECB scheme solved; a companion launcher (125 tests / 99% cov) and a PySide6 trainer GUI (253 tests / 100%), both two-stage reviewed. Plus the public HITMAN ZHMModSDK mod PRs above.

---

## 4. Professional character: the recurring verification lessons

### 4.1 Catalog (source → lesson, one line each)

| # | Lesson (paraphrased) | Source | Tier |
|---|---|---|---|
| 1 | Partial remediation, global claim: fixed 4 gates, README said all fail-closed, 2 were not; fix = a harness that proves the property on both good and injected-defect input, and names what it does not cover. | `reference_partial_remediation_global_claim_2026-09-18.md` | LOCAL |
| 2 | A reporting counter needs its own arithmetic cross-check: "0 excluded" while 13 files were excluded (`os.walk` never enters pruned dirs); caught only because 489 → 476 contradicted the message. | same file | LOCAL |
| 3 | Self-reported SUCCESS is worth almost nothing: 6/6 SUCCESS → 15/18 refuted; replicated 8/8 → 18/24; all PRs green on 100% coverage at the time. Refuters must *execute* (mutations, scratch tests); most findings were false *sentences* on top of working code. | `main/techniques/Measured- 6-6 agents…` | VAULT |
| 4 | Working-tree-green ≠ clone-green: 3,910 passed locally, a clone of the same commit had 31 collection errors; four rounds against real clones → 3,915. A `/_` scratch filter had deleted nine deliverables. | `main/projects/Prompt Two waves 4-5…` | VAULT |
| 5 | Validate the detector in both states: a dead-button crawler classified every control alive on a page with a 100 ms ticker (0/2 planted defects found); fixed with an ambient-noise control window; the note then says the fix did not change the real app's result ("do not claim it saved the run"). | `projects/reframe/Reframe functional-sweep… 2026-07-30` | VAULT |
| 6 | A rule can be the faulty instrument: `git archive` returns CRLF, not the blob; three agents hit it in one wave; worktree isolation landed agents in another project's checkout; the isolated suite passed either way and only the full-scope CI command caught the regression. | `techniques/Three verification traps…` | VAULT |
| 7 | Never state a count from recall: "8 PRs merged" was 15; "18 branches" was 20 — three miscounts in one session, all from re-quoting an earlier listing. Rule: re-run the enumeration in the same turn you report it. | `projects/reframe/Reframe v1.5 open-work register 2026-08-08` | VAULT |
| 8 | A fan-out reporting `agents_done: 28` beside `agents_error: 3` is not success — the three dropped lanes were the two CRITICAL user-facing ones; diff dispatched-lane names against branches that exist. | same | VAULT |
| 9 | Verify the shipped artifact, not the report about it: corrections were confirmed present "in the implementer's report" while the false claims lived in shipped docstrings. | `reference/Session learnings 2026-07-25` | VAULT |
| 10 | The C2 overclaim pattern (six times in one session): code correct, sentence wider than the evidence. Fix the sentence, quote the refuted wording, label it REFUTED, never silently delete. | same | VAULT |
| 11 | Report the net: "PR introduced a HIGH" was narrowly true and materially misleading (it closed 11); the proposed remedy would have been the worst version of the line. | same, §21 | VAULT |
| 12 | `first_patched_version: null` ≠ unfixable — reported as fact, refuted by resolving ranges against the registry; a CVSS 10 RCE had sat open because of it. | same, §18 | VAULT |
| 13 | "Not wired" must be checked in the REPO, not just the live config — drift disarmed a defect locally and hid it; the next deploy would re-arm it. | `projects/Program R…` | VAULT |
| 14 | In-memory assertions are not disk assertions: three ingest defects in a row were green under 100% coverage because tests asserted on the returned object, never on the SQLite index. | `projects/ai-sessions-render/… 47%…` | VAULT |
| 15 | Green gates cannot catch a broken build (mcp-funnel: CLEAN with 0 check-runs; all four Dependabot PRs broke `tsc`; zero merges was correct). | `projects/Fleet triage plan 2026-07-25` | VAULT |
| 16 | A format-mismatched grep produces a false ABSENCE — the most dangerous detector failure because it looks like evidence (uv.lock is TOML). | same | VAULT |
| 17 | Serial `bash -e` steps hide one layer per push (five pushes for five layers); run the battery locally in CI order. | `reference_layered_gate_unmasking.md` | LOCAL |
| 18 | `git commit -- paths` silently restored 12 staged deletions; the commit stat was the tell. | `reference_git_pathspec_commit_trap.md` | LOCAL |
| 19 | Failed calls ≠ missing tools: an agent claimed "no native tools" while its transcript showed them working; ToolSearch-prove absence before claiming it. | `reference_tool_absence_misattribution_2026-09-22.md` | LOCAL |
| 20 | Count DONE lines is not completion: log said 338 DONE while 12 headline packages were missing; run the `require()` battery. | `project_biomni_local_install…` | LOCAL |
| 21 | Validate with the metric the goal actually names (timbre similarity), not a proxy (f0 correlation) — proxy-green shipped a harmful model once; check training logs for NaN before shipping any checkpoint; a capped deque is not a throughput counter. | `project_rvc_voice_changer…` | LOCAL |
| 22 | Brief the obligation, name the source, let the lane verify: an OpenRAIL licence clause was asserted from memory, did not exist, and was caught by the agent told to check. | `Reframe v1.5 open-work register` | VAULT |
| 23 | Design agents to escalate, not adapt: one lane refusing to write into a wrong-repo worktree exposed an orchestrator bug that five silent lanes concealed. | `techniques/Three verification traps…` | VAULT |
| 24 | A never-gating suite rots silently; drift reads as flake (index line, 2026-08-14). | `MEMORY.md` | INDEX-ONLY |
| 25 | "Green gates found zero of eleven defects" — cited by the WHERE-map as a technique note; no such note exists in the vault (0 hits); treat as INDEX/MAP-ONLY. | `memory-map.md` | INDEX-ONLY |

### 4.2 What the pattern actually is

Almost every lesson has the same shape: an instrument (a test suite, a CI gate, a counter, an agent's SUCCESS line, a grep, a summary sentence, a rule) reported green, and the owner's process found the defect anyway by demanding a second, mechanically independent signal — a control in the known-bad state, a clone instead of the working tree, the lockfile instead of the PR title, the SQLite row instead of the returned object, the enumeration instead of the recollection. The failures were mostly produced by AI agents (and by the assistant writing these notes); the **countermeasures are the owner's design**: adversarial refuters that must execute, `verify_gate_controls.py`, `_prepush_gate.py` over `git cat-file` blobs, receipt schemas that forbid SUCCESS without an independent reviewer and a negative control, `RailHealthGuard`, `MCPOrphanReaper`, the "never self-certify" and "REFUTED with evidence is a success" briefing rules (`feedback_peer_review.md`, `feedback_full_rigor.md`, both VERIFIED-VAULT and dated 2026-05-28 — i.e. these were his standing instructions before the measured base rates confirmed them).

Two things distinguish this from ordinary "I value testing":
- It is **quantified**: 83% / 75% refutation base rates; 47.1% of a store silently dropped under 0 errors; 3,910 vs 31 collection errors; 0/2 planted defects found by a "working" detector; 4-of-6 gates fail-open while "10 of 10 green".
- It is **self-directed**: the notes catch the author's own miscounts, own false sentences, own wrong briefs, and record them under REFUTED rather than deleting them; the owner also rejects refusal-by-rotation and secret-wiping (§9 rules) while still insisting that exposures be reported with a blast radius.

### 4.3 Is it resume-expressible, and how

Yes — but as *practices and measured outcomes*, not as confessions, and in at most two or three lines. Candidate phrasings (all supported above):

- "Built independent-verification tooling around AI-agent-generated changes: adversarial refuters that must execute a mutation or probe before a merge; measured that 75–83% of agent 'SUCCESS' claims failed review even with green 100%-coverage CI, and gated merges on the independent verdict instead."
- "Verification-first engineering: every gate is tested in both states (clean input must pass, injected defect must fail) via a harness that also states what it does not cover; replaced 'all gates are fail-closed' prose with a runnable check after catching my own partial-fix/global-claim error."
- "Habit of validating instruments before trusting their silence — e.g. found and fixed a 47% silent data loss in an ingest pipeline that reported zero errors under 100% coverage."
- Cover-letter / interview material rather than resume: the count-from-recall rule, the C2 overclaim pattern, "report the net", "match the probe to the file format".

Do not put: "my agents lied to me", "42% of findings refuted" (index-only), the 1000-agent audit, or any number that has not been re-enumerated from its source in the same session the resume is written (the owner's own rule #7).

---

## 5. Does the "AI agents did it" distinction matter? Verdict per item

- **Author-of-record items where the distinction is irrelevant on paper:** Zenodo dataset (sole creator), public repos (sole owner), upstream PRs (his account). These stand on their own.
- **Items that are honest only with an orchestration verb:** the 500-unit fan-out, the 89/74-finding sweeps, the 267-alert campaign, the 96-verification estate audit, the WebCoder migration, most Reframe lanes. Use "designed and ran", "orchestrated", "independently verified", "adjudicated". The memory itself supplies the evidence that the owner's contribution is the *verification layer*, which is the part a reader should value.
- **Items where the distinction cuts the other way (his own hands):** the FAERS method (bucketed census + monotonic bound), the Wald arithmetic re-check, the release engineering, the reconcile decisions (121 → 3 branches), the legal/licensing calls (OpenRAIL, PrimariRo), the refusal to enable Actions on forks. These are judgment calls he made.
- **Disclosure:** the owner forbids AI disclosure in manuscripts (VERIFIED-LOCAL). A resume is not a manuscript; a short "AI-agent-orchestrated" qualifier on the fan-out items is the honest choice and also the more impressive one. Whether to say it is his call.

---

## 6. Red flags and do-not-claim list

1. **Compute provenance (VERIFIED-VAULT):** the Databricks workspace behind Program R / the 608-unit run / FEP+ runs is recorded in the vault as a Bolt corporate workspace under another named person, with later audit notes describing third-party employee credentials. Do not name the workspace, the company, or "Databricks-scale" on a resume; keep the fan-out description infrastructure-neutral; prefer the Modal runs.
2. **Index-only numbers:** 1582 findings / 97 slices / 1000 agents / 12.1 h / 225 findings / 42% / 12,272 records. Unusable until re-derived.
3. **"1.4.2 shipped"**: no public tag; last public tag is v1.4.1.
4. **"295 tests"**: PR-title claim; local receipts say 301 + 229 + 8; reconcile first.
5. **ORCID has zero works; both papers are drafts; Zenodo is a dataset deposit** — describe as "data & code deposit (Zenodo, CC-BY)" and "two manuscripts in preparation", not as publications.
6. **Affiliation string:** Zenodo says "Faculty of Mathematics and Informatics"; the owner's identity note says the official English is "Faculty of Mathematics and Computer Science". Pick one and fix the other.
7. **Credential hygiene notes exist** (values not read, not printed): the 2026-08-08 note asks the owner to rotate credentials in the toolchain repo history and says the repo "is now private"; the GitHub API today reports `agent-skills-toolchain` as **public** (its description still says "Private platform repo"). Confirm before linking that repo from a resume.
8. **Count drift is a documented habit of the notes themselves** (three miscounts in one session). Every number carried to the resume needs a same-day re-enumeration.

---

## 7. Gaps — what a resume needs that this source cannot supply

- Any employment history, job titles, dates, or employer names (the only employer-like signal, Bolt, is provenance-flagged and must not be used).
- Dates for the degree and coursework; grades; thesis title (the phenibut program may be thesis-adjacent — INFERRED, unverified).
- Publication or preprint status of Paper A / Paper B; whether the Zenodo v3 README still carries the false fail-closed sentence.
- Merge state of the upstream PRs (ZHMModSDK #241, event-link #12, pbinfo #14) — rate-limited; re-check with `gh` or authenticated API.
- Reconciled test count for WebCoder PR #152; any CI evidence that the PR's 295 figure is current.
- Re-derivation of the three index-only audit numbers from workflow journals (`~/.claude/projects/C--Users-prekzursil/<session>/subagents/workflows/wf_*/journal.jsonl`) if the owner wants them.
- Stars/usage/adoption for the public repos beyond Reframe (4 stars, 1 fork) and Zenodo (11 views, 2 downloads) — modest; the resume should lean on engineering rigor, not adoption.
- Languages/skills inventory as a list (Python, TypeScript/React/Electron, Rust (27 tests in ai-sessions-render), PowerShell, WSL/Linux, Frida/IDA, FastMCP, Modal, Schrödinger/ATM/OpenMM, openFDA/GWAS/MR tooling) is INFERRED from the notes, not stated anywhere as a skills list.

---

## Appendix A — Exact evidence paths

Local auto-memory (all read in full): `C:\Users\prekzursil\.claude\projects\C--Users-prekzursil\memory\{MEMORY.md, feedback_no_ai_disclosure_in_manuscripts.md, project_biomni_local_install_2026-09-20.md, project_biomni_mcp_browser_2026-09-20.md, project_claude_science_glm_bridge_2026-09-20.md, project_estate_mcp_tui_audit_2026-09-19.md, project_faers_v2_dedup_2026-09-15.md, project_rvc_voice_changer_2026-09-20.md, project_webcoder_wave_delivered_2026-09-22.md, reference_cs_local_stdio_connector_2026-09-20.md, reference_git_pathspec_commit_trap.md, reference_layered_gate_unmasking.md, reference_metaswarm_sessionstart_latency_2026-09-19.md, reference_partial_remediation_global_claim_2026-09-18.md, reference_tool_absence_misattribution_2026-09-22.md, reference_workflow_resume_semaphore_gotchas_2026-09-19.md, reference_workflow_tool_available.md, user_author_identity.md}`

Vault notes read (D:\basic-memory, read-only): `projects/Program R autonomous research loop 2026-07-26.md`; `research/Autonomous Codex on GitHub - decision brief 2026-07-11.md`; `projects/Wave2 Codex-Fleet GUI integration facts 2026-07-11.md`; `reframe/Reframe v1.5 program - locked scope + audit 2026-07-11.md`; `projects/reframe/Reframe functional-sweep + PR reconcile 2026-07-30.md`; `projects/reframe/Reframe v1.5 open-work register 2026-08-08.md`; `projects/reframe/Reframe v0.1.0 RELEASED … (2026-06-25).md`; `projects/reframe/Reframe quality-zero program (tracker).md`; `projects/reframe/Fleet 0-green + 3-tier auto-green automation COMPLETE (2026-06-30).md`; `projects/Reframe branch backlog cleanup 121 to 3 2026-07-11.md`; `projects/Reframe ultracode reconcile state 2026-07-11.md`; `reference/Reframe PR #290 merge-conflict reconcile 2026-07-12.md`; `main/techniques/Measured- 6-6 agents self-reported SUCCESS and 15-18 adversarial verdicts refuted them.md`; `techniques/Three verification traps that each defeated a written rule (2026-08-09).md`; `main/projects/Prompt Two waves 4-5 + platform CI lane 2026-08-10.md`; `projects/Both jobs landed- dbx-harness merged … 167 findings settled (117 of 167) 2026-07-30.md`; `reference/Session learnings 2026-07-25 (CSIE build + fleet campaign).md`; `projects/Fleet triage plan 2026-07-25 (wf_081e0b4a-3bc).md`; `projects/Consolidation + fleet + CSIE checkpoint 2026-07-24b.md`; `harness/Codex runner built + verified working 2026-07-11.md`; `harness/Reframe fleet CodeQL default-setup enabled 2026-07-11.md`; `harness/Config-drift audit + auto-compact fix 2026-07-13.md`; `harness/Phase 3- Harness-MCP-Doc SOTA Consolidation program 2026-07-13.md` (head); `phenibut/Phenibut program original aims vs current state 2026-09-14.md`; `phenibut/Paper 1 draft assembled + adversarially audited 2026-09-14.md`; `phenibut/Paper B placed + MetaBrain … 2026-09-15.md`; `phenibut/Phenibut corpus filing 2026-08-25.md`; `projects/phenibut/L05 verify RBFE SOTA 2026-09-20.md` (Zenodo lines); `projects/ai-sessions-render/… (47% of real Codex store was silently dropped).md`; `projects/PrimariRo v0.1.0-alpha live + grill critical findings.md`; `claude-memory/Documents-GitHub-quality-zero-platform/{MEMORY.md, fleet_drive_to_zero_worklist.md}`; `claude-memory/lessons/Durable-incremental beats big fan-out….md`; `claude-memory/root/{MEMORY.md, feedback_full_rigor.md, feedback_peer_review.md, feedback_parallel_agent_worktree.md, feedback_workflow_orchestration.md, reference_agent_skills_toolchain.md}`; `decisions/Databricks account usage - OWNER AUTHORIZED no restrictions.md`; `sessions/{Session capture 2026-09-22 WebCoder.md, sessions-catalog-2026-08-27.md}`.

Other local: `C:\Users\Prekzursil\.agents\memory-map.md`; `C:\Users\Prekzursil\.agents\PROGRAM-REPORT_2026-09-22.md` (head); `C:\Users\Prekzursil\.agents\skills\codex-databricks-fanout\SKILL.md` (grep only).

Public probes (2026-09-23): `https://api.github.com/users/Prekzursil`; `/repos/Prekzursil/{Reframe, WebCoder, agent-skills-toolchain, quality-zero-platform, ToolUniverse, ai-sessions-render}`; `https://github.com/Prekzursil/Reframe/{releases,tags}` (HTML, pages 1–2); `https://github.com/Prekzursil/WebCoder/pull/152` (HTML); `https://github.com/dsifry/metaswarm/pull/51`; `https://api.github.com/search/issues?q=author:Prekzursil+type:pr+-user:Prekzursil`; `https://zenodo.org/api/records/22836832` (via redirect from 22819600); `https://doi.org/10.5281/zenodo.22819600`; `https://prekzursil.github.io/PrimariRo/` (200).

Scan scripts: `scratchpad/vault_scan.py` (713 files scanned; hit table in §2), `scratchpad/gh_probe.py`, `scratchpad/pub_probe2.py`.
