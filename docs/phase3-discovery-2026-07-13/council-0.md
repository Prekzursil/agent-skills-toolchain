---
title: council-0
type: note
permalink: dqverify-repo-20261013/docs/phase3-discovery-2026-07-13/council-0
---

## CONFIG-ARCHITECT lens — Phase-3 SSOT consolidation

### Headline reframe
The problem is not "which SSOT tool" — it is that THREE sources currently claim truth with no verified one-directional deploy: repo HEAD ≠ repo working-tree ≠ live (`~/.agents/harness`), and TWO repos both claim SSOT (`agent-skills-toolchain` historic vs `ast-harness-reconcile` new). The one enforcement layer built (task-8) is committed-but-undeployed — the exact silent divergence this program exists to kill is live right now and nothing detected it. Fix the topology, not the tooling.

**Clean target topology (whole design in one picture):**
```
agent-skills-toolchain  (THE single editable SSOT repo)
├─ tools/mcp/canonical-mcp-servers.json ─render→ ~/.mcp.json ─promote(closed,prune)→ user scope
├─ ci/harness/          ─deploy(install.py --deploy)→ ~/.agents/harness/   ⟵ --check TREE parity
├─ hooks/               ─deploy→ ~/.claude/hooks/
├─ skills/ (enshrined)  ─deploy COPY→ ~/.agents/skills/ ─manifest view→ ~/.claude/skills.daily (local symlink, never committed)
├─ rules/ CLAUDE.md AGENTS.md ─deploy→ ~/.claude/
└─ codex render         ─→ ~/.codex/config.toml + hooks (env_vars, NOT ${VAR})
```
Everything flows repo → live, one way. Live→repo only at the deliberate enshrine step. `~/.claude`/`~/.agents`/`~/.codex`/`~/.mcp.json` are deploy TARGETS, never sources. That single inversion resolves half the ranked problems.

---

### Per-thread design (concrete, rides existing rails)

**Thread 1 — MCP SSOT enforced.** Editable source = `tools/mcp/canonical-mcp-servers.json`; `~/.mcp.json` becomes a generated build output self-declaring `"_generated_from"` via a `render-mcp.ps1` that resolves `${VAR}`. Enforcement = extend the existing `config_drift` gate baseline to cover `enabledPlugins` + `plugin:local-mcp-bridge:*`, because the VERIFIED root cause of codacy/deepsource resurfacing is that they ride the plugin bridge at user scope — a layer the drift gate does not watch and the drop never touched. Fix the drop at `plugin disable … --scope user`, not `.mcp.json`. *Disagree with naive:* "re-run promote with prune" ignores the plugin-bridge leak and does not prevent re-drift — wrong layer.

**Thread 2 — user-scope + one-folder centralization.** Accept the hard constraint (promote is Claude-CLOSED-only; a live session clobbers `~/.claude.json` on exit) rather than fighting it. Run `promote-mcp-userscope.ps1 -PruneExtraUserServers -Yes` once, fully closed, so user scope becomes EXACTLY canonical (adds `angr`, evicts cloud-quality family + firecrawl/tavily/figma-rest/semgrep, lands playwright + Kaggle fixes). Delete `D:/Research/.mcp.json` + the two D: promote-script clones — they exist only because Claude's per-tree walk-up can't reach `C:` from `D:`; user-scope promotion makes them redundant and they are pure drift sources. *Disagree with naive:* "one folder" does NOT mean "put everything under ~/.claude" — centralization = one editable SOURCE (repo), four locations stay as generated deploy targets.

**Thread 3 — config/skill/tool/hook centralization.** One repo, fixed layout. The 192/278/75 skill drift = copy-not-symlink + 86 un-enshrined runtime skills; enshrine the 86, then deploy one-way COPY. KEEP copy — do NOT switch repo→runtime deploy to symlinks (Git-for-Windows `core.symlinks=false` silently degrades a committed symlink to a text file). Rule: symlinks may exist as LOCAL uncommitted deploy artifacts (the `skills.daily` link is fine), never as committed repo content. Allowlist-track declarative config only; extend `no-runtime-junk.yml` to the full state denylist (`*.sqlite*`, sessions/, cache/, auth.json, .credentials.json).

**Thread 4 — cleanup-enforcement hook.** Endorse the `artifact_hygiene` Stop-hook as-is: SHADOW, reuses mutation ledger, advises on untracked/non-gitignored/non-scratchpad paths, NEVER deletes (§9 footguns). Separate the historical litter (25 momentstudio worktree copies, 33 worktree branches) — that is a one-time scripted sweep, not something a gate can retroactively fix. Don't conflate recurrence-prevention (gate) with backlog (sweep).

**Thread 5 — stale-branch reconciliation.** `stale_branch` SessionStart advisory gate: `git merge-base --is-ancestor <b> main` for merged detection (handles squash; `git branch --merged` misses these), age>90d for stale, one-time dedup, deletion stays §9-human-gated. *Disagree with naive:* do NOT auto-delete "merged-looking" branches — several carry unpushed commits (`[ahead 1]`) and battlecats-toolkit has +142/+29/+6 unmerged bodies. Salvage-verify unpushed work FIRST (one-time), THEN mass-prune the `[gone]`/worktree litter.

**Thread 6 — doc-reconciliation-enforcement hook.** `kb_supersede` (near-dup via `recall_index`, nudges `superseded_by:`/`valid_as_of:` per §8) + `scattered_doc` (flags new `*.md` outside canonical roots) — endorse. Config-architect priority = the dual-truth problem: basic-memory is the SEMANTIC SSOT (has supersede chains) while on-disk `.md` sprawl does not; resolution is on-disk plan docs carry a front-matter pointer to their basic-memory permalink or get archived once actioned.

**Thread 7 — scattered-harness-doc reconciliation.** A one-time sweep + a naming rule, not a gate. Define canonical doc roots (repo `docs/`, `.beads/`, basic-memory vault); enforce `~/.claude/` root holds LIVE config only (CLAUDE.md, AGENTS.md, rules/, settings.json), not loose plans. Sweep the 10+ superseded harness plans to `~/.claude/_archive/` with supersede markers; EXPLICITLY retire MEM0-PILOT-PLAN (actively contradicted, mem0=NO-GO, yet reads live). Delete/archive the three stale snapshot trees and banner the 293KB toolkit-gap-analysis — they inflate every recursive search.

**Thread 8 — harness-change-documented+committed gate.** `uncommitted_change` + `doc_required` Stop-hooks (SHADOW→ADVISE) mirrored to a pre-commit hard gate — endorse. CRITICAL addition: "committed" is necessary but insufficient. Today's failure was committed-but-UNDEPLOYED (repo≠live), which a commit-gate would not catch. The real invariant = committed AND deployed AND live-matches-repo; couple this gate to the thread-9 parity check.

**Thread 9 — harness-works-perfectly verification (keystone).** Current `install.py --check` reconciles settings.json hooks but never compares the live `~/.agents/harness` TREE vs `ci/harness` — the active divergence is invisible to it. Add a tree-parity check (hash live `*.py` vs repo `*.py`) and wire `--check` to SessionStart (definitely fires) as a periodic audit, not a human-only command. "Works perfectly" verified on four axes: (1) tree parity live==repo, (2) tests pass, (3) gates actually FIRING (shadow-sink shows fire events), (4) three-way HEAD==working-tree==live. *Disagree with naive:* "harness works = tests green" — coverage ≠ integration; a gate can be CI-green, shadow-inert, AND absent-from-live simultaneously (all three true today).

---

### Where I break from the obvious approach
1. **Do NOT adopt chezmoi (yet).** Its principles are right (allowlist-not-denylist, state/config split, one-way apply, encrypted secrets, per-OS templating) — BORROW them. But adopting a whole dotfile framework mid-consolidation is over-engineering: it solves multi-machine bootstrap (a problem this single Windows box does not have) while NOT solving the actual pain (drift enforcement + clobber-race + deploy-parity). Existing repo→`install.py --deploy`→`promote` rail already works. Revisit the tool only if a second machine materializes. Confidence ~80%.
2. **Kill the second SSOT repo.** `ast-harness-reconcile` created this session to be "source of truth" while `agent-skills-toolchain` also holds skills/harness/MCP source IS the drift the program means to end. Fold its content into `agent-skills-toolchain` (already the enshrine target `ci/harness`). One repo; do not push a standalone reconcile repo.
3. **Config centralization ≠ physical-folder centralization.** One editable SOURCE (repo) with generated deploy targets; the four config locations stay distinct because tools read them at fixed paths.
4. **Anchor drift checks to SessionStart, not `ConfigChange`.** The runtime `config_drift` gate fires on a native `ConfigChange` event the harness's own code documents as possibly-never-emitted — a LOW-confidence load-bearing assumption; adverse-inference says treat it as dead. SessionStart definitely fires.

---

### Top risks (config-architect)
1. **Two-repo SSOT ambiguity** — if both persist, drift is guaranteed. Resolve before any push. (~90%)
2. **Live-session clobber of `~/.claude.json`** — any generate/promote to user scope while a session is open is silently lost on exit; deploy must be Claude-closed OR target a read-at-launch `.mcp.json`, not `~/.claude.json`.
3. **Deploy-parity blindness** — SSOT is worthless if live≠repo and nothing checks it; failing silently NOW. The tree-parity `--check` is the single most important deliverable.
4. **Enforcement-creep nag-hell** — promoting shadow gates to ENFORCE too fast violates the anti-nag ladder (C5) and gets the harness distrusted/disabled. Keep SHADOW→burn-in→ADVISE; ENFORCE only per-gate after proven precision.
5. **Copy-not-symlink recurrence** — the 192/278/75 split re-forms unless deploy stays one-way and enshrine-then-deploy is disciplined. Do NOT "fix" via committed symlinks (Windows degrades them to text files).
6. **Secrets in tracked config** — `~/.codex/auth.json`, `.credentials.json`, `~/.codex/secrets/` sit in-tree. Allowlist-track only + gitleaks pre-commit backstop; whole-dir track leaks them (§9b blast-radius). If any were ever staged, rotate — don't just delete.

---

### Cut as over-engineering
- **chezmoi/age/SOPS full adoption** — principles yes, framework migration no.
- **MCP gateway/aggregator migration** — right EVENTUAL direction for the N×M process explosion + tool-catalogue tax, but a separate runtime-consolidation initiative; does not serve the config-SSOT goal; cut from this program's critical path (flag + schedule separately).
- **`doc_drift` AST-fingerprint binding** — low value where "docs" are plans/audits not code-bound API docs; the `_stripped_signature` stand-in over-fires. Ship SHADOW, expect to demote; do not invest heavily.
- **ML/predictive branch classification** — `merge-base --is-ancestor` + last-commit mtime suffices.
- **A SessionEnd auto-DELETE cleanup sweep** — too risky on Windows; advisory surfacing only, deletion human-gated.
- **Rushing all task-8 gates live at once** — deploy the mechanism, keep the enforcement ladder slow.

**Net:** the win is topological, not tooling — one editable repo, one-directional verified deploy, drift + tree-parity anchored to SessionStart, and a hard decision to delete the second SSOT repo + the D: config copies. The four researched gates are correct and ride the existing dispatcher; ship them SHADOW-first and resist enforcement-creep.