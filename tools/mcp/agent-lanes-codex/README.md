# Agent Lanes Codex

`tools/mcp/agent-lanes-codex/` stores the Codex-side orchestration contract plus the local override snapshots required to keep the Windows-first consultation lane reproducible.

## Provenance
- **Self-made lane contract**: `codex_consult` orchestration profiles and structured result schema.
- **Modified local fork**: the copied files in `local-overrides/` reflect the current workstation runtime adjustments.
- **Curated upstream inputs**: PromptBridge Desktop runtime code and docs that the local fork derives from.

## Why this matters
These files preserve the exact local behavior that was required to stabilize the workstation:
- keep `C:\Users\Prekzursil\.codex` as canonical
- disable automatic PromptBridge Desktop spawning by default
- preserve fallback-to-Lane-A behavior when the desktop sidecar is unavailable
- document why the codex-orchestrator bootstrap may report `config` drift while Codex remains live and locked

## Included local overrides
- `local-overrides/bootstrap.mjs`: generates the managed Codex MCP block with canonical Windows paths and `PROMPTBRIDGE_DESKTOP_AUTOSTART=false`
- `local-overrides/codex-orchestration.mjs`: preserves structured fallback behavior (`fallback_to_lane_a = true`) when PromptBridge curation is unavailable

## Validation notes
- `npm run orchestration:status -- --json` sees the managed Codex/PromptBridge servers and their autostart-disabled env
- full `orchestration:update` was blocked live by `EPERM` rename because the runtime directory was in use; the local overrides are therefore the source of truth until a cold update can run
