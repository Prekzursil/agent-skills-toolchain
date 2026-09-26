---
name: Operator-Trust Capability-Awareness Pattern
description: Every editor action surfaces its catalog status (LIVE/PHASE 2 PENDING/LIVE
  ONLY) so operators never confuse "bridge call succeeded" with "engine state changed".
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-operator-trust-pattern
---

The SWFOC editor's bridge has a load-bearing distinction: a Lua call can succeed over the named pipe (return "OK") while having zero engine effect (Phase-1-mirror only, no IDA pin yet). Operators clicking "Spawn unit" used to see "1/1 OK" and reasonably assume the unit spawned — it didn't. The capability-awareness pattern (built across iter 54-63) closes this gap.

**The pattern**: every operator-facing action exposes a `CapabilityAwareAction` (in `SwfocTrainer.Core.Diagnostics`) with:
- Helper-name list keyed against `CapabilityStatusCatalog`
- Auto-derived `Badge` (`"LIVE"` / `"PHASE 2 PENDING"` / `"LIVE ONLY"` / `"MIXED (m/n LIVE)"` / `"UNAVAILABLE"`)
- Auto-derived `Note` (catalog reason — e.g. `"BLOCKED-NO-RVA — AI scheduler"`)
- `Tooltip` composing `Name · Badge · Note` for one-shot XAML binding
- `IsAllLive` / `IsMixed` flags

**Multi-resolution visibility**:
1. **Per-button** — every badge `TextBlock` shows the status; hovering shows the tooltip
2. **Per-tab** — `HasPhase2PendingAction` + `Phase2PendingWarning` drive an amber banner listing every non-LIVE button by name
3. **Editor-wide** — bottom status bar shows `CapabilitySurfaceReport.SurfaceRollup` (`"Capability: 52 LIVE / 37 PHASE 2 / 3 LIVE ONLY · 94 actions · 59% engine-effective"`)
4. **Reports** — two markdown files in `knowledge-base/`: `capability_status_*.md` (keyed by helper name) + `capability_surface_*.md` (keyed by tab+button)

**Why:** Operators were getting burned by the LIVE-vs-mirror distinction; without per-button visibility they had to memorize which actions had engine effect. The user's overlay design explicitly asked for *"logical, handy, useful, intuitive"* feedback, and silent-success was the opposite of that.

**How to apply:** When adding a new operator-facing button to a V2 tab:
1. In the VM, add a `public CapabilityAwareAction MyAction { get; }` initialized with the SWFOC_X helper names the action invokes.
2. Add the action to the tab's `AllActions` property (every bridge-using V2 tab has this — it powers the editor-wide roll-up).
3. In XAML, render a stacked badge `TextBlock` below the button with `Text="{Binding MyAction.Badge}"` and `ToolTip="{Binding MyAction.Tooltip}"`.
4. The tab-level banner + editor-wide roll-up update automatically.

**Do NOT** add raw "REPLAY MIRROR ONLY" hand-written strings to button tooltips. The catalog is the source-of-truth — the badge + note flow from there. Hand-written status text drifts as the catalog updates.

**Forward-orphan check** at `tests/SwfocTrainer.Tests/App/V2/ViewModels/CapabilitySurfaceReportIntegrationTests.cs` walks every VM and asserts `AllActions` is non-empty — adding a tab without wiring `AllActions` fails CI. The drift-protection test on the same fixture asserts the on-disk surface report matches generated output.

**Coverage**: 21/21 bridge-using V2 tabs as of iter 60. Adoption count is part of the editor's release-readiness story.