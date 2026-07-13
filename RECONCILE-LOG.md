# Reconcile Log

Append-only record of runtime-config reconciliation sweeps (live `~/.agents` + `~/.claude`
→ this versioned repo, the source of truth). Newest first. Each entry records date, scope,
what was reconciled vs deferred, and outstanding owner-decisions. This is the human-readable
drift audit trail, paired with the machine-readable `skills/DEPLOYED-MANIFEST.json`.

Written by the reconcile process; a basic-memory capture of each sweep's *why* is a mandatory
companion step (see the enforcement wiring).

---

## 2026-07-13 (Wave-0) — Deploy + push (audit-gate converged)

**Branch:** `chore/enshrine-runtime-config` · **Commit:** `6fa8047` (Wave-0) · **PUSHED** to `origin`
(agent-skills-toolchain), tracking set. Audit-gate converged (independent Codex audit + our discovery
+ direct git/disk verification → `docs/phase3-discovery-2026-07-13/AUDIT-DESIGN-CONVERGED.md`).

### Done
- **CAS-lite deploy mechanism** (`install.py deploy()`): LOCK → PLAN → BACKUP → STAGE →
  pre-write-CAS-abort → per-file `os.replace` → post-write-parity+restore → receipt. Right-sized (no
  11-state journal / compensation engine / bundle store) per owner spec. +7 tests; 456 harness green.
- **DEPLOYED clean HEAD → live** `~/.agents/harness` (from `git archive HEAD`, NOT the dirty tree —
  held task-9 excluded). 28 files, parity clean, backup taken. **Enforcement now LIVE** (was inert:
  `_canonical_config_edit_guard`/`_basic_memory_nudge` absent pre-deploy → 4 matches post). Live libs
  import clean; hot-swap safe.
- **CLAUDE.md** AgentBridge → RETIRED pointer. **Branch pushed** (fresh branch, no `main` risk, no force).
- Deploy-plan adversarially reviewed (PROCEED-WITH-FIXES; 5 must-fixes closed) + `deploy()` code
  reviewed (every failure path traced).

### Known-open (NOT Wave-0 scope)
- `install.py --check`: `hooks.claude` OK; **`hooks.codex` config drift** (pre-existing — the deploy
  touched only the harness TREE, not `settings.json`) → Codex-parity/config-reconcile wave. The
  drift-detector correctly flagged it (SSOT working).
- Deploy-backup of live lands in `<repo>/ci/harness/backups/` (gitignored) not the live tree — minor
  `BACKUPS_DIR` location smell; functional (restore path recorded in the receipt).
- `source_commit: null` in the receipt (deployed from a non-git archive) — cosmetic; SHA = `6fa8047`.

### Held / deferred
- **task-9 (codex-invoke)** — complete + high-quality but self-reviewed only; HELD, folds into the
  **Axis-C unified cross-vendor workflow design** (next, fresh session).
- MCP user-scope promote (`-PruneExtraUserServers`) — needs Claude fully closed.
- PR to fold branch → toolchain mainline (D0.2) — link offered on push; owner's call.

---

## 2026-07-13 — Initial centralization (config-drift audit)

**Branch:** `chore/enshrine-runtime-config` · **Base:** `feat/codex-fleet-github-wave2`@`80a5863`
· **Commit:** `5d2fca2` (+ a config_drift shape follow-up) · **Not pushed** (awaiting owner).
**Trigger:** the 2026-07-13 config-drift audit (4 domains — harness / skills / mcp / hooks).
Headline: **zero real secrets**; the live drift is coherent, tested, and shadow-gated.

### Reconciled (live → repo)
- **Harness → `ci/harness`**: 8 core + 4 previously-unversioned modules
  (install / registration / recall_index / injection_grammar) + the net-new test suite
  (356 passing) + schemas + README. Carries the Stop-loop fix (populate `event.trigger` from
  `stop_hook_active` + a `ClaimWarning` re-entrancy guard).
  - Defect fixes: implement `EventLedger.last_failed_fingerprint`; fold the 5 `settings.json`
    hooks hand-edits into `registration.build_hooks` (closes the bare-`install.py` wipe
    footgun); correct `_config_drift`'s baseline **path and shape** (installer now records a
    curated-keys snapshot in `installed.json`; gate compares against it) — the shape fix is
    the peer-review follow-up.
- **Skills**: 85 live-only vendored — 30 first-party, 54 into `external/` (origin preserved),
  crypto-ctf **stripped** (313 MB `.venv` + `RsaCtfTool/` checkout excluded).
  `DEPLOYED-MANIFEST.json` added; `design-review-loop` marked superseded by `design-studio`;
  `learned` left live-only.
- **Hooks**: 4 wired-but-unversioned artifacts vendored (`local-tui-reminder`,
  `workflow-monitor-autolaunch`, `create/remove-worktree.ps1`).
- **MCP**: `tools/mcp/canonical-mcp-servers.json` reconciled up to live
  (+agent-mail / biomni-hub / angr, −superseded exa / tavily / firecrawl / figma-rest);
  playwright supply-chain pin (`playwright-mcp` → `@playwright/mcp`) and cloud-hub Kaggle env
  (`KAGGLE_API_TOKEN` → `KAGGLE_USERNAME`+`KAGGLE_KEY`) fixed in **both** `~/.mcp.json` and
  canonical.
- **gitleaks**: `.gitleaks.toml` allowlist extended for the redaction-test fixtures (all
  synthetic, verified non-functional).

### Deferred / flagged
- **D1 (security):** the secret-literal / irreversible-op / credential-read hard-blocks remain
  **default-OFF** (opt-in env flags) per the 2026-07-11 owner directive; the redaction-to-disk
  floor stays on. Enshrined as-is — flip to ALWAYS-ON on request.
- **External skill packs (53):** vendored to `external/` but NOT trusted as first-party; the 3
  hook-installers (gateguard, plankton-code-quality, continuous-learning-v2) need a security
  review before any promotion.
- **codex-fleet-github:** kept experimental-in-canonical (not promoted live) until
  `feat/codex-parity-runner` merges; cloud-hub OVH/Databricks env parked.
- **LOW (harness):** a bare `install.py` still wholesale-replaces `settings.json["hooks"]`, so
  a future NON-harness hook event a user hand-adds could be wiped (no active loss today —
  the harness owns all current groups).

### Outstanding (not yet done)
- Deploy repo→live (harness) + `install.py --check` green + re-run `sync-hooks.ps1`.
- MCP user-scope promote (`promote-mcp-userscope.ps1 -PruneExtraUserServers`) — requires
  Claude **fully closed**.
- Enforcement wiring (canonical-config edit-guard, basic-memory nudge, CI exclude-guard job).
- Push of the branch — **awaiting owner approval**.
