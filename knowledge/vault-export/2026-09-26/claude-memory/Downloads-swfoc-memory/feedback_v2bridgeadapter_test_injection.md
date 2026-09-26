---
name: V2BridgeAdapter Test Injection Pattern
description: To unit-test code that depends on BridgeActivityEntry timestamps or success
  state, use V2BridgeAdapter.RecordForTest — production calls go through SendRawAsync.
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-v2bridgeadapter-test-injection
---

When writing unit tests for `DiagnosticsTabViewModel` (or any code that consumes `V2BridgeAdapter.RecentCalls`) and you need to control the `Timestamp` or `Succeeded` field on activity entries, **do not** try to coerce the simulator into producing failures — it returns OK for both handled and unhandled commands. Instead, call the `internal` helper:

```csharp
var entry = new BridgeActivityEntry(
    Timestamp: DateTimeOffset.UtcNow.AddSeconds(-5),
    LuaCommand: "return SWFOC_X(1)",
    Succeeded: false,
    ResponseOrError: "ERR: bad call",
    DurationMs: 12);
adapter.RecordForTest(entry);
```

`RecordForTest` is wired in `V2BridgeAdapter.cs` and it:
- routes through the same `AppendToActivityRing` private helper as the production round-trip
- fires the `ActivityRecorded` event so subscribers (live UI) get the same callback they would on a real call
- respects the ring buffer cap (`RecentCallsCap`) just like the real path

Access works because `src/SwfocTrainer.App/Properties/AssemblyInfo.cs` already declares `[InternalsVisibleTo("SwfocTrainer.Tests")]`. No additional plumbing needed.

**Why:** introduced in iter 79 (2026-04-28) for the LastFailureSummary dismissal-logic tests. Tests need to control `Timestamp` so they can verify the pre-dismiss / post-dismiss / new-after-dismiss state transitions. The simulator can't produce failures, and even if it could, controlling the exact `Timestamp` would require time mocking. Direct entry construction + `RecordForTest` is cleaner than either alternative.

**How to apply:** any future test that needs to assert on `RecentCalls` shape, `LastFailureSummary` content, `BridgeActivityStats` rollup math, or `BridgeCommandSummary` aggregation — use this helper instead of trying to drive the simulator. The simulator is for end-to-end VM scenario tests where the wire format matters; `RecordForTest` is for unit tests where activity-log shape matters.