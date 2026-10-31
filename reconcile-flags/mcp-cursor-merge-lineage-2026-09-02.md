---
title: mcp-cursor-merge-lineage-2026-09-02
type: note
permalink: dqverify-repo-20261013/reconcile-flags/mcp-cursor-merge-lineage-2026-09-02
---

# FLAG (RESOLVED 2026-09-02): `merge_generated_cursor_mcp.py` had diverged in BOTH directions

Filed 2026-09-02 while building the surgical-deploy step of
`harness-lineage-reunion-2026-09-02.md` §6.6. **Nothing was copied either way.** Same
discipline as `import-2026-08-28/`: a genuine conflict is flagged, never merged blind.
Out of scope for the harness reunion PR; it needed its own reconcile — that reconcile is
the "Result" section below (branch `cursor/generated-cursor-mcp-reconciliation-ae2a`).
Sections 1-3 are the flag as filed; nothing in them was rewritten.

## 1. The two copies (as filed)

| | repo `main` (`.agents/scripts/merge_generated_cursor_mcp.py`, `cc9a2aec`) | live (`scripts/merge_generated_cursor_mcp.py` on `live-capture/2026-09-02`, `6e82943d`) |
|---|---|---|
| landed | `ed867a45` 2026-09-01 "make the merge registry-authoritative and add --check", pinned by `0573c64a`; then `259e3fd0` (PR #305) added `x_cursor.stdio_bridge` rendering | present at `c3cde97b` 2026-08-28 "version control-plane SSOT" and unchanged in the 2026-09-02 capture |
| model | **G-6=6B allowlist**: `CURSOR_ENABLED_SERVERS` is the only set emitted; parked catalog lives in `.agents/mcp-cursor-parked-31.json`; the registry is the sole source of an entry's body (live file never read back); `--check` reports drift and writes nothing; an http server may declare `x_cursor.stdio_bridge`, rendered with `--url <registry url>` | **two-phase attachment**: safe default = `CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS` (core six + owner-requested adapters); `--attach-all-safe` projects every safe definition; with `--write` it REQUIRES `--approvals-file` and refuses unless the approved set ⊆ safe default (Cursor's approval store keys on server id, so a stale approval auto-approves a newly attached definition); `basic-memory` rendered through a **hardcoded** `bm_cursor_http_session.py` stdio proxy (`CURSOR_BM_SESSION_PROXY`) instead of a raw url |
| tests | `.agents/tests/test_mcp_control_plane.py` (main): `test_cursor_*` cases (`g3d_enabled_allowlist`, `g6b_write_emits_only_keep_list`, `renders_a_declared_stdio_bridge`, `merge_drops_a_keep_list_server`, `check_reports_live_drift`, `check_is_green_when_live_matches`, bridge drift/normalise) | `tests/test_mcp_control_plane.py` (live): ~300 more lines — approval-evidence fail-closed matrix, attach-all dry-run/write gates, never-mount list, linkedin/glm53 owner adapters, plus the owner's 2026-08-28 "never rotate; manifest stays deleted" expectations; and `tests/test_cursor_remote_transport_policy.py` (remote http for context7/firecrawl, control-plane validations) |

## 2. Measured before (Linux, py3.12, live `scripts/` + `tests/` + `agents.json` + parked catalog extracted from the capture)

```text
live tests vs live script                 : 1 failed, 59 passed   (the 1 = Windows-only path probe test_cursor_basic_memory_uses_session_proxy_not_raw_url)
live tests vs MAIN script overlaid        : 28 failed, 32 passed  (27 in test_mcp_control_plane.py, 1 in test_cursor_remote_transport_policy.py)
MAIN tests vs LIVE script                 : 9 failed, 21 passed, 1 skipped (6 when filed; #305 added 3 more cursor cases)
```

Neither copy was a superset. Deploying main's file would have deleted the approval gate the
owner built on live and failed 27 of live's tests; folding live's file into main would have
dropped the `--check` drift probe, the registry-authoritative body rule and the registry-declared
bridge, and failed 9 CI tests.

## 3. Related, same family (as filed)

Live's `mcp_control_plane.py` was AHEAD of main — `REMOTE_REQUIRED_SERVERS = {"context7",
"firecrawl"}` must be http and tagged `remote-required`, credential-bearing http servers must be
https, http transport may not declare `command`/`args`, and the literal-secret regex knows
`ctx7sk-`/`fc-`. Live also carried three test files main lacked
(`test_cursor_remote_transport_policy.py`, `test_bm_cursor_http_session.py`,
`test_secret_audit.py`). `.agents/tests` was not wired into `.github/workflows/quality.yml`
at all.

## 4. Result (2026-09-02, branch `cursor/generated-cursor-mcp-reconciliation-ae2a`)

ONE reunited `.agents/scripts/merge_generated_cursor_mcp.py` on main's lineage, tests first
(the live tests were ported RED, then the script was made to pass both). The live tests were
read as the spec; every live-only behaviour they pin is in, and every main-only behaviour is
kept.

### 4.1 Measured after

```text
in-repo, .agents/tests (the new CI step):
  test_mcp_control_plane.py (main)              : 30 passed, 1 skipped
  test_mcp_control_plane_live.py (ported live)  : 37 passed
  test_cursor_remote_transport_policy.py (live) :  9 passed
  test_mcp_fleet_supervisor.py                  :  6 passed
  total                                         : 82 passed, 1 skipped

cross-checks against the VERBATIM lineage test files (overlaid on the live tree with the
reunited script + control plane + registry, exactly as section 2 measured):
  live VERBATIM tests vs reunited                : 1 failed, 59 passed   (same count as live vs live; the 1 = the hardcoded-proxy test, adapted -- 4.3)
  MAIN ORIGINAL tests vs reunited                : 1 failed, 29 passed, 1 skipped (the 1 = enabled=/disabled= summary words, adapted -- 4.3)
ruff check / ruff format --check (.agents/scripts, .agents/tests): clean; .quality/charter_check.sh: OK
```

### 4.2 What the reunited script is

Main's renderer and rules, unchanged:

- `x_cursor.stdio_bridge` rendering with `--url <registry url>` appended (PR #305); the script
  hardcodes **no** shim — an http entry without the declaration renders the direct URL, which
  is what keeps `--check` honest.
- `CURSOR_ENABLED_SERVERS` == the core six (G-6=6B keep-list; `test_cursor_g3d_enabled_allowlist_matches_locked_keep_list`).
- The registry is the ONLY source of a governed entry's body: a governed name the registry does
  not generate is **dropped, never adopted** — in both modes (see 4.3 for what "governed" means).
- `--check`: read-only drift report (`FAILED:mcp-cursor-check ... servers=<names>` exit 1 /
  `SUCCESS:mcp-cursor-check ... drift=0`), refuses `--write`, now also reports
  `attach_all_safe=`; `parked_skips=` and `bridged=` stay in the merge summary.

Live's attachment layer, ported (function-for-function from `6e82943d`):

- `CURSOR_RETIRED_SERVERS = {mixpanel, mixpanel-mcp}` and `cursor_unmountable_servers()`:
  never mounted from any source, even if the registry regresses.
- `CURSOR_DEFAULT_APPROVED_SERVERS` (core six) and `CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS`
  (core six + `glm53-space`, the owner-requested adapter); default merge attaches exactly that.
- `--attach-all-safe`: projects every safe registry definition; dry-run/`--check` are
  projections; `--write` REQUIRES `--approvals-file`.
- `ApprovalEvidenceError`, `parse_cursor_approvals` (`<name>-<16 hex>` ids, fails closed on
  absent/unreadable/malformed), `load_safe_default_approvals` (refuses evidence wider than the
  safe-default set, names the offenders), `fail()` → `FAILED:mcp-cursor-merge <reason>` on
  stderr, exit 2.
- `strip_disabled`: nothing written ever carries `disabled` (Cursor has no such field);
  `classify_registry_skips`; the summary vocabulary `attached= core_attached= noncore_projected=
  manual_preserved= disabled_keys= registry_disabled_skips= no_target_skips= attach_all_safe=
  approval_proof=`.

### 4.3 Where the suites genuinely contradicted each other, and the choice made

| contradiction | live pinned | main pinned | choice (registry stays authoritative) |
|---|---|---|---|
| `basic-memory` transport | `build_cursor_server("basic-memory", {http, url})` with **no** `x_cursor` returns the hardcoded `CURSOR_BM_PYTHON` + `CURSOR_BM_SESSION_PROXY --stdio` (`test_cursor_basic_memory_uses_session_proxy_not_raw_url`) | the same input renders `{"url": ...}`; the shim exists only when the registry declares it, and then WITH `--url` (`test_cursor_check_is_green_when_the_live_file_matches_the_registry`, `test_cursor_renders_a_declared_stdio_bridge_with_the_registry_url`) | **main.** The proxy is declared by the registry (`agents.json` `basic-memory.x_cursor.stdio_bridge`), the constants are gone. The ported live test is ADAPTED: it asserts the proxy through the live registry entry, that an undeclared entry renders the URL, and that the declared script is the tracked repo copy (this also removes the one Windows-only path probe that failed on Linux). The live intent — Cursor never dials the raw basic-memory URL — is preserved *because the registry says so*, and now every renderer/`--check` agrees. |
| manual live entries under `--attach-all-safe` | preserved: `hand-rolled` and `stale-disabled` (names the registry never had) survive attach-all, `disabled` stripped (`test_cursor_attach_all_preserves_safe_manual_live_entries`); live's code adopted ANY non-generated live name | a keep-list name the registry stopped generating must be dropped, never adopted (`test_cursor_merge_drops_a_keep_list_server_the_registry_no_longer_generates`, default mode) | **both, narrowed to live's own docstring** ("manual, *non-registry* live entries"): under attach-all a live entry is preserved only if its name is **ungoverned** — not generated, not in `mcp.servers` at all (`main()` passes `registry_names=set(servers)`), not in the safe-default set, not never-mount. A governed name the registry stopped generating is dropped in BOTH modes. `manual_preserved=` in the summary counts what was kept. |
| merge summary words | `"enabled=" not in stdout` — Cursor has no `disabled` field, so runtime-state words are misleading (`test_cursor_default_dry_run_projects_core_plus_owner_adapters`) | `enabled=2` / `disabled=0` (`test_cursor_g6b_write_emits_only_keep_list`) | **live's vocabulary** (the considered, documented change; under main's own G-6=6B rule `disabled=` was always 0). Main's test is ADAPTED to `attached=2 disabled_keys=0 parked_skips=1 attach_all_safe=false` and itself pins the absence of `enabled=`. Not a registry-authority question; recorded here so the summary line is not "fixed back". |
| `credential_rotation_manifest.json` | must NOT exist (`test_rotation_manifest_file_is_absent_never_rotate`; `validate_mcp_control_plane.py` prints `rotation_providers=0 rotation_policy=never` when absent) | skip when absent, validate when present (`test_rotation_manifest_contains_references_but_never_values`; the `.agents/.gitignore` negation anticipates a future capture committing it) | **no runtime conflict** (the file is absent on both). Live's two tests are ported and `validate_mcp_control_plane.py` gets live's never-rotate branch (main's version raised `FileNotFoundError` on the live box, where the manifest is deleted by owner decision 2026-08-28). Main's skip-test stays; if the owner ever reverses "never rotate", delete the live pair and the `.gitignore` negation already allows the file. |

### 4.4 Adjacent folds this needed (the live tests read the registry and the control plane)

- `.agents/scripts/mcp_control_plane.py`: live's validations folded onto main's `_validate_x_cursor`
  (disjoint hunks, no conflict): `REMOTE_REQUIRED_SERVERS`, http may not declare `command`/`args`,
  credential-bearing http must be https, `ctx7sk-`/`fc-` prefixes.
- `.agents/agents.json`: reunited = live registry + main's `basic-memory.x_cursor` block. Three-way
  merge with **no conflicting hunk**: live-side = context7/firecrawl → hosted https
  (`remote-required`), `glm53-space`, `linkedin`, huggingface description; main-side = `x_cursor`
  only. The reunited file differs from live's capture by exactly the 9-line `x_cursor` block
  (measured with `diff`). Provenance for the folded entries: `.provenance/.agents/agents.json.md`.
- `.agents/mcp-cursor-parked-31.json`: live's `_comment` (two-phase rollback catalog); the 31
  server bodies are byte-identical.
- `.agents/scripts/validate_mcp_control_plane.py`: missing manifest → `rotation_policy=never`.
- `.github/workflows/quality.yml` (`test-python`): new step `gate-tests-coverage mcp control
  plane` runs the four `.agents/tests` files above; `.quality/charter_check.sh` OK.

### 4.5 Siblings checked for the same split (main vs `live-capture/2026-09-02`, cross-run both ways)

| file | semantic diff | live tests vs MAIN copy | MAIN tests vs LIVE copy | verdict |
|---|---|---|---|---|
| `merge_generated_claude_mcp.py` | **none** — live already renders `type: "http"` (its line 66); only a comment and `ruff format` line breaks differ | green | green | **no split**; deploy main's copy (cosmetic) or leave live's |
| `mcp_fleet_supervisor.py` | one-directional, main ahead: fleet-total ceiling (`total_over_budget`, `fleet_over_budget=`/`sessions_over_budget=` in the summary), unused `asdict` import dropped | green (live's 4 tests ⊂ main's 6) | 1 failed: `test_fleet_total_above_the_idle_ceiling_is_degraded` (feature absent in live) | **no split**; deploy main's script + main's test file, as §6.6 of the reunion plan already says |
| `merge_generated_codex_mcp.py` | formatting only (quote style / wrapping) | green | green | no split |
| `bm_cursor_http_session.py` | one-directional, main ahead (#305 hardening) | live's 12 tests green against main's bridge (main's suite has 26) | — | no split; covered by #305's deploy note |
| `mcp_control_plane.py` | two-directional but **disjoint** (live: validations; main: `x_cursor`) | — | — | reunited here (4.4) |
| `validate_mcp_control_plane.py` | one-directional, live ahead (never-rotate) | — | — | folded here (4.4) |

## 5. Deploy note for the owner (Windows box; edit checkout `~/source/ast-integrate`, on this branch or on `main` after merge)

Direction: repo → live. **Ordering is load-bearing:** the reunited script hardcodes no
basic-memory proxy, so it MUST land together with the reunited `agents.json` (which carries
`x_cursor.stdio_bridge`). Copy the script alone onto the current live registry and Cursor's
basic-memory entry renders the raw URL again — the measured 27.08 failure state.

```powershell
# 0. Backup (belt and braces; --write also backs up mcp.json on its own)
$A = 'C:\Users\Prekzursil\.agents'
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$bk = "$A\backups\cursor-merge-reunion-$stamp"
New-Item -ItemType Directory -Force "$bk\scripts","$bk\tests" | Out-Null
Copy-Item "$A\agents.json","$A\mcp-cursor-parked-31.json" "$bk\"
Copy-Item "$A\scripts\merge_generated_cursor_mcp.py","$A\scripts\mcp_control_plane.py","$A\scripts\validate_mcp_control_plane.py","$A\scripts\mcp_fleet_supervisor.py","$A\scripts\merge_generated_claude_mcp.py","$A\scripts\bm_cursor_http_session.py" "$bk\scripts\"
Copy-Item "$A\tests\test_mcp_control_plane.py","$A\tests\test_cursor_remote_transport_policy.py","$A\tests\test_mcp_fleet_supervisor.py" "$bk\tests\"
Copy-Item "$env:USERPROFILE\.cursor\mcp.json" "$bk\mcp.json"
"$bk"   # keep: rollback source

# 1. Pre-flight, read-only: the registry delta must be exactly the x_cursor block
cd C:\Users\Prekzursil\source\ast-integrate
git status --short --branch
git diff --no-index --stat "$A\agents.json" .agents\agents.json      # expect: 1 file, +9 lines, -0 (basic-memory.x_cursor)

# 2. Registry + control plane + renderer, together (the pair that must not be split)
Copy-Item .agents\agents.json                                "$A\"
Copy-Item .agents\mcp-cursor-parked-31.json                  "$A\"
Copy-Item .agents\scripts\mcp_control_plane.py               "$A\scripts\"
Copy-Item .agents\scripts\validate_mcp_control_plane.py      "$A\scripts\"
Copy-Item .agents\scripts\merge_generated_cursor_mcp.py      "$A\scripts\"
Copy-Item .agents\scripts\bm_cursor_http_session.py          "$A\scripts\"   # #305 hardened bridge (live's 12 tests pass against it)
# the two no-split siblings from reunion plan §6.6
Copy-Item .agents\scripts\mcp_fleet_supervisor.py            "$A\scripts\"
Copy-Item .agents\scripts\merge_generated_claude_mcp.py      "$A\scripts\"
# tests: main's control-plane file REPLACES live's (its cursor block now lives in the _live file)
Copy-Item .agents\tests\test_mcp_control_plane.py            "$A\tests\"
Copy-Item .agents\tests\test_mcp_control_plane_live.py       "$A\tests\"
Copy-Item .agents\tests\test_cursor_remote_transport_policy.py "$A\tests\"
Copy-Item .agents\tests\test_mcp_fleet_supervisor.py         "$A\tests\"

# 3. Verify on the box BEFORE any --write
cd $A
python scripts\validate_mcp_control_plane.py                                      # SUCCESS ... servers=42 ... rotation_policy=never
python -m pytest tests\test_mcp_control_plane.py tests\test_mcp_control_plane_live.py tests\test_cursor_remote_transport_policy.py tests\test_mcp_fleet_supervisor.py -q
#   expect 82 passed, 1 skipped (the skip = main's rotation-manifest test; the manifest is absent by decision)
python scripts\merge_generated_cursor_mcp.py --check
#   expect EXACTLY: FAILED:mcp-cursor-check ... drift=1 servers=basic-memory attach_all_safe=false
#   (the live hand edit lacks --url). ANY other name in servers= is new information: stop, read it, do not --write.
python scripts\merge_generated_cursor_mcp.py                                      # dry run; expect attached=7 core_attached=6 noncore_projected=1 approval_proof=not-required write=false

# 4. Apply (default mode: the surface does not change -- core six + glm53-space, as today)
pwsh -File scripts\sync_shared_state.ps1            # or only Cursor:  python scripts\merge_generated_cursor_mcp.py --write
python scripts\merge_generated_cursor_mcp.py --check                              # SUCCESS:mcp-cursor-check ... drift=0 managed=7
Get-Content "$env:USERPROFILE\.cursor\mcp.json" | Select-String -Context 0,6 '"basic-memory"'   # command + args ending in --url http://127.0.0.1:8765/mcp
# Cursor: reload the window (a definition change needs a restart). Tools list populates.
```

Rollback = restore `$bk\agents.json`, the six scripts and `$bk\mcp.json` (or the automatic
`mcp.json.bak-<ts>`), then reload Cursor. No daemon, port, task, approval store or secret is
touched by any step above; the approval-gated `--attach-all-safe --write` path is NOT run by
`sync_shared_state.ps1` and is only ever run by hand with the 7-step procedure in the
script's docstring.

## 6. Decision taken (what the owner still has to confirm)

Which model governs the Cursor MCP surface: **both, as one script.** The allowlist + `--check`
(main) is the default and the drift probe; the two-phase approval-gated attachment (live) is
the explicit widening path. The registry stays authoritative in every mode (4.3). The surgical
deploy of this file is **unblocked** with the ordering constraint in section 5. Left for the
owner to confirm on the box: that `--check` reports exactly `drift=1 servers=basic-memory`
before the write (anything else means the live `mcp.json` has moved since the 2026-09-02
capture and needs reading first), and whether main's rotation-manifest skip-test should be
retired now that "never rotate" is pinned in CI by the ported live pair.