# store-map — the 12-store registry (status as of 2026-10-22)

Every credential store the owner already has on this box. Each entry: path,
shape, status (+evidence), parser to use, allowed sink(s), refresh owner.
Evidence legend: **[V]** = path/mtime probed this session (2026-10-22);
**[R]** = carried from the 2026-10-22 stores research (not re-probed here).
NEVER write values into this file — names, shapes, paths, lengths only.

| id | Path | Shape | Status 2026-10-22 | Parser | Sinks allowed | Refresh owner |
|---|---|---|---|---|---|---|
| grok | `~/.grok/auth.json` **[V]** (1763 B, mtime 10-22 02:58) | issuer-keyed OAuth: top-level keys are issuer URLs; entry = key / refresh_token / user_id / email / team_id / expires_at (RFC3339) / oidc_client_id | LIVE | issuer-map flattener → normalized single-entry doc (grok-lane-import.py:64-80 precedent) | bridge admin import — the ONE bridge already wired; do NOT re-import elsewhere; vault = candidate | grok CLI; the bridge refreshes its own copy. Refresh endpoints = inference, never hand-rolled |
| codex | `~/.codex/` **[V]** (config.toml present; NO auth file) | env-key only — providers reference env vars (e.g. `GROK_LANE_KEY` via `env_key`) | n/a — not a harvest source; roster-relevant | none (config ref scan, names only) | n/a | n/a |
| claude | `~/.claude/.credentials.json` **[V]** (30069 B, mtime 10-21 23:20) | OAuth token file; `designOauth` live, `claudeAiOauth` EMPTY; carries `refreshTokenExpiresAt` | LIVE (designOauth); EMPTY (claudeAiOauth) | shape_json walker; exp from refreshTokenExpiresAt | env (dry-run first); vault candidate | claude CLI rewrites it at runtime |
| zcode | `~/.zcode/v2/credentials.json` **[V]** (18749 B, mtime 10-22 03:14) | flat key-value store | LIVE | shape_json walker; NO native exp → derive from JWT if a value is a JWT | env (dry-run first); vault candidate | zcode CLI rewrites it at runtime |
| gemini | `~/.gemini/oauth_creds.json` **[V]** (1571 B, mtime 10-21 05:41) | standard OIDC pair: access_token string(261), scope string(149), token_type, id_token string(920, JWT), expiry_date unix-ms, refresh_token string(103) | LIVE | shape_json walker; offline JWT exp decode from id_token; sibling `~/.gemini/google_accounts.json` **[V]** (55 B) gives the account tag | env, vault; **DEMO TARGET** | gemini-cli |
| cursor (desktop) | `%APPDATA%\Cursor\User\globalStorage\state.vscdb` **[V]** (3,016,777,728 B ≈ 3.01 GB SQLite, mtime 10-21 09:22) | SQLite keyring (VS Code globalStorage) | LIVE desktop / STALE cli **[R]** | read-only SQLite query (`mode=ro` URI) — NEVER copy the 3 GB file | vault candidate (extract-to-ref) | Cursor app (running) |
| cursor-agent | auth.json at the stores-research locator **[R]** (not re-located in the 2026-10-22 probe of `~/.cursor*`) | OAuth | STALE 2026-09-02 **[R]** | shape_json walker when located | none until owner re-auth | none on this box — watchdog marks stale + alerts |
| opencode | `~/.local/share/opencode/auth.json` **[V]** (2296 B, mtime 2026-04-27 17:18 — mtime CONFIRMS the research date) | OAuth | STALE 2026-04-27 | shape_json walker | none until owner re-auth | none on this box — watchdog marks stale + alerts |
| gcloud | `%APPDATA%\gcloud\credentials.db` **[V]** (20480 B, mtime 10-21 05:39) + `legacy_credentials/<account>/` **[V]** (5 account dirs) | SQLite credential db + per-account legacy dirs; 6 accounts total **[R]** | LIVE | read-only SQLite query; per-account isolation via account dirs (never copy between accounts) | vault candidates (per-account items) | gcloud CLI |
| aws | `~/.aws/sso/cache/*.json` **[V]** (2 cached SSO docs, mtimes Jul-25 / Sep-14) | SSO cache JSON with `expiresAt` | cached / re-auth via CLI | shape_json walker; exp from expiresAt | none (SSO cache is AWS-owned) | `aws sso login` |
| gh | `%APPDATA%\GitHub CLI\hosts.yml` **[V]** (88 B, mtime Jul-24) | hosts map; token arrives via env in this estate (env-token form) | env-keyed | YAML key scan (names only) | n/a (token lives in env; roster tracks the env name) | gh CLI |
| scw / op | `~/.config/scw/config.yaml` **[V]** (4599 B, mtime 08-24) / `~/.op` **[V]** ABSENT this pass | provider CLI configs | scw present (profile-keyed); op not installed | YAML/TOML shape walk; profile names only | vault candidates | provider CLIs |

## Liveness rule

A store rewritten since the last ledger pass = LIVE evidence (mtime is the
signal). The watchdog compares mtimes + decoded expiries per pass; a stale
mtime with a still-valid expiry is `unknown`, not `stale` — only an expired or
research-flagged store is `stale`.

## Cross-store laws (from SKILL.md, restated where they bite hardest here)

- Never copy `auth.json` between accounts — per-account isolation via isolated
  HOME dirs / profiles (grok-fleet GROK_HOME precedent).
- Never read a store into anything but process memory; shape output is
  names/types/lengths only.
- The grok store feeds exactly ONE bridge (never-share-one-Build-credential);
  the demo target is gemini for exactly this reason.
