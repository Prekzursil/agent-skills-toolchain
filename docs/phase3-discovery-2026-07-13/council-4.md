# Council Verdict — Lens: OWNER-WORKFLOW-FIT

The single question my lens asks of every proposed design: **does it survive the owner's actual working conditions** — 25+ concurrent sessions, 50-100-agent worktree-isolated fan-outs, no-babysit autonomy, quality-over-cost, commit/PR-everything, `~/.claude.json` clobber-on-exit, Windows PowerShell/MSYS footguns, and basic-memory as the canonical semantic store? Most of the "obvious" designs in the research **fail that test**. Below is what I'd actually ship.

---

## Headline disagreement (read first)

**Reject chezmoi.** The dotfiles-tool research is competent but solves a problem the owner already solved. He has a **versioned repo-as-SSOT + `install.py --deploy` generate-and-copy engine** (`ast-harness-reconcile`/`agent-skills-toolchain`), a `promote-mcp-userscope.ps1` generator, and CI guards. chezmoi is a **second deploy engine to babysit**, a new failure surface, and — critically — its `age`-encrypted-secrets-in-repo model introduces a *lockout* risk ("back up the key or you're locked out") on a no-babysit box. That is an anti-owner-fit trade. **Cut chezmoi and cut the age/SOPS layer entirely.** Keep the existing `.gitignore`-secrets + gitleaks pre-commit backstop the owner already runs. The deliverable is *finishing* `install.py --deploy` + a parity check, not adopting a new tool.

**Second disagreement: almost nothing here should ever reach ENFORCE/block.** The owner's contract is anti-nag ladder + fail-open + "surface, human decides." Every gate below ships **SHADOW → ADVISORY and mostly stays advisory forever.** A block-happy design will nag-storm across a 100-agent fan-out (the documented N-agent prompt-flood) and get ripped out. The hard blocks belong at the pre-commit boundary where a human reconciles, never mid-fan-out.

**Third disagreement: no auto-delete, no auto-sweep, anywhere.** Stale-branch pruning and artifact cleanup that *acts* replays the `mcp_doctor reap` disaster (machine-wide action killed sibling sessions' live children). With worktree isolation + concurrent sessions, a branch touched today may be a live sibling's. Every destructive step is human-reviewed, one-time, or off.

---

## Per-thread recommended design

### Thread 1 — MCP single-source-of-truth (enforced)
- **Canonical = `tools/mcp/canonical-mcp-servers.json` in the toolchain repo** (D2, already decided). `~/.mcp.json` is a **generated artifact**, self-labeled `canonical-generated`. Generate one-way; never two-way sync (research agrees).
- **Fix the drop at the RIGHT layer.** codacy/deepsource resurface via `plugin:local-mcp-bridge` at **user scope + `enabledPlugins`** — verified. The prior drop operated on `.mcp.json`/`disabledMcpServers`, the wrong surface. Cure = `claude plugin disable <name>@<mkt> --scope user` (the **`mcp-fleet-curation` skill already exists** — use it, don't build new), and **extend the `config_drift` baseline to watch `enabledPlugins` + plugin-bridge servers.**
- **Do NOT rely on `config_drift`'s `ConfigChange` trigger** — it's a LOW-confidence, possibly-never-emitted host event. Owner-fit replacement: a **SessionStart read-only drift-audit** that diffs live user-scope vs canonical and *injects* the extras list. Read-only = safe to run live every session = fits no-babysit. Ship SHADOW → ADVISORY.

### Thread 2 — MCP user-scope + one-folder centralization
- One-time, Claude-fully-closed: `promote-mcp-userscope.ps1 -PruneExtraUserServers -Yes` (adds `angr`, evicts the dropped cloud-quality family + firecrawl/tavily/figma-rest/semgrep, lands the playwright + Kaggle fixes).
- **Delete `D:/Research/.mcp.json` + the two `D:` promote-script clones** — pure drift sources.
- **Owner-fit reality check:** "Claude fully closed" is nearly never true on a 25-session box, so this keeps getting deferred. **Structural fix: generate to a launch-read `.mcp.json` Claude ingests at startup, sidestepping the `~/.claude.json` write-race** for all *future* generation. The one-time prune still needs a closed restart — make it an explicit owner checklist step, not a hook.

### Thread 3 — config/skill/tool/hook centralization
- **SSOT = one repo, deployed DOWN by COPY** (`install.py --deploy`), **never symlink** (Windows Git `core.symlinks=false` degrades a link to a plaintext file — research-confirmed footgun). Copy-not-symlink is why 192/278/75 drift, so the guard is the **parity check (Thread 9)**, not symlinking.
- **Resolve the canonical-repo ambiguity now:** `ast-harness-reconcile` is a *reconcile staging area*, not a rival SSOT. **Merge it into `agent-skills-toolchain` (the CI-backed historic canonical) and retire it.** Two "sources of truth" is the disease, not the cure.
- Enshrine-or-prune the **86 un-enshrined vault skills** (the live `chore/enshrine-runtime-config` branch is already doing this — let it finish).

### Thread 4 — cleanup-after-work
- **`artifact_hygiene` Stop-hook, mutation-ledger-based, ADVISORY, never deletes.** Reuse the mutation ledger you already write → the set of this-session paths that are untracked, un-gitignored, and outside scratchpad. Inject the list. Near-free, precise, no full-tree scan.
- Optional `SessionEnd` sweep is **scratchpad-only, opt-in, never touches a repo** — given the `New-Item -Force`/`rm -rf` footguns, keep it advisory.

### Thread 5 — stale-branch reconciliation
- **`stale_branch` SessionStart, ADVISORY, `merge-base --is-ancestor` (handles squash/rebase), 90-day staleness, per-repo dedup, NEVER deletes.**
- **Owner-fit non-negotiable: skip any branch owned by a concurrent session/worktree** — cross-check the WorktreeCreate registry and exclude mtime-today. Never even *suggest* deleting today's branch. The 56-Reframe / 33-worktree-litter bulk cleanup is a **one-time human-reviewed sweep** (salvage the +142/+34 unpushed bodies first per the triage), not the hook's job.

### Thread 6 — doc-reconciliation enforcement
- **`kb_supersede` nudge riding `recall_index.py`:** on a new memory note / MEMORY.md bullet near-dup of an existing note lacking `superseded_by:`/`valid_as_of:`, inject the §8 supersede reminder. This mechanizes a rule the owner *already follows by hand* — perfect fit. ADVISORY.
- **Cut the `doc_drift` AST/tree-sitter binding gate** — over-engineered for prose scatter; it's a code↔doc-binding tool. Defer indefinitely.

### Thread 7 — scattered-harness-doc reconciliation
- **One-time sweep** of the ~10 loose `~/.claude` root plans (SOTA-HARNESS-RECOMMENDATIONS(+V2), HARNESS-REMEDIATION, MEM0-PILOT-PLAN[contradicted], etc.): each gets a supersede marker, folds into a basic-memory note, or moves to `archive/`. Same for the 3 stale snapshot trees and the 16-doc design-research corpus (mark "implemented").
- **Establish the convention that fits how he already works: durable decisions live in basic-memory (supersede-chained), not loose root `.md`.** On-disk audit/plan docs are ephemeral outputs. Going forward, a lightweight `scattered_doc` inject (new `*.md` outside canonical roots + scratchpad) surfaces violations. ADVISORY.

### Thread 8 — harness-change-documented-and-committed gate
- **`uncommitted_change` Stop-hook inject** (tracked-harness edits + dirty tree + no commit this turn) and fold **`doc_required`** into the existing `claim_warning` module. ADVISORY interactive; the **pre-commit hook is the hard boundary.** Fits "commit/PR-everything" exactly.

### Thread 9 — harness-works-perfectly verification (THE KEYSTONE)
- **Add a live↔repo tree-parity check:** hash-diff live `~/.agents/harness` against repo `ci/harness`. This is the missing verification **failing silently right now** — task-8 is committed-but-undeployed, and `install.py --check` only reconciles settings.json hooks, not the tree.
- **Wire it to SessionStart (read-only, safe live) + `/harness-audit`** — must be automatic, not "when a human runs it," per no-babysit.
- Verify gates are **deployed and firing**, not just CI-green (coverage ≠ integration).

---

## Sequencing (owner-fit priority order)
1. **Deploy task-8 to live + add the parity check (Thread 9).** Without this the *entire enshrinement re-drifts* — the three-way split (repo HEAD ≠ working tree ≠ live) is happening now. This is the keystone; everything else is downstream.
2. Pick ONE canonical repo; merge `ast-harness-reconcile` → `agent-skills-toolchain`, retire it (Thread 3).
3. Fix the MCP drop at the plugin/user-scope layer + SessionStart drift-audit (Thread 1).
4. Ship the advisory gates SHADOW (Threads 4/5/6/8).
5. One-time human sweeps (Threads 5-bulk / 7).
6. MCP prune, Claude-closed (Thread 2).
7. **Later, decoupled:** MCP HTTP-gateway migration.

---

## Top risks (my lens)
- **The fixes themselves are un-runnable in his workflow.** Parity-*write* and promote need Claude closed, which is nearly never true on a 25-session box. Mitigation: parity **check** is read-only (runs live); writes go to a launch-read `.mcp.json`; only the one-time prune waits for a restart.
- **Gate nag-storm across fan-outs.** New gates firing in 50-100 subagents = the documented prompt-flood. Gates must be subagent-aware, per-session dedup, shadow-first, fail-open.
- **Enshrine-then-edit-in-place re-creates the split.** Putting `~/.agents/harness` under git while still editing it live re-drifts unless the parity check lands FIRST and deploy discipline holds. This is the exact failure the program exists to kill, currently active.
- **Coupling risk:** `basic_memory_nudge` needs the ledger `canonical_tree` stamp — the two lanes must deploy together or the nudge is dead-on-arrival.

## What I'd cut as over-engineering
- **chezmoi** (entire tool) — duplicates `install.py --deploy`.
- **age/SOPS secret-encryption-in-repo** — lockout risk; gitignore + gitleaks already suffices.
- **`doc_drift` AST/tree-sitter gate** — wrong tool for prose; defer.
- **Atlan-style doc-freshness scoring** — basic-memory supersede-chains already do this.
- **Coupling the MCP HTTP-gateway migration into this program** — good direction (it genuinely fixes the N×M process explosion he's hit: kernel panic, RAM-OOM), but it's a separate multi-week effort. Do lean-catalog + canonical-prune now; gateway-migrate later, decoupled.

**Bottom line:** the SOTA design in the research is directionally right but over-tooled for this owner. The owner-fit build is *smaller*: finish the deploy engine he already has, add the one parity check that's silently failing, curate MCP at the plugin layer, and ship the rest as advisory shadow gates that surface-not-block — because on a no-babysit, high-fan-out, concurrent-session box, anything that acts autonomously or nags is a liability, not a feature.
