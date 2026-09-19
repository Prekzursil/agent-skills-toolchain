# ZCode runtime lens — 2026-09-04 (disk-verified)

Provenance: disk-verified. Bodies under `memories/` were not ingested.

## Surface counts
- Live `mcp.servers`: **20**. Disabled on disk: apify, burp, github, kaggle (**4**). Implied-enabled: **16**.
- Registry `targets` contain `zcode`: **16**. Registry `enabled:true` among those: **14** (kaggle+burp registry-off).
- `x_zcode.enabled:false`: **2** (apify, github) — globally on, ZCode-off.
- Arithmetic: 16 registry + 4 leftovers = 20. Live-enabled = 12 registry-on (14 minus apify/github) + 4 leftovers = 16.
- z.ai native (`zai-devpack`): **4**, all also in the registry (not unmanaged).
- `plugins.enabledPlugins` (same file, not MCP): **9**.
- memories: **8** project dirs, **36** `.md` files (27 default + 9 phenibut).

## Classification
**A. Registry-managed (16):** agent-mail, apify, basic-memory, bedrock-claude, biomni-hub, burp, deepwiki, exa, github, kaggle, openaiDeveloperDocs, scholarly-access, web-reader, web-search-prime, zai-vision, zread.

**B. z.ai native (4; subset of A):** web-reader HTTP `https://api.z.ai/api/mcp/web_reader/mcp`; web-search-prime HTTP `…/web_search_prime/mcp`; zread HTTP `…/zread/mcp`; zai-vision stdio `cmd /c npx -y z_ai/mcp-server@latest`. Inventory `zcode_native_mcp: ["zread"]` is incomplete vs live **4**.

**C. Local leftovers (absent from `agents.json`; merge preserves):** node_repl (Codex `cua_node` `node_repl.exe`), cua_repl (`ChatGPT.exe` WindowsApps), mcphub (`http://127.0.0.1:24680/sse`, `${MCPHUB_TOKEN}` template). Extra vs merge docstring trio: **consult-offsec** (`D:\MCP\consult-offsec\server.py`) — live-only.

## `x_zcode.enabled` pattern
Merge (`merge_generated_zcode_mcp.py:75-79`): `enabled = x_zcode.get("enabled", server.get("enabled", True))`. False keeps the entry with `enabled:false` (does not drop). True omits the key (runtime default-on). Only apify (`agents.json:63-65`) and github (`:516-518`) have an `x_zcode` object. kaggle/burp disable via registry `enabled:false` (`:1452`, `:1484`) and still render live. Live knobs `tool_timeout_sec`/`env_vars` survive re-render (kaggle).

## second-config
**no.** One MCP map: `C:\Users\Prekzursil\.zcode\cli\config.json`. `.zcode\v2\config.json` exists; grep found no `mcp`/`servers` keys. Plugins sit in the same cli file.

## memory path vs basic-memory
`C:\Users\Prekzursil\.zcode\cli\memories` — **yes, a second semantic store**. G-81 (`memory-contract.md:67-70`) makes basic-memory the sole writer (`http://127.0.0.1:18765/mcp`). ZCode still mounts BM HTTP (`config.json:104-106`) and a native per-project markdown tree. `memory-map.md` has no zcode/memories hit. Inventory `ZCODE-SECOND-MEMORY` (P1) stands.

Project dirs: ast-integrate-4f0ac333d5779c3c, auth2api-6b23eb7f8b54030d, csie-foundation-wt-3c0455cbf3a3b0f9, default-a18792a756ad3f38, github-4bd38543de91627c, phenibut-1d4b47731d5f7c69, prekzursil-e5f7a9a8c99ba29a, primariro-957163d7d26ff938 (six empty `memory/`).

default names: agent-mail-mingle-transport.md, agents-md-tampering-incident.md, basic-memory-edit-append-dataloss.md, basic-memory-only-consolidation.md, bedrock-claude-mcp.md, bm-capture-pipeline.md, consult-offsec-mcp.md, cyberstrike-loose-posture.md, devtu-devfleet-tooling.md, fabric-session-distillery.md, fabric-usage-recall.md, grill-workflow-contract.md, harness-ssot-topology.md, hermes-runtime.md, huihui-cyberstrike-inference.md, mcphub-fleet-architecture.md, MEMORY.md, mimosa-guard-contract.md, modal-qwythos-deployment.md, owner-identity-bolt-question.md, owner-workflow-preferences.md, runtime-wiring-map.md, space-relocation-2026-09-03.md, uncensored-models-council-verdict.md, zai-devpack-mcps.md, zcode-custom-providers.md, zcode-mcp-config-schema.md.

phenibut names: a2d-science-state.md, codex-fleet-rules.md, grant-applications.md, jaguar-scf-discipline.md, MEMORY.md, monitor-eta-discipline.md, schrodinger-scaleway-ops.md, toolchain-prs-status.md, user-profile.md.

## vs 2026-08-27
Scorecard table (`CROSS-RUNTIME-SCORECARD_2026-08-27.md:9-16`) has **no ZCode row**. No prior live MCP count to regress against. Sync then (`:27`): claude+codex+cursor only. Now `VALID_TARGETS` includes zcode (`mcp_control_plane.py:15`) and `sync_shared_state.ps1:188-189` runs the zcode merge — coverage **gain**, not a count regression. Unmanaged: consult-offsec live-only; memories parallel to BM.

## file:line
- live map: `C:\Users\Prekzursil\.zcode\cli\config.json:16-156` (natives 112-135; leftovers 37-56 node_repl, 87-91 mcphub, 93-95 cua_repl, 146-155 consult-offsec; BM 104-106; agent-mail 96-98)
- leftovers policy: `merge_generated_zcode_mcp.py:14-16,127-128`
- x_zcode merge: `merge_generated_zcode_mcp.py:11,75-79`
- x_zcode SSOT: `agents.json:63-65` apify, `:516-518` github
- z.ai SSOT: `agents.json:1502-1618`
- kaggle/burp registry-off: `agents.json:1446-1500`
- BM/agent-mail target zcode: `agents.json:760-771`, `:1189-1200`
- VALID_TARGETS: `mcp_control_plane.py:15`
- sync: `sync_shared_state.ps1:66,188-189`
- G-81: `memory-contract.md:67-70`
- scorecard gap: `CROSS-RUNTIME-SCORECARD_2026-08-27.md:9-16,27`
- inventory: `inventory.md:15,37,74`; `inventory.json:151-168,249-263,593-623,937-940`

UNIT-COMPLETE: runtime-zcode
