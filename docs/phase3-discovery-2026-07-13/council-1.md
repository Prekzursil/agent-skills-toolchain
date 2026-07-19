## PRAGMATIST / ANTI-OVERFIT VERDICT — Phase-3 consolidation

**One-line thesis:** The single highest-value act in this whole program is not building anything — it is **`install.py --deploy` of the already-committed task-8 tree + a 20-line live↔repo parity check**. The mechanism the owner is asking for mostly EXISTS as unpushed source. "SOTA consolidation" here means *deploy, delete, and run the script*, not adopt a new framework. I dissent from both marquee research recommendations (chezmoi, MCP-gateway migration) as scope-inflating overfit for this program.

---

### Two big DISAGREEMENTS with the research up front

**1. REJECT chezmoi as part of this program (confidence ~85%).** The research's own TL;DR concedes the hard problem is "split declarative config from 34 GB of runtime state via an allowlist — not which tool." That allowlist split is achievable *today* with `.gitignore` + the existing `install.py --deploy` (which already excludes runtime state) and the git-tracked toolchain repo. Introducing chezmoi means: a new deploy engine, Go-template forking of every config, an `age` keyring to back up (a new lockout failure mode), and re-plumbing four already-working deploy paths (`promote-mcp-userscope.ps1`, `install.py --deploy`, skills copy, hooks). That is a *second* source-of-truth engine layered on a workspace whose entire disease is *multiple sources of truth*. Chezmoi is the right answer for a fresh fleet; it is overfit for a box that already has repo-as-SoT + a deploy command. **Cut it. Keep the git repo + `install.py --deploy` as the deploy engine.**

**2. REJECT MCP-gateway migration inside this program (confidence ~80%).** The gateway pattern is genuinely good and already partially live (cloud-hub/search-hub/agent-mail). But the *evidenced* pain is drift + promote-not-run + resurfaced-plugin servers — **none of which a gateway fixes**. Gateway migration is per-server labor solving the N×M process-explosion problem, which is not on this program's ticket. Folding it in doubles the blast radius. **Note it as a separate future track; do not gate Phase-3 on it.**

---

### Per-thread design (ride existing rails)

**Thread 1 — MCP single source of truth.** Don't build the generator/render pipeline yet. The fix is procedural and already-tooled: (a) owner-decides the 13 legit drift-ins vs 9 prunes (EVPI-gated, per the MCP map — do NOT silently bet); (b) run `promote-mcp-userscope.ps1 -PruneExtraUserServers -Yes` **Claude-closed** — this lands `angr`, evicts codacy/deepsource/firecrawl/tavily/figma-rest/semgrep, and ships the pending playwright + Kaggle fixes in one shot. The recurring-resurfacer root cause is the **plugin bridge** (`plugin:local-mcp-bridge:codacy` at user scope) which `.mcp.json` pruning can't reach — so the *one* real code change is `claude plugin disable … --scope user` + widen the committed `config_drift` baseline to watch `enabledPlugins`. That's an edit to an existing gate, not a new one. **Disagreement with naive approach:** naive says "write a two-way sync." No — one-way promote already exists; the bug is it was never *run with prune*, not that it's missing.

**Thread 2 — user-scope + one-folder.** Delete `D:/Research/.mcp.json` and the two `D:/*/hooks/promote-*.ps1` clones (stale, drift sources). Once user scope = canonical, no per-drive copy is needed. No new mechanism. The "one folder" is already `~/.mcp.json` → user scope; stop treating the D: copies as config.

**Thread 3 — config/skill/tool/hook centralization. THE decisive anti-overfit call: pick ONE repo.** Right now `agent-skills-toolchain` (memory says canonical) and `ast-harness-reconcile` (RECONCILE-LOG says SoT) are *two* declared sources of truth — the exact disease. Fold `ast-harness-reconcile`'s enshrined content into `agent-skills-toolchain` (established, has CI + `no-runtime-junk.yml`) and retire the sibling repo to a pure staging clone, or vice-versa — but **there must be exactly one.** Deploy via the existing `install.py --deploy`. For the 192/278/75 skills three-way drift: the live `chore/enshrine-runtime-config` branch is already doing this — let it finish, then **switch runtime vault from copy to the deploy command** so it can't silently diverge again. No new tool.

**Thread 4 — cleanup-enforcement.** Build the `artifact_hygiene` Stop gate exactly as the research maps it: reuse the **mutation ledger you already write** to list session-created paths that are untracked + not gitignored + not in scratchpad → `inject` (never delete — §9 footgun). ~1 module method, SHADOW-first, `GATE_CONTRACTS` entry. This one earns its keep and is near-free. Keep.

**Thread 5 — doc-reconciliation ENFORCEMENT hook.** **Push back hardest here.** Do NOT build `doc_drift` with tree-sitter AST-fingerprint doc→`code#symbol@sha` binding — that is Fiberplane frontier machinery for a multi-committer team codebase, wildly overfit for a solo harness, and the research itself flags it will over-fire until tree-sitter coverage lands. **Cut it entirely.** The 80% of value is the `kb_supersede` inject (reuse the *already-built* `recall_index.py` near-dup similarity to nudge AGENTS.md §8 `superseded_by:` on new notes) — cheap, rides existing index, keep that one only. The bulk doc debt is a **one-time cleanup, not a hook problem** (see Thread 6/7).

**Thread 6 & 7 — scattered / superseded doc reconciliation.** This is an afternoon of `git mv`, not a gate. Concretely: (a) create `~/.claude/_archive/` and move the ~10 loose superseded harness plans (SOTA-HARNESS-RECOMMENDATIONS v1/V2, HARNESS-REMEDIATION, MEM0-PILOT-PLAN [actively contradicted], CAPABILITY-PROGRAM-PLANS, etc.) with a one-line `SUPERSEDED-BY:` header pointing at the basic-memory permalink; (b) delete the 3 stale snapshot trees (`_harness-trim-backup-2026-06-05`, `skills-archived-2026-06-11`, `skills.pre-agents-*`) and the ~25 momentstudio worktree audit copies — pure clutter that dominates every census; (c) fix `ast-harness-reconcile/CLAUDE.md` (still documents retired AgentBridge — the #1 contradiction). Recurrence prevention = one lightweight `scattered_doc` inject (new `*.md` outside `docs/`/`.beads/`/vault/`rules/` → nudge). **Disagreement:** naive/SOTA says "build a doc-currency enforcement hook + freshness scoring on 4 axes." No — basic-memory *already* carries the supersede chains (it's the healthiest surface); the on-disk debt is one-time. Reconcile by pointing files AT the vault permalink, don't rebuild the vault's metadata engine on disk.

**Thread 8 — harness-change-documented+committed.** Build `uncommitted_change` Stop gate (reuse ledger: ≥1 tracked-code mutation + dirty tree + no commit this turn → inject), SHADOW→ADVISE. Cheap, keep. But recognize the *real* thread-8 signal is thread-9's parity check — if live≠repo, the change was never committed-and-deployed. Don't over-invest in the interactive gate; the hard block belongs in a repo pre-commit hook, not mid-session.

**Thread 9 — harness-works-perfectly verification. Highest-value single build in the program.** Add a **live↔repo tree-parity check** to the existing `install.py --check`: hash/diff `~/.agents/harness` against `ci/harness` and report divergence. ~20 lines. This is the check that would have caught "task-8 committed but undeployed" — the active silent failure `--check` is blind to today because it only reconciles settings.json hooks, not the code tree. Wire `--check` into the SessionStart advisory (dedup'd) so a human sees drift without a cron. No new framework — extend the command that exists.

---

### What I'd CUT as over-engineering (the anti-overfit list)
- **chezmoi + `age` secrets engine** — new SoT engine on a multi-SoT disease; deploy already exists.
- **MCP-gateway migration** — right pattern, wrong program; solves an unticketed problem.
- **`doc_drift` AST/tree-sitter doc↔code binding** — frontier team-tool; over-fires; solo workspace doesn't need spec-to-symbol@sha binding.
- **A semantic "scattered-doc classifier" service** — the reconcile is `git mv` + archive dir, done once.
- **A stale-branch classification *tool*** — see below; it's a session-start advisory + git one-liners, not software.
- **Any new git repo** — fold to ONE existing repo.
- **Two-way config sync** — one-way promote/deploy already exists.
- **Promoting any new gate past SHADOW before burn-in** — all new gates ship shadow, `GATE_CONTRACTS`-registered so the anti-zombie scorer can sunset the ones that never fire (most of these speculative gates will).

### Thread 4b (stale-branch) — deliberately minimal
Build `stale_branch` as an **advisory-tier SessionStart inject only** (dedup'd like `budget_pacing`): `git merge-base --is-ancestor <b> main` → prunable; last-commit-age > 90d → stale; surface a one-time list, never `git branch -D` (§9-gated). The 56 Reframe / 30 toolchain branches are mostly harmless `_wu*_review`/`worktree-*` litter — a human `git branch -d` sweep + GitHub "auto-delete head branches" clears 90% of it. Do NOT build a salvage-classifier; the branch-triage census already did that analysis by hand once, which is all it needed.

---

### Top RISKS (pragmatist lens)
1. **Program becomes a build-fest and never deploys** — the 5+ proposed gates are seductive; meanwhile the *committed* enforcement layer sits inert in an unpushed branch. Risk: shipping more shadow gates while the real silent divergence persists. **Mitigation: deploy-first, build-second; parity check before any new gate.**
2. **Two-source-of-truth is entrenched by adding a third** (chezmoi, or keeping both repos). Every "SOTA" addition that introduces a parallel store *is* the disease.
3. **Promote-with-prune requires Claude fully closed** — an unavoidable operational gotcha (live session clobbers `~/.claude.json` on exit). Any automation of it will silently fail against a live session. Keep it a documented manual step, not a hook.
4. **New gates ship shadow and stay shadow forever** — without a recorded burn-in/promotion path + `GATE_CONTRACTS` fitness, they're pure catalogue tax. If a gate can't state its promotion criterion, don't build it.
5. **`config_drift` may be permanently inert** (depends on a possibly-unemitted `ConfigChange` host event — LOW-confidence load-bearing assumption). Verify the host emits it before trusting thread-1's runtime sentinel; if not, fall back to the SessionStart `--check` sweep (which doesn't depend on host events).

**Net:** Deploy task-8. Add the tree-parity check. Run promote-with-prune. Delete the D: copies + 3 snapshot trees + fix the AgentBridge CLAUDE.md. Build exactly two cheap ledger-reusing gates (`artifact_hygiene`, `uncommitted_change`) plus one `kb_supersede` nudge, all shadow. Archive the loose docs with permalink pointers. That is the whole program — no chezmoi, no gateway, no new repo, no AST doc-binding.

