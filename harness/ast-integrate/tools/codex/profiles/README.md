# Versioned Codex profiles

Source of truth for the per-invocation Codex scoping profiles (spec §2). These are the
**versioned repo copies only** — deploying them into `$CODEX_HOME/profiles/` is a separate
step owned by `ci/harness/install.py` (`--deploy-codex`), NOT done here.

## The two-file pattern

Each profile is two files (spec §2a):

| File | Parsed by codex? | Content |
|---|---|---|
| `<name>.config.toml` | Materialized as `-c` overrides by the `codex-invoke` skill (not native `-p`) | ONLY real, `--strict-config`-clean codex keys (spec G6): `model`, `model_reasoning_effort`, `approval_policy`, `sandbox_mode`, `web_search`, `service_tier`, `[shell_environment_policy]`, and (M0 only) static `mcp_servers.<name>.enabled=false` lines. |
| `<name>.scope.json` | **No** (codex never sees it) | The scoping manifest: `mode`, `mcp_allowlist`, `tools`, `skills_allowlist`, `seal`, `model_fallbacks`, `captured_mcp_defs`, `base_snapshot_hash`, `notes`. |

Secrets discipline: MCP creds appear **only** as `${VAR}` placeholders — never inline, in any
`.config.toml`, `.scope.json`, or (doctor-populated) `captured_mcp_defs`.

## Scoping modes (`scope.json.mode` + `seal`)

- **M0** — static difference-disable against a known-fixed base; the `.config.toml` carries
  `mcp_servers.<x>.enabled=false` for every base server not in `mcp_allowlist`. Fully offline.
- **M1** — runtime difference-disable against the live base (`live_base − mcp_allowlist`),
  robust to base drift. One live read, reused for `--print-command` and launch (spec §2e).
- **M2** — sealed base (`seal:true`): **M2a** empty allowlist ⇒ zero-MCP (`--ignore-user-config`);
  **M2b** non-empty allowlist ⇒ re-materialize allowlisted servers from `captured_mcp_defs`
  (fail-closed if uncaptured).

Non-empty `skills_allowlist` + non-empty `mcp_allowlist` ⇒ ephemeral `CODEX_HOME` with a
**materialized `config.toml`** carrying exactly the allowlisted MCP defs (spec §2b — this is
what stops the "MCPs vanish on the skills path" bug).

## The 5 profiles

| Profile | model / effort | sandbox / approval | web | mode | seal |
|---|---|---|---|---|---|
| `audit-readonly-max` | gpt-5.6-sol / max | read-only / never | live | M1 | no |
| `build-sandboxed` | gpt-5.6-sol / high | workspace-write / on-request | live | M1 | no |
| `exec-fast` | gpt-5.6-sol / medium | workspace-write / on-request (fast tier) | disabled | M0 | no |
| `fanout-json` | gpt-5.6-sol / max | read-only / never | disabled | M2 (M2a) | yes |
| `consult-review` | gpt-5.6-sol / max | read-only / never | live | M1 | no |

## Anti-rot

`mcp-manifest.json` (canonical base MCP names) and `models-manifest.json` (allowed slugs) are
the offline sources of truth for `ci/harness/tests/test_codex_profiles.py`. The `codex-doctor`
runs the authoritative live probes (allowlist ⊆ live base, slug resolves, harvest+pin,
exec-runtime scope proof) per codex release and re-pins these manifests when the base drifts.

Doctor-populated fields (`captured_mcp_defs`, `base_snapshot_hash`) are intentionally
empty/absent in the versioned source — they are filled at deploy time.
