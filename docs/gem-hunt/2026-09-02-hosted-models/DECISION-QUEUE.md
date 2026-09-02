# Hosted-models hunt - OWNER DECISION QUEUE (2026-09-02)

13 decisions. Recommended option is always **first**, with the reason. Cost = RAM / money / effort
(effort = files or subsystems touched, not calendar time). Ids match CONSOLIDATED-GEM-DECISIONS.md.
Facts behind each are verified there (V-rows). Nothing here is built yet.

**D1. glm53-space deprecation path?** (G7, C1, C5)
- **A. Redirect tombstone in the SAME registry slot** - archive the box copy first (T0-1; it is on
  no remote ref), land the successor `enabled:false`, overlap window, then `glm53-space` becomes
  `enabled:false` + `RETIRED 2026-09-xx -> use inference`, `RETIRED_MCP_SERVERS += glm53-space`,
  move its `CURSOR_SAFE_DEFAULT_ATTACHED_SERVERS` slot (owner-requested default adapter) to the
  successor, retire the pinned test on purpose; remove one release later. *Why:* Cursor approval
  ids are `<name>-<hash>`; a rename looks like a new server; "a tombstone resolves, a missing
  server fails opaquely" (codex-consult precedent). Cost: 0 RAM; ~5 files; reversible per step.
- B. Hard-delete row + dir now. Cost: 0; breaks in-flight Claude/Cursor mounts; loses the parity
  oracle. C. Keep as-is. Cost: keeps a dangling path + hardcoded pair.

**D2. Registry SSOT shape?** (G2, C2)
- **A. Sibling `.agents/models.json` + `models_control_plane.py`** cloned from the MCP validator
  (reference-only creds, closed `x_*`, `locks[]`, capability lattice, per-endpoint `api[]`).
  *Why:* keeps `agents.json` blast radius and `lastSyncSourceHash` untouched; six lenses converge
  on the field set. Cost: 0 RAM; 1 module + 1 file + ~13 tests.
- B. `upstreams` block inside `agents.json` (lens 11): one file, but the MCP validator must learn
  a second domain and every model tweak re-hashes the fleet. C. Synced `state/catalog/index.json`
  only (lens 13): no SSOT for `:8317` / `ollama` / `lms`, which no public feed knows.

**D3. Generic inference MCP hosting?** (G1, C4)
- **A. stdio `uv run --locked` server in glm53-space's slot**, targets `claude` (+ Cursor via the
  safe-default attach); tools `models_list / chat / probe / budget_status`; one model round, no
  loop, no shell/file tools. *Why:* 0 idle RAM, server count stays 42, no new port, reuses the
  launcher that already resolves `${HUGGINGFACE_TOKEN}`. Cost: ~40-80 MB per live session.
- B. Native Streamable-HTTP `inference-hub` on `:8901` under `mcp-http-host` supervision, with an
  in-process `/v1` face (lens 07): concurrency, restart-transparent for Cursor, but one resident
  process (~60-150 MB) and a new port on a 31.6 GB box at ~1.8 GB free. Owner may promote A->B
  later; the tool surface is identical. C. No MCP, wrappers only (lens 02): leaves Claude, Cursor,
  Agy, Gemini with no door.

**D4. Materializer scope, first wave?** (G3, C6-C8)
- **A. Goose (file-set, safest) -> Grok (`[endpoints]` collapses 36 blocks; gated on `:8317`
  `/v1/models`) -> OpenCode -> Aider (+wrappers) -> Fabric -> Codex LAST** (never `chat`, smoke +
  rollback). Dry-run + routing report by default; `--write` per runtime. Cost: 0 RAM; 6 renderers
  sharing the MCP-merge idioms.
- B. All six at once. Cost: one bad Codex block bricks the primary rail (#41816).
- C. None - publish zero-code recipes only (lens 01). Cost: four hand-copied tables keep drifting.

**D5. Eval gate before ANY build wave?** (G6, C10)
- **A. Green = (1) M0 probe receipt committed (T0-12), (2) glm53-space archived (T0-1), (3) T1
  contract suite on the stdlib fake OpenAI server at pass@1 = 1.00 in CI (second job of
  `routing-benchmark.yml`), (4) validator red-proof tests pass; capability evals pass@3 >= 0.90,
  reliability pass^k n >= 4 before any renderer `--write`.** *Why:* both known misses were
  bridge-shaped; the registry must never claim an unmeasured capability. Cost: ~600 lines
  pytest + fakes; $0 (fakes); T3 hosted runs weekly under the daily caps.
- B. Probe receipt only. C. No gate (rejected: L7 and #41816).

**D6. OpenAI `/v1` face for Fabric/Goose/Aider/OpenCode?** (SK21, D3)
- **A. Drop `openai_proxy.py`; point consumers straight at upstreams via the renderers.** *Why:*
  the HF router already speaks `/v1` with `:provider` suffixes; every consumer supports
  `env_key`; the proxy is a process + a hop with no capability. Cost: -1 process.
- B. Keep a `/v1` face inside the hub (only meaningful with D3-B).

**D7. Split `HUGGINGFACE_TOKEN`?** (G8, C16)
- **A. ADD a fine-grained token with only "Make calls to Inference Providers" as
  `HUGGINGFACE_TOKEN_INFERENCE`; the inference MCP declares only that name; Hub MCP keeps the
  current token. Never revoke (L6).** Cost: 1 owner click; 2 files (`local.json` name,
  registry entry). Note: `.gitleaks.toml` says the committed private-env tokens "SHOULD be
  rotated" - that escalation is yours, not this hunt's.
- B. Keep one token. Cost: inference path (strangers' Spaces, public logs) carries write scope.

**D8. OpenRouter key scoping + Guardrails?** (TL3, C17)
- **A. 2-3 labelled keys (`or-codex-sidecar`, `or-cli-grunt`, optional `or-ide-opencode`), each
  with daily `limit_reset`; one Guardrail: provider + model allowlist, `data_collection: deny`,
  Secrets preset, `limit_usd` (0 = instant no-rotation kill).** *Why:* the lock says
  "spend-capped" but nothing proves `limit` is set; keys are the only lawful budget proxy (L2).
  Cost: owner clicks only; 3 name-only pointers.
- B. One key + Guardrail. C. Status quo (account was overdrawn on 08-27).

**D9. `codex-cursor` / `claude-cursor` wrappers?** (G4, V32)
- **A. Probe auth2api for `/v1/responses` and `/v1/messages` (T0-12); mark a wrapper `broken`
  in the registry routing report if its wire fails; do not render a Codex block for `:8317`
  until the probe passes.** Cost: two `curl`s.
- B. Assume they work. Cost: silent dead wrappers; possible bricked Codex.

**D10. Local inference posture, now that the box HAS an RTX 4050 (6 GB)?** (V17, C13)
- **A. Ollama stays the local endpoint; user env `OLLAMA_MAX_LOADED_MODELS=1`, short
  `OLLAMA_KEEP_ALIVE`; models <= 7B Q4 (weights <= ~5 GB VRAM, `qwen2.5:7b` proven); LM Studio
  JIT + auto-evict ON; registry rows carry `resource.ramBytes`; local-bind check `127.0.0.1`
  only.** Cost: -RAM (default allows 3 co-resident models); cold-load seconds on first call.
- B. LM Studio primary. C. No local models (loses the free T2 eval lane and the PACE C rung).

**D11. Routing policy + PACE data - where?** (G9, PU3, C21)
- **A. `.agents/routing-policy.json` (names only, closed schema, provenance in `.provenance/`)
  with a `pace:` block per task class (P/A/C/E, each rung a different means, E = handoff via
  `:8765` + `:8812`), read by wrappers with a loud fallback; autoresearch loop later.** Cost: 0
  RAM; adopt-later after D5.
- B. Prose in the skill only. Cost: routing stays unmeasurable.

**D12. Meta loop scheduling?** (G10, C15)
- **A. Daily `catalog_sync.py` as a Scheduled Task (`register-tasks.ps1` style, mutex +
  IgnoreNew) + probe ladder L0-L5 as an `all` mode of `hooks/mcp-liveness`; capability score in
  a sidecar; retire is always human write-back.** Cost: 0 resident RAM; ~3 scripts.
- B. SessionStart-only. C. None (registry `lastSync` already 11 weeks stale).

**D13. `codex mcp-server` deprecated upstream 2026-08-24 - response?** (T0-3, V28)
- **A. Doc note now in CLAUDE.md / AGENTS.md / multi-ai-mingle; keep the mount (L7); plan the
  next fan-out shape (ACP workers / app-server client) with the `hma` adapter (PU1) later.**
  Cost: 3 doc edits.
- B. Migrate now to `codex-plugin-cc` slash commands (loses autonomous fan-out). C. Ignore.

**Order of execution if all A:** T0-1, T0-12, D7/D8 clicks -> WU-1..3 (registry, fakes, eval gate)
-> D5 green -> WU-4/5 (MCP + tombstone) -> WU-6..8 (renderers, Codex last) -> WU-9+ (meta loop,
PACE, `hma`). Details: BUILD-WAVE-PROPOSAL.md.
