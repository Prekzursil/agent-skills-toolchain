# Program charter (scratch rev-earlier)

Prompt One option-universe / architecture-selection stand-in for BLD-0018.
Each capability is identified by cap_id and a stable mechanism fingerprint.
Labels may change later; mechanisms must not be treated as drops when they persist.

## Capabilities

### Widget persistence
- cap_id: CAP-KEEP
- mechanism: persist.widgets.sqlite
- label: Widget persistence

### Council Protocol Compiler
- cap_id: CAP-COUNCIL-COMPILER
- mechanism: council.protocol.compile
- label: Council Protocol Compiler

### Telemetry beacon
- cap_id: CAP-TELEMETRY-BEACON
- mechanism: telemetry.beacon.http
- label: Telemetry beacon

### Marketplace sync daemon
- cap_id: CAP-MARKETPLACE-SYNC
- mechanism: marketplace.plugin.sync
- label: Marketplace sync daemon

### UX live-preview pane
- cap_id: CAP-UX-PREVIEW
- mechanism: ux.preview.live-pane
- label: UX live-preview pane

### Remote auto-push
- cap_id: CAP-REMOTE-AUTO-PUSH
- mechanism: git.remote.auto-push
- label: Remote auto-push
