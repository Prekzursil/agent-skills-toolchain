# Estate locks, written down once (L1-L7, G-32, G-36)

Status: normative index as of 2026-09-02 (hosted-models build wave). Each lock appears here
exactly once with its rule, where a machine ENFORCES it today, and which clauses are merely
DOCUMENTED (prose that a human must hold; nothing fails when it is broken). The data copy of
the same list is `locks[]` in `.agents/models.json`; the two must agree, and a change to one
lands with the other in the same commit.

Why this file exists: the consolidated hunt's verification row V18
(`docs/gem-hunt/2026-09-02-hosted-models/CONSOLIDATED-GEM-DECISIONS.md`, section 3) found the
locks scattered across `.agents/AGENTS.md` (L5), `.agents/skills/openrouter-routing/SKILL.md`
and `.agents/skills/gem-hunt/SKILL.md` (L1, L2), `skills/hosted-model-agents/SKILL.md` (L3,
G-32, G-36), and a brief that nobody in the repo could cite (the 7-day retirement clause of L3,
L6 "never rotate", L7). This file is the answer to V18. Every path in backticks below is checked
for existence by `ci/tests/test_estate_locks_doc.py`, so a lock can no longer point at a file
that has moved.

How to read the table: "ENFORCED" names a check that fails closed (a validator error, a CI job,
a runtime refusal) at the path given. `V1`-`V20` are the red-proof rules of
`.agents/scripts/models_control_plane.py`, one failing fixture per rule in
`.agents/tests/test_models_control_plane.py`; `V-P1`-`V-P14` are the rules of
`.agents/scripts/routing_policy.py`, pinned by `.agents/tests/test_routing_policy.py`. "DOCUMENTED
only" lists the clauses no check holds, as V18 recorded them.

| id | rule (one sentence) | ENFORCED today | DOCUMENTED only |
|---|---|---|---|
| L1 | OpenRouter is a spend-capped CLI/Codex sidecar only: never Cursor BYOK, never Claude ANTHROPIC_BASE_URL, never a new OpenRouter MCP. | `.agents/models.json` lock L1 and the `openrouter` row (`sidecarOnly: true`, `denyCallers` holds `cursor` and `claude`, `targets.cursor` and `targets.claude` are `excluded`); `.agents/scripts/models_control_plane.py` V7 (a `sidecarOnly` row may not target `cursor` or `claude`), V14 (`openrouter` must be `sidecarOnly`), V15 (`denyCallers` must name `cursor` and `claude` on `openrouter` and its models); `.agents/scripts/routing_policy.py` V-P9 (an OpenRouter rung or escalation needs `callers` within codex / cli); `tools/mcp/inference-hub/hub/registry.py` refuses denied callers at call time (`CALLER_DENIED`). | The BYOK and `ANTHROPIC_BASE_URL` clauses are box settings, held by `.agents/skills/openrouter-routing/SKILL.md` and the anti-overfit anchor in `.agents/skills/gem-hunt/SKILL.md`; "no OpenRouter MCP" is held by review of `.agents/agents.json`. |
| L2 | No LiteLLM proxy, no LangGraph, no second orchestration runtime, no vector-DB memory (Aider embedding the litellm library is a render target, not a proxy). | Nothing direct: `.agents/models.json` records `enforcedBy: review` for L2. Indirect: the validators and the hub are stdlib-only and their suites run in CI with pytest alone (`docs/gem-hunt/2026-09-02-hosted-models/BUILD-CONTRACT.md` section 0), so an import of either package fails there. | The whole lock: `.agents/skills/openrouter-routing/SKILL.md` ("Do not install LiteLLM"), the anchor in `.agents/skills/gem-hunt/SKILL.md`, and the SKIP rows of the consolidated hunt (SK3, SK5, SK6, SK19). |
| L3 | auth2api `:8317` stays the only Cursor bridge and retires within 7 days of an official Cursor `/v1` GA. | `.agents/models.json` lock L3 and the `cursor-auth2api` row (`singletonKey: cursor-bridge`, `retiresWhen`); `.agents/scripts/models_control_plane.py` V6 (two enabled endpoints may not share a `singletonKey`), V13 (`cursor-auth2api` must carry `retiresWhen`), V8 (port 8317 is refused on any other endpoint id); `.agents/scripts/routing_policy.py` V-P5 (at most one `cursor-*` rung per class) and V-P10 (a primary on a retiring endpoint needs an escalation on one that does not retire). | The 7-day clock itself: `retiresWhen` is a sentence, not a timer, and no official Cursor `/v1` exists yet (V33), so the trigger has not fired; re-check at each hunt. |
| L4 | Ports 8765 (basic-memory), 8812 (agent-mail), 8317 (auth2api) and 8770 (browser-bridge hub) are owned; 8901 belongs to `inference-hub`, the only new resident process, and it idle-exits. | `.agents/models.json` lock L4 and `policy.hub` (`host: 127.0.0.1`, `port: 8901`, `idleExitSeconds: 600`); `.agents/scripts/models_control_plane.py` V8 (an endpoint `baseUrl` on 8765 / 8812 / 8770, on 8317 for any id but `cursor-auth2api`, or on 8901 is an error) and the `policy.hub` checks (loopback host; the port may not be an owned one); the owned URLs themselves live in `.agents/agents.json` (8765, 8812) and `SECURITY.md` (8770). | "Only new resident process" and idle-exit are the hub server's own behaviour (the bind on 8901 is the single-instance mutex; watchdog exits at `idleExitSeconds`), specified in `docs/gem-hunt/2026-09-02-hosted-models/BUILD-CONTRACT.md` section 4; no check outside the hub counts resident processes. |
| L5 | `.agents/skills` is the ONE prompt SSOT; every runtime loads skills from it and profiles resolve to paths under it. | `.agents/AGENTS.md` "Universal harness share (HARD)"; root `AGENTS.md` names `.agents/skills/` canonical and `skills/` a compatibility copy; `ci/check_skill_dual_write.py` (D-001 guard, run by `.github/workflows/skill-dual-write.yml`) fails a change that edits one root without the other. | `.agents/models.json` lists `inference-hub:profile-resolver` for L5, but no profile resolver exists under `tools/mcp/inference-hub/` yet (the `x_hub.profile_root` block is declared in the contract, section 1.4, and unused); until it lands the hub side of L5 is prose. |
| L6 | Never rotate credentials; secrets by environment-variable NAME only; a value never appears in a registry, rendered config, ledger, log, report, fixture or doc. | `.agents/scripts/models_control_plane.py` V1 (a literal secret anywhere in the registry is the first error; shapes from `LITERAL_SECRET_RE` in `.agents/scripts/mcp_control_plane.py` plus AWS, Slack and PEM extras), V2 (`auth.env` / `altEnv` must be environment names), V19 (a credential is bound to its issuer host); `.agents/scripts/routing_policy.py` names-only rule (URL or credential-shaped text is an error labelled L6); `tools/mcp/inference-hub/hub/redaction.py` (outbound scan for the exact values of every registry credential set in the environment plus the literal patterns; `REFUSED_SECRET_IN_PROMPT`); `.gitleaks.toml` with the `gate-secrets (gitleaks)` job in `.github/workflows/quality.yml` (repo-wide, names only). | "Never rotate": no repo check can hold a non-action, and `.gitleaks.toml` (allowlist 1) says the committed private-env tokens "SHOULD be rotated/revoked"; that escalation is the owner's (DECISION-QUEUE D7 note), not this lock's. |
| L7 | Never remove a feature to buy simplicity or reliability; present the tradeoff and keep the capability reachable. | `.agents/tests/test_models_control_plane.py` `test_glm53_capability_preserved` (the L7 receipt: `glm-5.3` on `hf-router` stays reachable through the hub after the glm53-space lane was deleted); `.agents/scripts/models_control_plane.py` V10 (local RAM over budget is a WARNING, never an error that drops a row) and the routing report, whose every `excluded` row names an `alternative`; `.agents/scripts/merge_generated_cursor_mcp.py` moved the deleted lane's safe-default slot to `inference-hub` (`CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS`) and purges the stale name (`CURSOR_RETIRED_SERVERS`) instead of leaving Cursor with nothing. | The general rule: brief-only until 2026-09-02 (V18); now data in `.agents/models.json` lock L7 and prose here. Whether a given change "removes a feature" is a review judgement. |
| G-32 | `ai-mode` and the `*-cursor` wrappers stay process-local to auth2api `:8317`; no persistent global Cursor-bridge environment. | `.agents/models.json` `cursor-auth2api` row (`denyCallers: cursor`, `targets.cursor: excluded`) and `.agents/scripts/models_control_plane.py` V15 (`cursor` must be denied on every `cursor-*` endpoint and model): Cursor never calls its own bridge; wire shapes stay `declared` until the D9 probe, so no `*-cursor` wrapper is rendered before it passes. | The process-local / no-global-env clause is a box posture: `skills/hosted-model-agents/SKILL.md` hard rule 5 (mirror `.agents/skills/hosted-model-agents/SKILL.md`). |
| G-36 | At most one `cursor-agent` process at a time (RAM). | Nothing counts `cursor-agent` processes. The nearest data is `concurrency.maxInFlight: 1` on the `cursor-auth2api` row in `.agents/models.json` (one call in flight to the bridge); `.agents/scripts/mcp_fleet_supervisor.py` dedups MCP daemons, not `cursor-agent`. | The whole lock: `skills/hosted-model-agents/SKILL.md` hard rule 5 (mirror `.agents/skills/hosted-model-agents/SKILL.md`). |

## Build-wave amendments (2026-09-02)

- L4: port 8901 is `inference-hub`, the ONE new resident process the wave adds (owner answer D3,
  `docs/gem-hunt/2026-09-02-hosted-models/BUILD-WAVE-STATUS.md`). It is lazy-started by a stdio
  shim on first use and idle-exits after `policy.hub.idleExitSeconds` (600 s), so it costs no RAM
  when unused; a second copy fails its bind and exits. No other new port or daemon is allowed by
  the wave. Design source: `docs/gem-hunt/2026-09-02-hosted-models/BUILD-CONTRACT.md` section 4.
- L6: the fine-grained inference-only token NAME `HUGGINGFACE_TOKEN_INFERENCE` was ADDED (D7); the
  Hub MCP keeps `HUGGINGFACE_TOKEN`; nothing is rotated or revoked. The OpenRouter sidecar gained
  labelled key NAMES (`OPENROUTER_API_KEY_CODEX_SIDECAR`, `OPENROUTER_API_KEY_CLI_GRUNT`, optional
  `OPENROUTER_API_KEY_IDE_OPENCODE`, D8) while the legacy `OPENROUTER_API_KEY` stays as it is.
  The owner mints in the browser and sets the variables by hand
  (`docs/gem-hunt/2026-09-02-hosted-models/OWNER-CLICKS.md`); agents never mint.
- L7: the glm53-space MCP lane was hard-deleted (D1 = B) and its capability kept as model
  `glm-5.3` on endpoint `hf-router`; the receipt is the test named in the L7 row.

## Honest gaps (no machine holds these today)

- L2 as a whole, L6 "never rotate", the 7-day clock of L3, the process-count clause of G-36 and
  the process-local clause of G-32 are prose. They were prose in the brief too (V18); the change
  is that the prose now has one address.
- L5's hub-side clause names a resolver that is not on this branch. When `x_hub.profile_root` is
  wired, move it from the DOCUMENTED column to ENFORCED with the module path.
- L1 "no OpenRouter MCP" has no validator rule in `.agents/scripts/mcp_control_plane.py`; it is
  review of `.agents/agents.json` at sync time.

## How to change a lock

Edit `locks[]` in `.agents/models.json` and this table in the same commit, run the registry
validator CLI (`.agents/scripts/validate_models_control_plane.py`, which must print its
`SUCCESS:models-registry` line) and the doc test (`ci/tests/test_estate_locks_doc.py`), and record
the reason in `.provenance/.agents/models.json.md`. A lock is never deleted; a retired lock keeps
its id with the word RETIRED and the date in its rule text (L7 applies to the locks themselves).
