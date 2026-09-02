# FLAG: `merge_generated_cursor_mcp.py` has diverged in BOTH directions

Filed 2026-09-02 while building the surgical-deploy step of
`harness-lineage-reunion-2026-09-02.md` §6.6. **Nothing was copied either way.** Same
discipline as `import-2026-08-28/`: a genuine conflict is flagged, never merged blind.
Out of scope for the harness reunion PR; it needs its own reconcile.

## The two copies

| | repo `main` (`.agents/scripts/merge_generated_cursor_mcp.py`, `cc9a2aec`) | live (`scripts/merge_generated_cursor_mcp.py` on `live-capture/2026-09-02`, `6e82943d`) |
|---|---|---|
| landed | `ed867a45` 2026-09-01 "make the merge registry-authoritative and add --check", pinned by `0573c64a` | present at `c3cde97b` 2026-08-28 "version control-plane SSOT" and unchanged in the 2026-09-02 capture |
| model | **G-6=6B allowlist**: `CURSOR_ENABLED_SERVERS` is the only set emitted; parked catalog lives in `.agents/mcp-cursor-parked-31.json`; the registry is the sole source of an entry's body (live file never read back); `--check` reports drift and writes nothing | **two-phase attachment**: safe default = `CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS` (core six + owner-requested adapters); `--attach-all-safe` projects every safe definition; with `--write` it REQUIRES `--approvals-file` and refuses unless the approved set ⊆ core six (Cursor's approval store keys on server id, so a stale approval auto-approves a newly attached definition); `basic-memory` rendered through the `bm_cursor_http_session.py` stdio proxy (`CURSOR_BM_SESSION_PROXY`) instead of a raw url |
| tests | `.agents/tests/test_mcp_control_plane.py` (main): 6 `test_cursor_*` cases (`g3d_enabled_allowlist`, `g6b_write_emits_only_keep_list`, `renders_live_basic_memory_as_the_shared_http_singleton`, `merge_drops_a_keep_list_server`, `check_reports_live_drift`, `check_is_green_when_live_matches`) | `tests/test_mcp_control_plane.py` (live): ~300 more lines — approval-evidence fail-closed matrix, attach-all dry-run/write gates, never-mount list, linkedin/glm53 owner adapters, plus the owner's 2026-08-28 "never rotate; manifest stays deleted" expectations |

## Measured (Linux, py3.12, live `scripts/` + `tests/` + `agents.json` + parked catalog extracted from the capture)

```text
live tests vs live script                 : 1 failed, 50 passed   (the 1 = Windows-only path probe test_cursor_basic_memory_uses_session_proxy_not_raw_url)
live tests vs MAIN script overlaid        : 27 failed, 20 passed  (26 new failures, all test_cursor_* / linkedin / glm53 / attach-all)
MAIN tests vs LIVE script                 : 6 failed, 18 passed, 1 skipped (all 6 test_cursor_* cases)
```

Neither copy is a superset. Deploying main's file would delete the approval gate the
owner built on live and fail 26 of live's tests; folding live's file into main would
drop the `--check` drift probe and the registry-authoritative body rule and fail 6 CI
tests. The sibling scripts are safe: `merge_generated_claude_mcp.py` (main adds
`type: "http"`) and `mcp_fleet_supervisor.py` (main adds the fleet-total ceiling) pass
the live suite when overlaid, and are in the reunion deploy plan.

Related, same family, not touched: live's `mcp_control_plane.py` is AHEAD of main —
`REMOTE_REQUIRED_SERVERS = {"context7", "firecrawl"}` must be http and tagged
`remote-required`, credential-bearing http servers must be https, http transport may not
declare `command`/`args`, and the literal-secret regex knows `ctx7sk-`/`fc-`. Live also
carries three test files main lacks (`test_cursor_remote_transport_policy.py`,
`test_bm_cursor_http_session.py`, `test_secret_audit.py`). Note `.agents/tests` is not
wired into `.github/workflows/quality.yml` at all today.

## Decision needed (owner)

Which model governs the Cursor MCP surface: the allowlist + `--check` (main) or the
two-phase approval-gated attachment (live) — or both, with the live file's approval
gate grafted onto main's registry-authoritative renderer. Until then the surgical
deploy of this one file is **blocked**; the other two scripts are not.
