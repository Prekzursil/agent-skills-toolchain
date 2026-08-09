THE CONSISTENCY CONTRACT. This is the single authoritative list of everything NOT done for the
harness / agent-skills-toolchain / workflow_design / monitor programs. Nothing may be dropped
without an explicit recorded owner decision naming it.

---

# REGISTER — lane `reconcile` — built 2026-08-08

**COVERAGE.** All 127 raw items from five readers were mapped; none was discarded silently (the
raw→deduped map is at the end, §7). Twelve DONE/UNKNOWN claims were re-probed independently
today; **four were refuted** (§6). Statuses NOT re-probed today are inherited from the source
reader with its evidence quoted — those are marked `[inherited]` and are, by this lane's own
vocabulary, NOT-CHECKED-by-me even where the source reader verified them.

If it still reads this way, the unit died before measuring anything and no verdict here may be cited.
(This line is retained deliberately: it was true of the skeleton, and is false of this revision —
the sections below carry measured evidence.)

**RAW → DEDUPED: 127 → 103** (24 merged away, 18.9% compression).
OUTSTANDING 69 · DELIBERATELY-SKIPPED 3 · SUPERSEDED 5 · SETTLED 26.

Dedupe was by MEANING. Where two readers named the same work differently (`T0-3`/`X5`,
`B0-SCOPE`/`B0`, `U2`/`MON-WFMON-PREDECESSOR`, `B5-GAMESEC`/`B3`), the merged entry carries **all**
source ids so the original join keys survive.

Status vocabulary: DONE-VERIFIED · DONE-CLAIMED (= NOT-CHECKED, stays in register) · IN-FLIGHT ·
OPEN · SUPERSEDED · DROPPED-BY-OWNER · UNKNOWN. Effort: S/M/L/XL.

---

## 1. OUTSTANDING — real work, nothing has retired it

### 1A. Program A — toolchain / Prompt Two (32)

| id | title | status | eff | evidence | sources |
|---|---|---|---|---|---|
| R-A01 | **Prompt Two (the ≥2,048-unit maximal build) has never been started.** Anchor `_USER-PROMPTS.md:11437` "Begin by reading the prior decision artifacts, verifying the baseline, creating the command-center ledger… Then launch the program." | OPEN | XL | Six independent signals in L13: 0/13 Phase-0 files; a 2026-07-23 CONTROLLED detector recorded `NOT_YET_EXECUTED`; backlog row A8 BLOCKED; the only P2-named doc self-declares "PLAN ONLY"; 0 of 100 remote branches / 20 worktrees name it; basic-memory has no note. `[inherited]` + confirmed by me: `PROMPT-TWO-A8-PLAN.md` (27,107 B, 2026-07-24 14:45) exists with no sibling execution dir | P2-START, A8-PROMPT-TWO |
| R-A02 | Phase 0 — the 13-file command-center ledger AND the freeze/snapshot clean-room baseline. Anchor `:10590-10603` | OPEN | M | `_check_prompt1_exit.py` → "0 ok / 0 trivial / 13 missing of 13" across all three program roots `[inherited]`; my listing of `unified-continuation/20260723T190727Z/` shows no PROGRAM-CHARTER.md, no WORK-UNIT-CATALOG.json, no ARTIFACT-MANIFEST.json | P2-CC-1..13, P2-P0 |
| R-A03 | **The three Prompt-Two entry inputs were never filled** — selected option IDs (`:10514`), owner overrides/priorities (`:10518`), release mode (`:10522`). OWNER-BLOCKING | OPEN | S | Literal `[PASTE …]` placeholders retained; no OWNER-DECISIONS.md exists to substitute. `07-OPTION-UNIVERSE.json` now carries `owner_decisions: 70`, the natural source for input 1 | P2-IN-1, P2-IN-2, P2-IN-3 |
| R-A04 | **An unapproved ~50× de-scope replaced Prompt Two with a 38-item harness tranche**, and every downstream artifact now calls that "Prompt Two" | UNKNOWN | S | `PROMPT-TWO-A8-PLAN.md:30-33` cites "The 38 (verbatim SPEC:212-217)" from `variant4-pre-prompt2/20260721T165847Z/15-PROMPT-TWO-SPEC.md`. No approving owner turn found in the corpus, `17-DECISION-LOG.md` or `32-OWNER-DECISIONS.md`. UNKNOWN, not DROPPED: absence of an approval record is weaker than a recorded refusal | P2-DESCOPE |
| R-A05 | Unresolved owner fork inside the substitute program: treat the SPEC's 38 as canonical (C22/G-05) or accept the 1.9R adjudication (I3/D07)? Surfaced 2026-07-24, never answered | OPEN | S | `PROMPT-TWO-A8-PLAN.md:58-62`, :99-100 (C22→I3 COMPOSE_WITH H-22; G-05→D07 SPLIT_REQUIRED) | P2-A8-FORK |
| R-A06 | **Marketplace — registry, trust/supply-chain, and tooling.** What exists is a single self-listing manifest, not a marketplace: no publisher identity, channels, SBOM, signatures, provenance, vuln status, lockfile, revocation, mirrors, moderation, governance; no linter / publisher CLI / scaffolder / validator / fixture marketplace | OPEN | XL | `json.load(.claude-plugin/marketplace.json)` → keys `[name, owner, description, plugins]`, `plugins: 1`, that entry's `source: "./"`. Only `scripts/plugin_registry_doctor.py`, `osv-scanner.toml`, `SECURITY.md` on main `[inherited]` | P2-M-2, P2-M-10, P2-P6 |
| R-A07 | **Workflow foundry** (discover/import/repair/translate/merge/distill/generate/benchmark/publish) + `workflow-scout`/`workflow-forge` as executable meta-workflows. GRADE-FROM-CODE trap: the NAME is taken by a 22 KB prose fan-out contract | OPEN | XL | Verified by me today: `git ls-tree -r --name-only origin/main` over 7,913 paths → `workflow-foundry` **0**, `workflow-(scout\|forge)` **0**; control `README.md` = 1. The skill dir exists only on branch `chore/harness-reconcile-20260808` @ e33f66c4. `10-WORKFLOW-FORGE-SPEC.md` is 105,067 B of specification | P2-M-3, P2-P7-SCOUT |
| R-A08 | ≥96 materially distinct **EXECUTABLE** blueprints, ≥40 flagship with e2e tests. Anchor `:10898` "no placeholders or renamed copies" | OPEN | XL | `09-WORKFLOW-BLUEPRINT-LIBRARY.json` → 108 blueprints with `"discovery_only": true`. Verified by me: `workflows/` on origin/main = **1 file**; live `~/.claude/workflows/` holds 10 | P2-P2B |
| R-A09 | **Universal council system** — CouncilSpec compiler, ≥48 protocol blueprints, ≥64 editable presets, anti-failure controls. Highest-value grade-from-code catch: `skills/council` looks like the deliverable and is an unrelated inherited 4-voice prompt skill | OPEN | XL | `skills/council/SKILL.md` 6,346 B, frontmatter `origin: ECC`, roles Architect/Skeptic/Pragmatist/Critic, no CouncilSpec, no schema, no runtime. `12-COUNCIL-PROTOCOLS-AND-PRESETS.json` → 58/72 with `"status": "DISCOVERY - no protocol here has been executed"` `[inherited]`; I confirmed `skills/council` = 2 paths on origin/main | P2-M-6, P2-P2C |
| R-A10 | Council schema covers 11 of 12 named axes — `replay` is absent, so no instantiated council can be audited after the fact | OPEN | S | `11-COUNCIL-SPECIFICATION.schema.json`: token `replay` occurs **0** times; `escalat*` 6, `dissent` 7 `[inherited]` | P1-X08 |
| R-A11 | Phase 4 — 20 formal contracts schema-checked + executable conformance tests BEFORE implementation. Skipping this is why two completion reducers now coexist (R-A18) | OPEN | XL | `11-COUNCIL-SPECIFICATION.schema.json` is the only schema located across the program roots; no conformance suite `[inherited]` | P2-P4 |
| R-A12 | Phase 5 — plugin install/update/repair/rollback/uninstall, health check, conformance validator, migration. Manifest ships, lifecycle does not | IN-FLIGHT | L | `install.py` absent at repo root (detector-controlled ls-tree); only `agent-self/harness/install.py`. No repair/uninstall/health entry points `[inherited]` | P2-P5 |
| R-A13 | Mission 4 — deep-research as the **configurable production workflow** of `:11248-11278` (real substrate exists; the specified product does not) | IN-FLIGHT | L | `skills/deep-research/SKILL.md` 14,147 B on main + `references/research_harness/{cache,grading,harness,preflight,report,routing}.py` + 5 test modules `[inherited]` | P2-M-4 |
| R-A14 | Mission 5 — gem-hunt system. A skill file reads as done; there is no runtime behind it | DONE-CLAIMED | M | `skills/gem-hunt/SKILL.md` 6,812 B on main — prose only, no `scripts/`, no `references/` `[inherited]`. **= NOT-CHECKED; stays in the register** | P2-M-5 |
| R-A15 | Mission 9 — cross-workflow benchmark tournament (Phase-2B stopping condition 18). CI gates exist; no tournament harness | IN-FLIGHT | L | `ci/` gate set + `tools/mutation-gate` + `tools/detector-self-test` on main; no tournament found `[inherited]` | P2-M-9 |
| R-A16 | Mission 11 / Phase 16 — **the self-improvement loop that keeps only measured wins and reverts the rest.** This is the mechanism that would have prevented the whole drift pattern | OPEN | L | No keep/revert-on-measurement engine in repo or live trees; Phase-16's 10 steps have no implementation `[inherited]` | P2-M-11 |
| R-A17 | Phase 15 — 21-item release ceremony, canary-first. Double-blocked: on its own content and on R-A03 (release mode never chosen) | OPEN | L | `release/` on main = 14 files, all README/config/platform notes; no signed artifacts, SBOM, attestation, vuln scan, compatibility matrix `[inherited]` | P2-P15 |
| R-A18 | **Two completion predicates coexist** — a live instance of a hazard Prompt Two itself names at `:11314` | IN-FLIGHT | M | `hooks/_shared/completion.py` (canonical E01 reducer) AND `skills/workflow-foundry/scripts/receipt_gate.py` (14,404 B, own `--self-test`). Neither defers to the other `[inherited]` | P2-CP |
| R-A19 | 46 named failure classes: several demonstrably seeded, but with no TEST-REGISTRY.json coverage of the set is unprovable — and R-A18 shows at least one class live and unguarded | IN-FLIGHT | L | Confirmed-seeded: bare `.sh` on Windows, repo-vs-live divergence, detector-silent-in-both-states, mutation-survives, eager per-session MCP multiplication, worktree-points-at-wrong-repo, stale-branch-reverts-newer-work. No registry enumerates all 46 `[inherited]` | P2-FC |
| R-A20 | Phase 9 residual on the (otherwise done) adapter layer: capability negotiation + abstraction-leak documentation | OPEN | M | Named as the residual inside the P2-M-8 DONE finding `[inherited]` | P2-M-8 (residual) |
| R-A21 | `01-BLOCKER-REPRODUCTION.md` + a **reproducible failing fixture**. Prompt One's own first action (`:6744`) required one; the root-cause work rests on a live host that has since changed | OPEN | M | Verified by me: absent from BOTH trees (31,384 files indexed; controls pass — `14-NO-REGRESSION-CONTRACT.md` PRESENT 39,221 B, sentinel ABSENT). `platform-redesign-2026-07-19/fixtures/` and `/evidence/` empty. `02-BLOCKER-ROOT-CAUSE.md` self-declares "NOT FULLY RESOLVED" | P1-A01, P1-X01, P1-EXIT |
| R-A22 | **The fusion decomposition record**: `08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json` + `10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json` + `10-WORKFLOW-FUSION-AND-CERTIFICATION-PLAN.md`. Without the merge maps a fused workflow cannot be decomposed back to its sources, so every fusion claim is unfalsifiable. Two of the three are ALSO Prompt Two final deliverables | OPEN | L | Verified by me: all three ABSENT from both trees, same controlled scan as R-A21. `10-WORKFLOW-FORGE-SPEC.md` IS present (105,067 B) — spec without provenance | P1-A01, P1-X06, P1-EXIT, P2-P2A (provenance half) |
| R-A23 | `15-IMPLEMENTATION-PRECONDITIONS.md` — the gate Program A must clear before any option is applied. Without it "apply-ready" has no written definition | OPEN | M | Verified by me: ABSENT from both trees (same controlled scan). `14-NO-REGRESSION-CONTRACT.md` present, so the pair is half-built | P1-A01, P1-X11, P1-EXIT |
| R-A24 | `05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md` — exact name absent; the CONTENT exists sharded as four `05-ECO-*.md` (72,150 + 92,804 + 53,973 + 36,768 B). A naming reconciliation, not lost research | OPEN | S | Verified by me: exact-name ABSENT both trees; the four shards enumerated in `platform-redesign-2026-07-19` | P1-EXIT, P1-C02 |
| R-A25 | Artifact #29 — the 8 named editable diagrams (current-state architecture, failure-path, plugin lifecycle, marketplace trust flow, workflow execution graph, review pipeline, deployment/rollback, option dependency map). Anchor `:7857` "in an appropriate editable format" | OPEN | M | Verified by me: `platform-redesign-2026-07-19/diagrams/` exists and holds **0 files**; `harness-restore-20260806/diagrams` does not exist; extension scan for `.mmd/.drawio/.svg/.excalidraw/.puml/.dot/.graphml` across 31,384 files → **0** | P1-A29, P1-A01 |
| R-A26 | The two program trees are unreconciled — 9/28 exact names at `platform-redesign-2026-07-19`, 17/28 at `harness-restore-20260806`; grading either alone under-counts | OPEN | S | `10-WORKFLOW-FORGE-SPEC.md` + `12-COUNCIL-TEST-MATRIX.md` exist ONLY in the former; the 07/08/09/12 JSON pairs ONLY in the latter `[inherited]`, corroborated by my two-root scan | P1-C02 |
| R-A27 | Closing instruction `:7919` "End by presenting the first owner decision from the grill" — the queue exists; the conversational act is not disk-observable | DONE-CLAIMED | S | `16-GRILL-QUEUE.md` 35,271 B verified present by me, TIER 0 first, G-01 carries options/recommendation/tradeoff/downstream/blocks per `:7890-7896`. **= NOT-CHECKED; stays in the register** | P1-X13 |
| R-A28 | **A4 — implement C16 = ADOPT_THE_SPLIT.** A binding owner decision the contract forbids re-asking (`_l14_body_A.txt:1389`), never built. **NOW UNBLOCKED** — its gate (A1–A3) is fully verified today | OPEN | L | Backlog state "READY (after A1–A3)"; no `C16-H20-DOSSIERS/` exists `[inherited]`. Gate cleared: see T-15/T-16/T-17 | A4-C16 |
| R-A29 | **A5 — implement H-20 = RETAIN_STANDALONE_ADOPT_SHADOW_FIRST** (human-approved SessionStart crash-orphan requeue, idempotency, audit events, disable switch). Second binding un-reaskable decision, never built. **NOW UNBLOCKED** | OPEN | L | Backlog state "READY (after A1–A3)"; no implementation dossier `[inherited]`. Directly weakens recovery from the very failure this wave investigates | A5-H20 |
| R-A30 | A6 — Increment-1 green claims (557 tests / 100% branch / vendor parity) must be re-measured; the contract downgrades them at `:1395`. The C:-disk owner-gate that blocked them is now satisfied | OPEN | L | Backlog: "CLAIMED_NEEDS_REMEASURE … monitor-live receipt + 3-unit smoke + review + commit never run". No `INCREMENT1-DOSSIER/` `[inherited]` | A6-INC1 |
| R-A31 | A7 — post-Wave-2 current-state reconciliation (the delta, not a rerun): freeze main SHA, compare every selected option against current source, classify DONE / ADOPTION_REMAINING / BUILD_REMAINING. **The single gate between merged work and Prompt Two** | OPEN | XL | Backlog "BLOCKED on A1–A5"; no `POST-WAVE2-GROUNDING/`, none of the five A-* artifacts exist `[inherited]` | A7-POSTW2 |
| R-A32 | A9 — Prompt 2.1 expansion delta, gated on A8. Carries the explicit rule `:1524` "Do not fold Program B's unrelated backlog into Prompt 2.1" | OPEN | XL | Backlog "BLOCKED on A8"; no `PROMPT-2.1/` `[inherited]` | A9-PROMPT-21 |

### 1B. HARNESS — the unified two-program contract's own machinery (10)

| id | title | status | eff | evidence | sources |
|---|---|---|---|---|---|
| R-H01 | **`RESUME.json` went stale while work continued — the direct, measured cause of the drop.** Contract `:1901` "At every wave boundary update RESUME.json atomically"; `:1919` "A future session must be able to resume from RESUME.json without rereading the entire transcript corpus" | OPEN | M | Verified by me: `RESUME.json` mtime **2026-07-23 23:54**, still `"A3_land_m02": "landing"`; `M02-CI-DISPATCH-BLOCKER.json` 07-24 00:41 and `PROMPT-TWO-A8-PLAN.md` 07-24 14:45 written after it with no update. 15 days stale — and A3 has since MERGED (T-17), so the pointer is not merely old, it is **wrong** | RESUME-STALE |
| R-H02 | The machine-readable twins were never written: `09-RECONCILED-BACKLOG.json` (33 mandated per-item fields; the prose table carries 4) and `06-PROGRAM-B-SCOPE-DOSSIER.json` (16 workstreams live only in prose) | OPEN | L | Verified by me: directory listing of the continuation root shows `09-RECONCILED-BACKLOG.md` (5,681 B) and `06-…-DOSSIER.md` (15,815 B) with **no `.json` sibling for either** | ART-09-JSON, ART-06-JSON |
| R-H03 | `10-DEPENDENCY-GRAPH.{json,md}` and `11-CAPABILITY-PRESERVATION-GRAPH.json` never written → §17's "every reconciled backlog item reachable from a final disposition" is **not computable**, which is exactly the check that would have surfaced the never-started items | OPEN | L | Verified by me: all three absent from the continuation root listing | ART-10-11-GRAPHS |
| R-H04 | `12-ORDER-PLAN-A-THEN-B.md` and `13-ORDER-PLAN-B-THEN-A.md` never written. **Reframed:** the owner chose INTERLEAVE (S-01), so the A/B binaries are moot — what is genuinely owed is an INTERLEAVE order plan with collision map, serialization boundaries and rollback boundaries | OPEN | M | Verified by me: both absent. Partially satisfied already — `09-RECONCILED-BACKLOG.md` contains an interleave wave plan and a non-collision proof `[inherited]` | ART-12-PLAN-AB, ART-13-PLAN-BA |
| R-H05 | 3 of 6 mandated ledgers absent: `EVIDENCE.jsonl`, `RUNS.jsonl`, `DEPLOYMENTS.jsonl`. Without EVIDENCE there is no claim/evidence ledger to audit; without RUNS no Databricks run IDs or terminal states — both are §19 inputs | OPEN | M | Verified by me: present = `EVENTS.jsonl` (1,664 B), `PRS.jsonl` (955 B), `RESUME.json`; the other three do not appear in the root listing | LEDGERS-3OF6 |
| R-H06 | **No program has a receipt. 11 of 51 contracted artifacts exist**: top-level 11/21, `program-a/` **0/11**, `program-b/` **1/12**, `shared/` **0/7**. `FINAL-INDEPENDENT-AUDIT.md`, `UNIFIED-PROGRAM-RECEIPT.json`, `UNRESOLVED-OWNER-ACTIONS.md` all absent, so the unified program has **no terminal state at all**. Cheapest first move: an honest PARTIAL `PROGRAM-B-RECEIPT.json` — a partial receipt is a terminal state, no receipt is not | OPEN | L | `_l15_contract_check.py` with a passing detector control (known-present `RESUME.json`=True, sentinel=False) `[inherited]`; my listing confirms `program-a/` and `shared/` do not exist and `program-b/` holds only `B1-PERFORMANCE-DIAGNOSIS.md` | TREE-RECEIPTS, B-CONTRACT, B7 |
| R-H07 | Stage 5 INDEPENDENT AUDIT never ran — no final audit, no receipts, no terminal `UNIFIED-PROGRAM-COMPLETE/BLOCKED` line, and the **17-fixture mutation battery** at `:2007-2027` (the thing that would catch every false-done) was never executed | OPEN | XL | Six named artifacts absent under two independent probes `[inherited]`; corroborated by my root listing | STAGE5-AUDIT |
| R-H08 | X2 — Databricks execution envelope: timeout readback, idempotency, terminal-state polling. The prior `timeout_seconds: None` defect must not recur; 11-step per-run protocol at `:870-887` | OPEN | M | Backlog X2 = READY; no `shared/DATABRICKS-ENVELOPE/` (and `shared/` itself does not exist) | X2-DATABRICKS |
| R-H09 | X3 — canonical `.agents/skills` vs live projection reconciliation, under the binding principles at `:962-970` (union before overwrite; zero implicit removals; one-way projection after cutover; no last-write-wins) | OPEN | L | Backlog X3 = READY; no `shared/SKILL-RECONCILIATION/`. Note the "26 uncommitted skills" is an Increment-1 CLAIM to re-measure, and belongs to X3, **not** Program B | X3-SKILLS |
| R-H10 | **NEW (measured today, in no reader's list): 18 of 20 live `rules/common/*.md` differ from the repo.** The deployed behaviour contract is not the versioned one. 15 repo-ahead, 3 live-ahead, 2 identical, 0 repo-only, 0 live-only. This absorbs both `T0-6` (ci-hygiene squash-merge amendment) and `T0-7` (PowerShell `${n}:` footgun): **both landed in the repo and neither is live** | OPEN | M | SHA-256 compare, repo `rules/common` vs `~/.claude/rules/common`: `TOTAL=20 IDENTICAL=2 DIFF=18`. Worst: `agents.md` repo 2052 / live 314; `hooks.md` 4828/849; `ci-hygiene.md` 8219/4420. LIVE-AHEAD: `owner-ops-authorization.md`, `performance.md`, `security.md`. Content probes: `squash-merge` repo=2 live=**0**; `drive-qualified` repo `windows-shell.md:261` live=**0**. UNVERIFIED inline: direction is inferred from size + one corroborating source (32-OWNER-DECISIONS Q19 independently measured `owner-ops-authorization.md` as live-ahead); settling experiment = search each live variant's hash against every blob of that path in git history, the algorithm L16 already ran for monitorcore | NEW, absorbs T0-6, T0-7 |

### 1C. MONITOR — unified cockpit (19)

| id | title | status | eff | evidence | sources |
|---|---|---|---|---|---|
| R-M01 | **The cockpit is merged, 100%-gated, 39 test modules — and registered in NO launcher.** `python -m monitorcore.unified --help` exits 0 advertising five panes; the registry lists only wfmon/agentmon/codexmon/crcp | OPEN | S | Verified by me in three copies: repo `.agents/skills/monitor-launcher/monitors.toml`, repo `skills/monitor-launcher/monitors.toml`, and live `~/.agents/skills/monitor-launcher/monitors.toml` — all four stanzas `[wfmon][agentmon][codexmon][crcp]`, **no `[cockpit]`/`[unified]`**. `unified.py` present in both repo and live. **One TOML stanza converts the flagship from unreachable to reachable** | MON-CORE-UNWIRED |
| R-M02 | Redeploy the 13 stale monitorcore files **and add a repo→live drift gate**. T0-1 was completed once and silently rotted again | OPEN | S | Re-measured by me today, independent of L16's `_l16_hash.json`: 37 .py files, **24 identical, 13 differ, 0 repo-only, 0 live-only** — including `unified.py`, `pane.py`, `pane_views.py`, `nav.py`, `view.py`. Deploy is SAFE: L16's direction algorithm located all 13 live variants in git history (raw and CRLF-normalised) → `live_drift_NOT_IN_ANY_COMMIT_dangerous: []` | MON-DRIFT-13, MON-DEPLOY-SAFE, T0-1 |
| R-M03 | Collapse **three** autolaunch registrations into exactly one cockpit window (widen the dispatcher matcher, retire the 2 dedicated hooks on disk, behind `MONITOR_AUTOLAUNCH=off`). **Same defect under two ids — join keys preserved deliberately** | OPEN | S | `settings.json` matchers `Workflow` and `mcp__codex__codex`, plus `_dispatch/manifest.json:260` and `:270` `[inherited]`. Double-open not itself observed — UNVERIFIED inline | T0-3, X5 |
| R-M04 | Retire the bespoke Textual `wfmon` app (U2 = HYBRID: salvage the `journal.jsonl` data layer, rebuild presentation on the shared cockpit). Also a live violation of the program's own skip-list (927 ms / 41 MB Textual on a RAM-tight box) | OPEN | M | `wfmon.cmd` → `workflow_monitor.py:66-71` still imports `textual.app.App`. Two signals it is live: the `settings.json` `Workflow` matcher and three dated `%TEMP%/wfmon-autolaunch-<sid>.lock` files `[inherited]`. **Settles supersession: wfmon is the PREDECESSOR, so the monitor program is NOT superseded** | U2, MON-WFMON-PREDECESSOR |
| R-M05 | Lane-1 BLOCKING — the workflows pane must ADAPT `FleetPoller`, not reimplement it. Named damage: "the legacy wfmon board and the new wfmon pane render different numbers for the same run" | OPEN | M | `lane1-wfmon-BLOCKING.md`: measured mentions `parse_manifest` 0, `iter_manifest_paths` 0, `FleetPoller` 0 → "the reuse-vs-rebuild decision was not made, it was skipped", almost-certain 90-99% `[inherited]` | LANE1-BLOCK |
| R-M06 | **The program parked 2026-07-27 immediately after 7 adversarial-gate blocking verdicts, and the unblocking work was never scheduled.** Six remain live (BUILD-2 is now REFUTED — see T-26): lane1-wfmon, lane2-mcp, lane3-ultracode, lane4-adapters, unattributed, BUILD-1-agentspec-FAIL | OPEN | UNKNOWN | `gate-findings/` inventory; newest paths in the tree are all under `parked-backup-20260727-034150/`; sibling `monitorcore.bak-20260727-091532` same day. No owner decision retired the program `[inherited]` | MON-PARK-CAUSE |
| R-M07 | Scope `deny-credential-reads` to write-class tools only (keep the guard — scope it, never remove it, AGENTS.md §9) | OPEN | S | Matcher is now `Read\|Edit\|MultiEdit\|Grep\|Bash\|PowerShell` — no longer unconditional, but still fires on read-class Read/Grep, so the ~275 ms/call tax persists on the most frequent tools `[inherited]` | T0-4 |
| R-M08 | Quarantine (do NOT delete) `~/.local/opt/mingle/monitor/` → `…/mingle/monitor.retired-20260718/` | OPEN | S | `~/.local/opt/mingle/monitor` still present; `monitor.retired-20260718` absent `[inherited]` | T0-9 |
| R-M09 | Delete `monitorcore.bak-20260727-091532` — zero unique bytes, and keeping it invites a future session to treat it as a salvage source and re-walk a dead end | OPEN | S | 31 files, strict name-subset of live, 25 byte-identical, all 6 differing variants located in git history → `bak_UNIQUE_not_in_live_and_not_in_git: []` `[inherited]` | MON-BAK-DEAD |
| R-M10 | WU8 split verdict — the read-only export/`--once` frame shipped; the **in-chat `PushNotification` half did not** | OPEN | M | `export.py`/`timeline.py`/`render_html.py`/`render_md.py`/`pdf.py`/`report_doc.py` present and `--once` executes, but `grep -rl PushNotification` over the package → no hit `[inherited]` | WU8 |
| R-M11 | Phase 2 (WU9 sub-agents v2, WU10 truncation banner, WU11 partial repaint, WU12 ctypes shells, WU13 relay run-id grouping) — genuinely untouched; **3 of 5 are honestly externally blocked**, so the residual is smaller than the headline | OPEN | L | `winproc.py` absent everywhere (WU12); no partial-repaint module (WU11 — only WU7's sync-output primitive); no live-trace artifact for WU9; WU10/WU13 externally blocked per GRILL-DECISIONS:90-92 `[inherited]` | WU9-WU13 |
| R-M12 | U7 stdlib `ThreadingHTTPServer` + SSE web rail and U10 shared SQLite FTS5 tail index. **The "web" half of "web + TUI + control daemon" does not exist at all** — any claim the cockpit is web-capable is false | OPEN | L | `grep -rlE 'ThreadingHTTPServer\|text/event-stream'` and `grep -rli 'fts5\|sqlite3'` over the package → no hit; `server.py`/`hub.py`/`feed.py`/`tui.py` all absent `[inherited]` | U7-U10 |
| R-M13 | U14/U15 — source-declared `control_kind` + **ONE control daemon** (owned-PID firewall, Job-Object tree-kill, honest per-type badges). Absorbs X18's authorised-but-unscheduled BUILD (live MCP restart/reload was PROVEN possible, refuting the "impossible" verdict — research-done was being mistaken for item-done) and X17's residual gaps (live control, user-scope config CRUD, budgeting with impact preview) | OPEN | L | `grep -rl 'control_kind'` → no hit; no `tree_kill`, no JobObject `[inherited]`. X18 research landed: MEMORY.md "live add/remove/disable/reconnect work on 2.1.214 via the stream-json `control_request` stdin channel; 11/11 proven" + `mcp-restart/MCP-RESTART-VERDICT.md` | U14-U15, X18, X17 (residual) |
| R-M14 | U18 — live Gantt + ghost-pending nodes. Owner chose "BUILD NOW, full scope, highest-risk item, eyes open"; never started | OPEN | XL | `grep -rli 'gantt'` over the package → no hit. `timeline.py` (the IR the decision leans on) does exist `[inherited]` | U18 |
| R-M15 | U20 — the alert DELIVERY rail (ntfy / toast / dead-man). Graded from code, and the code says so in its own words | OPEN | M | `contract.py:11` verbatim "the *delivery* rail — ntfy / toast / dead-man — is PR-G, nothing is wired here" (echoed `codex_source.py:308`, `databricks_source.py:718`); `alert()` exists on all 6 sources but returns `Alert \| None` = classification only `[inherited]` | U20 |
| R-M16 | E5 — wire the salvage roster as MonitorSources (taskwatch_monitor, supervision-registry, event-ledger, the bypassed CodexSource adapter, mcp-manager `core/status.py` → McpFleetSource, search-hub quota lane). The inventory was produced and then not consumed — the same drop pattern, one level down | OPEN | M | `tools/taskwatch_monitor` (58 files) and `tools/otel-traces` exist in the repo; only five source classes exist (Agents, Codex, Databricks, SystemHealth, Mcp) `[inherited]` | E5 |
| R-M17 | E7 — `GitHubActionsSource` (workflow runs + self-hosted/cloud runners) with `control_kind="github-actions"` → cancel / rerun / rerun-failed. An explicit new owner ask with a full spec, never started; depends on R-M13 | OPEN | M | `grep -rli 'github'` over the package hits only `redact.py`; no source class, no control_kind `[inherited]` | E7 |
| R-M18 | **Enroll the monitor cockpit program in the unified contract.** It was not dropped BY that program's execution — it was never in scope, so recovery must enroll it explicitly rather than expect to find it in the backlog | OPEN | XL | `grep -ic cockpit` over the full 62,722-char contract body = **0** (control: `grep -ic databricks` = 22); `09-RECONCILED-BACKLOG.md` has exactly one monitor row (X4) and zero cockpit references `[inherited]` | MONITOR-COCKPIT |
| R-M19 | X4 — monitorcore and shared-file collisions: 29 trees inventoried (incl. `D:\inc1-wt\ast-increment1`, 44 py, PRE-EXISTING worktree, read-only), never resolved. "Do not sweep untracked files into another unit's commit" | OPEN | M | Backlog X4 = READY; no `shared/MONITORCORE-COLLISIONS/` `[inherited]`. Corroborated by my probe finding monitorcore/monitors.toml copies across ~15 additional scratch/worktree roots | X4-MONITORCORE |

### 1D. Program B — workflow_design (8)

| id | title | status | eff | evidence | sources |
|---|---|---|---|---|---|
| R-B01 | B1's **M1–M5 reversible prevention proposals reach no config, no hook, and no owner decision queue** — the purest green-not-live instance in the wave. 16 days on the headline metric is WORSE: 1,233 processes today vs 1,070 at diagnosis | OPEN | S | `(Get-MpPreference).ExclusionPath` count = 0 (M1 unapplied); `grok*` processes = 1 (M2 unapplied); grep for a fan-out width cap in `~/.claude/hooks` = 0 (M5) `[inherited]` | B1-FIX |
| R-B02 | Re-verify the **6 CLAIMED_NEEDS_REMEASURE** items — mcp-parity, mcp-gui, api-perm-script, abbyy-ocr-mcp, claude-in-chrome, awesome-game-security-install. RE-VERIFY, not build; and give all 16 workstreams a final disposition (`:21370` "Do not silently drop a workstream because it was absent from the initial seed list") | OPEN | M | Dossier census sums to 16, `CLAIMED_NEEDS_REMEASURE 6`; `:98` "VERIFIED_DONE items lean on MEMORY.md, which is point-in-time"; the dossier bands them 55-80% and warns two are likely genuinely outstanding. No re-measurement artifact exists `[inherited]` | B2-REVERIFY, B6, B2 (re-verify half) |
| R-B03 | Skill authoring and skill lifecycle work (the prompt's B2 — 11 required per-skill fields, 9 mandatory skill properties). Specified in detail, never executed. **Do not cite the "26 uncommitted skills" as progress — it was moved out of B into X3 (R-H09)** | OPEN | M | Backlog READY; zero commits in ast-integrate since 2026-07-23 matching program-b/workflow_design (control: "skills" → 78 commits) `[inherited]` | B2 (authoring half) |
| R-B04 | B4/B5 game-domain skill families — 5 Battle Cats + 3 SWFOC skill dirs exist and are router-reachable, but nothing marks them as Program-B items with outstanding verification, and no receipt binds them | DONE-CLAIMED | M | 5 + 3 skill directories confirmed present under `~/.agents/skills/`; zero validation run — and `validate-all-skills.ps1` is itself unrunnable (32-OWNER-DECISIONS Q22) `[inherited]`. **= NOT-CHECKED; stays in the register** | B4, B5 |
| R-B05 | **Zero consumers reach any Program-B artifact** (diagnosed-not-wired). B0's dossier was read once by the backlog and by nothing since; B1's diagnosis has no reader at all | OPEN | S | Four mechanically independent, detector-controlled probes: `grep -rl 'unified-continuation'` across repo + hooks + skills + workflows + agents = 0 (control `workflow-foundry` = 10); git log since 07-23 = 0 commits (control "skills" = 78); basic-memory = 0 notes (control = 1 exact hit); the one nominal consumer, `RESUME.json next_actions[2]`, names the plan `09-RECONCILED-BACKLOG.md:42` **retracted** `[inherited]` | B-WIRING |
| R-B06 | **basic-memory holds ZERO notes on Program B — the measured cause of the forgetting.** One note, S effort, and it unblocks everything else from being re-dropped. The same gap should be closed for Prompt Two and for the monitor program | OPEN | S | Controlled recall probe: `search_notes 'workflow_design Program B unified two-program continuation'` → 8 results, **all negatively scored** and off-topic (top hit −12.48); control query returns 1 exact highly-relevant hit `[inherited]` | B-RECALL |
| R-B07 | **B3/B4/B5 mean different things in the two authoritative documents** — an ambiguous id is how an item gets closed twice or never. Prompt (higher authority per §0 BINDING AUTHORITY ORDER): B3 awesome-game-security / B4 Battle Cats / B5 SWFOC. Backlog: B3 VERIFIED_DONE confirmations / B4 Reframe / B5 awesome-game-security | OPEN | S | Both numbering schemes read directly from their source files; overlap confirmed on three ids `[inherited]`. Also note the backlog's B4 = "Reframe", which is OUT-OF-SCOPE for this session (concurrent session owns it) — do not action it here | B-IDCLASH |
| R-B08 | 🔴 **Live third-party credentials in `Downloads\workflow_design\Diag 1.txt` — 7 Ed25519 `agent_private_key` + 24 `refresh_token`, tied to a corporate identity — unactioned for 16 days**, sitting in the tree the conversation archive ingests. Rotation is OWNER-ONLY (AGENTS.md §9); what is owed here is a decision + a quarantine, not a rotation | OPEN | S | `UNIFIED-BACKLOG.md:80-83` — CONFIRMED by a controlled scanner on 2026-07-23 with reproduced counts `[inherited]`. I did **not** open or re-scan the file; exposure state unchanged and unquantified since — UNVERIFIED inline, settling experiment = a read-only count-only scan plus a check of what indexes that directory | B-SEC |

---

## 2. DELIBERATELY-SKIPPED — recorded owner decisions. These stay visible forever.

| id | item | the owner decision that skipped it | do-not |
|---|---|---|---|
| D-01 | **T1-1** fold-8-hooks-into-`_dispatch` · **T1-4** skill-vault reconcile / daily-set trim · **T1-9** retire-43-hook-dirs | `GRILL-DECISIONS-2026-07-26.md:22-24` — "ADDITIVE ONLY (G-4). Explicitly NOT authorized, do not touch… The live hooks tree and skill curation stay as they are." | Do not re-propose. Re-surfacing these wastes a gate cycle | 
| D-02 | **awesome-game-security installers** (prompt B3 / backlog B5) | Owner, idx 3684, verbatim: "do only the swfoc thing not the installers". Reaffirmed at corpus `:27059` "awesome-game-security stays deferred"; recorded as `OWNER_DEFERRED` at `09-RECONCILED-BACKLOG.md:51` | Do not re-enrol. Corroborated: zero on-disk footprint across six roots — that absence is EXPECTED, not a gap |
| D-03 | **The 283 options / 108 blueprints / 58 protocols / 72 presets / 11 architectures being unbuilt is CORRECT, not a backlog.** They are DESIGN output under a plan-mode mandate | `:6727` "Do not begin broad implementation yet." · `:7919` "Do not claim implementation success in this phase." · `:9714` "Do not write files unless explicitly told to switch from plan mode to apply mode." | Do not enumerate 500+ phantom items. They are Program A's INPUT QUEUE, gated by R-A03 (selected option IDs). `09-PROMPT-ONE-EXIT-AUDIT.json`: "status: DESIGN (not implemented) is the document being CORRECT, not incomplete" |

---

## 3. SUPERSEDED — replaced, with what replaced it

| id | item | replaced by | note |
|---|---|---|---|
| S-01 | The A-then-B / B-then-A **sequencing** of the unified contract | **INTERLEAVE** — `15-OWNER-DECISION-RECEIPT.json` `"q1_answer": "INTERLEAVE"`, verbatim source "it should be interleave not separate as program a and program b… since sequential is slow" (corpus `:24240`/`:24932`) | **Only the SEQUENCING is superseded — the B-lane ITEMS are not.** Conflating the two is how the whole lane got dropped; this is the third recorded re-litigation |
| S-02 | `14-OWNER-DECISION-PACKET.md` (the consolidated ask) | The owner answered Q1 directly, mid-turn, twice | Legitimate under §0's authority order — but it also short-circuited §5.1, which is why R-H04's order plans were never produced |
| S-03 | The lane-2 **desktop MCP GUI** half of X17 | `D:/tools/mcp-manager` (launched by `/mcp-gui`) — "the program explicitly does NOT rebuild the desktop GUI" | A legitimate saving. Its three genuine residual gaps (live control · user-scope config CRUD · budgeting with impact preview) are NOT superseded — they live in R-M13 |
| S-04 | The 2026-07-20 exit audit's "workflow_candidates **13 SHORT** / blueprints **72 SHORT**" | A record-level recount: 284 candidates, 108 blueprints | Citing the stale numbers would manufacture a large phantom backlog. See T-02 |
| S-05 | Program B's "**fan out per repo**" plan over `Documents\GitHub` | B0's own characterization — `09-RECONCILED-BACKLOG.md:42` "The 'fan out per repo' plan is **RETRACTED.**" | Program B is overwhelmingly local/harness work. A resumption following the contract's literal §3 framing would fan out onto 19 residue repos |

---

## 4. SETTLED (DONE-VERIFIED) — do not re-open, do not re-plan

Kept in the register on purpose: the second failure mode is re-planning work that already landed.

| id | settled fact | evidence |
|---|---|---|
| T-01 | **Prompt One is corpus 6687-7921 (transcript line 11,822)**, not the larger `### line 9,840` message (which is a capability-reconciliation instruction + a ~120 KB pasted OOM transcript) | corpus `:6690` opening role line; `:6788` carries the floors verbatim; `:7919` is the closing line `:28785` attributes to "prompt 1" |
| T-02 | **All six Prompt One quota floors MET**, recounted from JSON records not headings: options **283** (MD↔JSON symmetric difference 0), workflow candidates **284**, blueprints **108**, protocols **58**, presets **72**, architectures **11** | `_l12_content.py`; `08-WORKFLOW-CANDIDATE-REGISTRY.json` classification histogram ADOPT-AS-IS 122 / UNKNOWN-NEEDS-PROBE 44 / DISTILL 43 / RETIRE 24 / … |
| T-03 | The two corpus copies of the UNIFIED TWO-PROGRAM CONTINUATION are **byte-identical** (both sha256 `5bf8aa3c…6394`) — one governing document, no reconciliation owed | `_l14_extract.py`: `BYTE_EQUAL_RAW True`; LF-normalised 62,723 == declared 62,722 + trailing NL |
| T-04 | Stage 1 RECONSTRUCT (§4 Phase 0 read-only state reconstruction) was performed — 12 of 13 mandated files present | Directory listing of `unified-continuation/20260723T190727Z/` (re-confirmed by me) |
| T-05 | **Stage 2 RECONCILE-ONE-BACKLOG DID run — the prime suspect is REFUTED** (almost-certain 90-99%). `09-RECONCILED-BACKLOG.md` enumerates all three namespaces A0-A9, B0-B6, X1-X4 and even corrects Program B's scope | 5,681 B, 2026-07-23 23:21, verified present by me. Neither program was dropped there |
| T-06 | X1 — completion.py deployment/import inversion SETTLED as **NO_INVERSION**; the hard gate on every completion claim cleared | `X1-COMPLETION-INVERSION-SETTLE.json` (2,017 B): AST symbols identical, bodies identical after newline normalisation, divergence is CRLF-only |
| T-07 | B0 — Program B scope characterization DONE and independently corroborated (26-repo classification sums to 26; 16 workstreams by evidence class) | `06-PROGRAM-B-SCOPE-DOSSIER.md` 15,815 B + `06b-…-CORROBORATION.json` 2,721 B, both re-confirmed present by me |
| T-08 | B1 — the machine-performance/freeze diagnosis ARTIFACT is complete (9 sections, per-claim bands, honest UNKNOWNs, read-only) | `program-b/B1-PERFORMANCE-DIAGNOSIS.md` 24,636 B, self-declared "COMPLETE — all sections measured". **The workstream remains PARTIAL/recurring — its residual is R-B01, not this row** |
| T-09 | Mission 1 — the installable plugin manifest is shipped on main | Verified by me: `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` both in `git ls-tree -r origin/main`. Merged as PR #152 `2719d99` (confirmed ancestor of origin/main) |
| T-10 | Mission 7 — multi-agent execution and verification harness is substantially real and on main | `agent-self/harness/{adapters,dispatcher}.py`, `hooks/_shared/completion.py`, `tools/event-ledger`, `tools/monitorcore` all on origin/main |
| T-11 | Mission 8 — cross-vendor adapter layer is real and load-bearing (camelCase alias tolerance is a measured guard-bypass fix; `transport_error` D010) | `agent-self/harness/adapters.py`, `dispatcher.py` on main; 32-OWNER-DECISIONS Q1. Residual → R-A20 |
| T-12 | Phase 2A — workflow archaeology, ≥160 candidates classified with provenance: **284**, pinned to today's main. Do not re-run | `08-WORKFLOW-CANDIDATE-REGISTRY.json` `source_of_truth_ref 07f465f37d49` = current origin/main (I confirmed origin/main = `07f465f3`). Provenance half → R-A22 |
| T-13 | Phase 8 — skill/capability routing WITH the regression suite proving no context flooding. Fully shipped | `hooks/semantic-router/{route,embed,build_index,eval,intents,observe,success}.py` + `index/vecs.f32` + `index/meta.json` on main; gate merged as PR #143 `f71eff7` (confirmed ancestor) |
| T-14 | **main advanced 121 commits since the program pin — real work, from a DIFFERENT authority (the "Prompt 1.9R" 92-ID gate), not Prompt Two.** Do not re-plan it, and do not credit it to Prompt Two | `git rev-list --count d4076fb9c392..origin/main` = 121; `d4076fb9` confirmed ancestor. Commit subjects carry 1.9R option ids (I5, M04, G-04, L13+G-10, G-06, J10, C12, F02, M02), never a Prompt-Two work-unit id |
| T-15 | **A1 — B21 type-gate MERGED** (upgraded from DONE-CLAIMED by me today) | `c3c06378 2026-07-23 feat(harness): B21 — read-only skill-surface reconciler, type-clean (#158)`, `merge-base --is-ancestor origin/main` exit 0. Control: `deadbeef1234` → exit 128 |
| T-16 | **A2 — F02 quality-workflow MERGED** (upgraded from DONE-CLAIMED by me today) | `e07fd6eb 2026-07-23 feat(adoption): F02 … (#157)`, ancestor exit 0 |
| T-17 | **A3 — M02 MERGED as PR #160** (upgraded from UNKNOWN by me today). The CI-dispatch blocker was environmental (Actions allowance exhausted at a $0 cap) and has since cleared. **This unblocks A4 and A5 (R-A28, R-A29)** | `9e4f0e55 2026-07-24 feat(ci): M02 — final-tree strict-parity guard + canonical-to-projection applier (#160)`, ancestor exit 0. `RESUME.json` still says `"A3_land_m02": "landing"` — the pointer is 15 days stale AND wrong (R-H01) |
| T-18 | WU0 — the dual-write invariant holds: repo `tools/monitorcore/monitorcore` ↔ vendored `skills/workflow-monitor/monitorcore` byte-identical, so the `diff -r` gate is green; 39 test modules | 37/37 identical, n_diff 0 |
| T-19 | WU1 — ctx% hardening: `num>denom` surfaces as SUSPECT instead of hiding behind `min(100,…)` | `ctx.py:83` `return f"ctx {gauge.raw_pct}% SUSPECT"` + `test_ctx.py` |
| T-20 | WU2-WU7 — event feed, group tree, responsive width, drill-down nav, two-signal stall, ansi_screen: the comp#1 BLOCKING deliverables are real code | `event_feed.py`, `group_tree.py`, `responsive.py`, `nav.py`+`view.py`+`cockpit.py`, `stall.py`, `ansi_screen.py:56` — each with a matching test module; WU6 hardened post-merge at `146cca9b`/`c4860688` |
| T-21 | T0-2 — codex-monitor-autolaunch repointed off the legacy mingle monitor, closing the 1-orphan-per-session × 27 leak | `~/.claude/hooks/codex-monitor-autolaunch/check.py:39` LAUNCH = `~/.local/bin/codexmon.ps1`; no mingle reference remains |
| T-22 | T0-5 — `rules/common/single-signal-verification.md` shipped and has become the estate's most-cited rule | 12,295 B; reconciled into the repo at `f49f8362`. Second signal: it is one of only **2 of 20** rule files byte-identical between repo and live (my hash run) — i.e. it is genuinely deployed |
| T-23 | T0-10 — the basic-memory checkpoint note exists. **This is the pointer that sat in always-on memory the whole time and was never read** | MEMORY.md index: "Unified cockpit program 2026-07-18 — ⭐ CURRENT: ALL monitors → ONE monitorcore cockpit … Index: `~/.claude/monitor-harness-ultracode-2026-07-18/README-INDEX.md`". The loss was a RECALL failure, not a missing-data failure |
| T-24 | X6 — machine-wide launch lock for the cockpit window, implemented and provably running | `workflow-monitor-autolaunch/check.py:77`; three `%TEMP%/wfmon-autolaunch-<sid>.lock` files dated today |
| T-25 | All six "known related" workflow assets belong to **Program A**, not Program B. "workflow_design" is a SESSION NAME, unrelated to Claude Code Workflows — keyword recall on "workflow" surfaces A and buries B | `31-LANE-foundry.md:1` (Workstream D); `09-WORKFLOW-BLUEPRINT-LIBRARY.json` lane = "Layer B - divergence/option generation"; `STATE-OF-THE-WORLD.md:59-61` pins harness-sota to A9/Prompt-2.1. 281 tracked repo paths match "workflow" |
| T-26 | 🔒 **The BUILD-2 mcpctl secret-leak finding is REMEDIATED on origin/main** (refuted as live by me today). The gate quoted `return strip_controls(redact_text(text))` (redact first = one control byte defeats every pattern) | `tools/mcpctl/mcpctl/safety.py:190` on origin/main now reads `return redact_text(strip_controls(text))`. Two independent signals: the call order itself, and the docstring — "ORDER IS LOAD-BEARING: strip controls FIRST, then match secrets… Measured on the pre-fix ordering: 20/20 shape × separator combinations leaked verbatim through the CLI", naming the regression test and a `safe-order-swapped` mutant. **It no longer outranks the build items** |

---

## 5. THE CRITICAL PATH — ordered, with reasoning

1. **R-B08 — the live credentials in `Downloads\workflow_design\Diag 1.txt`.** (S) Only item with a
   security blast radius, unactioned 16 days, sitting in the tree the conversation archive ingests.
   Owner decision + quarantine; **rotation is the owner's, never yours** (AGENTS.md §9). Everything
   else can wait a day; this cannot.
2. **R-B06 — write the basic-memory notes** (Program B, Prompt Two, monitor cockpit). (S) This is the
   *measured* cause of the forgetting: the durable store the estate relies on to survive compaction
   contains nothing about Program B, so no resuming session could ever recall it. One note each, and
   the re-drop mechanism is closed. Do this before any build work, or the build work gets dropped too.
3. **R-M01 + R-M02 — one TOML stanza and a 13-file redeploy.** (S+S, ~30 min) Highest yield-per-effort
   in the entire register: converts a merged, 100%-gated flagship from unreachable to reachable, and
   the deploy is algorithmically proven to destroy nothing (`dangerous: []`). Ship the drift gate with
   it or it rots a third time.
4. **R-A03 + R-A04 — the owner input packet and the de-scope ruling.** (S) Everything in Program A is
   gated on knowing *which program is being executed*. An executor that picks silently repeats exactly
   the paraphrase-drift this register exists to stop. Batch with §6.
5. **R-H01 + R-H02 + R-H03 — make the resume pointer true and machine-readable.** (M/L/L) `RESUME.json`
   is 15 days stale **and now wrong** (it says A3 is "landing"; A3 merged). Until the backlog has a
   JSON twin and a dependency graph, §17 reachability is not computable and this register is the only
   thing standing between the programs and a fourth drop.
6. **R-H10 — deploy the rule delta.** (M) 18 of 20 live rule files differ from the repo; the deployed
   behaviour contract is not the versioned one, and two individually-tracked items (T0-6, T0-7) turn
   out to be nothing but this one drift. Affects every session on the box.
7. **R-A28 + R-A29 → R-A30 → R-A31 → R-A01.** (L,L,L,XL,XL) **This chain is newly unblocked**: A1/A2/A3
   are all verified merged today, so C16 and H-20 — two *binding, un-reaskable* owner decisions that
   were never built — are READY right now. A7 (R-A31) is the single gate between merged Wave-2 work and
   Prompt Two; A8 (R-A01) is Prompt Two itself.
8. **R-H06 — write honest PARTIAL receipts** (start with `PROGRAM-B-RECEIPT.json`). (L) No program can
   reach a terminal state without one, and a partial receipt with honest UNKNOWNs *is* a terminal state.
9. **R-M18 — enroll the monitor program.** (XL to finish, S to enroll) It was never in the contract, so
   it will keep being invisible until someone writes it in. Enrol first, schedule R-M06's six remaining
   gate verdicts second.

Explicitly NOT on the critical path, and why: R-M14 (U18 Gantt) is owner-flagged highest-risk;
R-M11's Phase 2 is 3/5 externally blocked; R-A06/R-A07/R-A08/R-A09 are all XL and all downstream of the
R-A03 scope ruling — starting any of them before step 4 is how the 50× de-scope happened the first time.

---

## 6. UNANSWERED OWNER QUESTIONS — send as ONE batch, do not ask piecemeal

The owner asked explicitly not to be interrupted piecemeal. **27 open questions.**

**From `32-OWNER-DECISIONS.md` (Q1, Q2, Q4, Q5, Q7, Q8 are reported ANSWERED; 19 remain):**

| # | question (one line) |
|---|---|
| Q3 | `dark-surface/check.py` is now **97% of the Stop battery** (4.29 s of 4.4 s). Who owns converting it — and does the conversion's typed-silence change get its own both-states row? |
| Q6 | RT-01 role-based model floor — adopt the table with T3 (cheap tier) OFF, or run a bounded pilot? Collides with your standing Opus-for-substantive-subagents preference |
| Q9 | B-24 measurement-only ratings (no stars, no download counts) — adopt? |
| Q10 | J-15 dual-use disclosure review before upstreaming security-bearing code — and apply it to `chore/harness-reconcile-20260808` before merge? |
| Q11 | C-32 budget-aware fan-out width profiles — adopt the mechanism; **the numbers are yours** |
| Q12 | B-20 plugin-cache GC (12 GB, 230,181 files, 49/57 entries temp orphans) — approve after a dry-run report? |
| Q13 | B-10 / M-31 quarantine + review the unregistered marketplace clone that ships its own `hooks/` (CVE-2026-47751 shape). *The one item the author would not defer* |
| Q14 | I-02 corpus attrition (364 of 668 executed scripts already deleted by temp sweeps) — adopt copy-on-run now, hold retention? |
| Q15 | M-29 deploy the 11 dark cross-vendor skills — into the LAZY vault, starting with 3? |
| Q16 | B-01 owner marketplace index — public or private? |
| Q17 | `~/CLAUDE.md:31` documents `bd prime --work-type recovery`, which errors *unknown flag* — fix the doc or add the flag? |
| Q18 | `.beads/plans/` (documented) vs `.beads/context/` (the only path a live reader checks) — which is canonical? |
| Q19 | `rules/common/owner-ops-authorization.md` is live-only, on no git ref — reconstruct and commit, or accept? *(independently corroborated today: it is one of only 3 LIVE-AHEAD rule files — see R-H10)* |
| Q20 | The 6 metaswarm guides + `templates/external-tools-setup.md` are dead links from `~`. Where do they live? Pure fact only you hold |
| Q21 | `~/CLAUDE.md` is metaswarm **project** instructions living at `~`, so its mandatory 9-phase gate applies to every session whose cwd is home. Intended? |
| Q22 | `scripts/validate-all-skills.ps1` is unrunnable (resolves a validator under `.agents/skills/.system/` that exists nowhere) — restore or repoint? *(blocks R-B04)* |
| Q23 | `dup-guard` has 68 open fires; closing them needs a generic-name stop-list + target-role filter, which make the guard speak less. Precision-vs-recall on a guard with real true positives |
| Q24 | Promote `workflow-foundry` into the curated 79-skill set, or leave it in the 330-skill lazy vault? (its description is 1,750 chars — rank 1 of 418, 5.9× median, and descriptions are always-loaded context) |
| Q25 | Five hook test files collect **zero** tests under pytest — wire them in, or run them separately and print the count? |

**Program-level questions NOT in that document (8):**

| # | question | register id |
|---|---|---|
| OQ-1 | **Prompt Two — which option IDs are selected?** The `[PASTE SELECTED OPTION IDS HERE]` placeholder is still literal. `07-OPTION-UNIVERSE.json` carries `owner_decisions: 70` and is the natural source | R-A03 |
| OQ-2 | **Prompt Two — owner overrides and priority ordering?** Without it any executor invents one | R-A03 |
| OQ-3 | **Prompt Two — release mode: PR-ONLY / PRIVATE CANARY / PUBLIC MARKETPLACE?** Owner-only gate; Phase 15 branches entirely on it | R-A03, R-A17 |
| OQ-4 | **Was the 38-item harness tranche an APPROVED substitute for the ≥2,048-unit Prompt Two?** No approval record exists anywhere I searched. If not approved, every artifact calling the tranche "Prompt Two" is mislabelled | R-A04 |
| OQ-5 | **C22/G-05 (the SPEC's 38) vs I3/D07 (the 1.9R adjudication)** — which authority wins? Surfaced 2026-07-24, never answered | R-A05 |
| OQ-6 | **`Diag 1.txt` credentials** — quarantine where, and do you want the blast-radius trace (what indexes that directory) before or after? *Rotation is yours; I will not touch it* | R-B08 |
| OQ-7 | **Program B renumbering** — the prompt and the backlog disagree on B3/B4/B5. Prompt wins by §0 authority order; confirm so it can be renumbered ONCE and never re-litigated | R-B07 |
| OQ-8 | **Enroll the monitor cockpit program into the unified contract, at what priority?** It was never in scope, so it stays invisible until you say so | R-M18 |

**NOT-CHECKED (surfaced, not folded into a pass):** the brief states an "agentify" question and a
"dependency" question are already answered. **Neither appears anywhere in `32-OWNER-DECISIONS.md`
Q1-Q25**, and I did not locate them elsewhere, so I can neither list them as open nor confirm them as
answered. Settling experiment: grep the corpus for the turn that answered them and record it in
`17-DECISION-LOG.md`.

---

## 7. RAW → DEDUPED MAP (auditable compression: 127 → 103)

Merged clusters (24 raw ids absorbed):

- `P1-A01` + `P1-A29` + `P1-EXIT` + `P1-X01` + `P1-X06` + `P1-X11` + `P1-C02` → **R-A21 · R-A22 · R-A23 · R-A24 · R-A25 · R-A26** (each missing artifact paired with the exit criterion it fails). *Reconciliation finding: the two readers listed DIFFERENT six-item missing sets — one included `diagrams`, the other `05-ECOSYSTEM`. My controlled scan says **all seven** gaps are real; each reader under-counted by one.*
- `P2-START` + `A8-PROMPT-TWO` → **R-A01**  ·  `P2-CC-1..13` + `P2-P0` → **R-A02**  ·  `P2-IN-1/2/3` → **R-A03**
- `P2-M-2` + `P2-M-10` + `P2-P6` → **R-A06**  ·  `P2-M-3` + `P2-P7-SCOUT` → **R-A07**  ·  `P2-M-6` + `P2-P2C` → **R-A09**
- `P1-Q01` + `P1-Q02` + `P1-Q03` → **T-02**  ·  `ART-09-JSON` + `ART-06-JSON` → **R-H02**  ·  `ART-12` + `ART-13` → **R-H04**
- `TREE-RECEIPTS` + `B-CONTRACT` + `B7` → **R-H06**  ·  `Q1-INTERLEAVE` + `B-SEQ` → **S-01**
- `B0-SCOPE` + `B0` → **T-07**  ·  `B1-PERF` + `B1` → **T-08**  ·  `B5-GAMESEC` + `B3` → **D-02**  ·  `B4` + `B5` → **R-B04**
- `B2-REVERIFY` + `B6` + `B2`(re-verify half) → **R-B02**; `B2`(authoring half) → **R-B03**
- `T0-3` + `X5` → **R-M03** *(join keys deliberately preserved)*  ·  `U2` + `MON-WFMON-PREDECESSOR` → **R-M04**
- `MON-DRIFT-13` + `MON-DEPLOY-SAFE` + `T0-1` → **R-M02**  ·  `U14-U15` + `X18` + `X17`(residual) → **R-M13**
- `T0-6` + `T0-7` → **R-H10** *(both turned out to be one systemic repo→live rules drift, not two rule-authoring gaps)*

## 8. WHAT I RE-PROBED TODAY, AND WHAT CHANGED

Twelve claims re-probed independently. **Four refuted, one strengthened, seven confirmed.**

| claim as received | verdict | probe |
|---|---|---|
| `MON-SEC-MCPCTL` — shipped-CLI secret leak, "outranks every build item" | **REFUTED — fixed on main** | `safety.py:190` now strips before redacting; docstring names the pre-fix 20/20 leak + the regression test + the `safe-order-swapped` mutant |
| `A3-M02` — UNKNOWN, blocked on CI dispatch | **REFUTED — MERGED (PR #160)** | `9e4f0e55`, ancestor of origin/main, exit 0 |
| `T0-6` — UNKNOWN, "`ci-hygiene.md` absent at that path" (single probe) | **REFUTED — the live file EXISTS (4,420 B)** and the amendment is in the repo (8,219 B, `squash-merge` ×2), just not deployed | `Test-Path` = True; content grep repo=2 live=0 |
| `T0-7` — OPEN, "never landed" | **REFUTED — landed in the repo** (`windows-shell.md:261`), absent live | `git grep` repo hit; live grep 0 |
| `A1-B21` / `A2-F02` — DONE-CLAIMED on a same-author ledger | **STRENGTHENED → DONE-VERIFIED** | `c3c06378` / `e07fd6eb` both real commits, both ancestors of origin/main; control `deadbeef1234` correctly fails |
| 6 Prompt-One artifacts missing · 0 diagrams · cockpit unregistered · 13 monitorcore files stale · `program-a/`+`shared/` absent · `RESUME.json` stale · foundry/scout/forge absent from main | **CONFIRMED** (each with a detector control) | see the evidence column of the matching row |

Detector controls used: known-present file (`14-NO-REGRESSION-CONTRACT.md`, `README.md`) and
known-absent sentinel (`__CONTROL-SHOULD-NOT-EXIST__.md`, `deadbeef1234`) both behaved correctly on
every scan, so no "0 results" above is an uncontrolled zero.

**Not re-probed (inherited, therefore NOT-CHECKED-by-me):** every row marked `[inherited]`. The
largest such blocks are the Program-B wiring probes, the monitor package greps (U7/U10/U14/U18/U20/E5/E7),
and the Prompt-Two mission grades other than M-1/M-3.
