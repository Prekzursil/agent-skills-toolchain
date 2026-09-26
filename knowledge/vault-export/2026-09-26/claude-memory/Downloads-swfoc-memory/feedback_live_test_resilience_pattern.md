---
name: Live test resilience — defense-in-depth against locator/attach mismatch
description: When a test uses ProcessLocator + RuntimeAdapter.AttachAsync on the real
  game, layer 4 defenses (inline catch → shared helper → locator regression test →
  audit) so the SwfocExtender.Host sidecar flake can't recur
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-live-test-resilience-pattern
---

When a test uses `ProcessLocator` + `RuntimeAdapter.AttachAsync` to attach
to the live game, the locator and adapter have **different opinions**
about what counts as a SWFOC process:

- **Locator's `FindBestMatchAsync(ExeTarget.Swfoc)`** uses heuristics on
  process name, path, and command-line tokens. Can return non-null for
  sidecar processes (e.g. `SwfocExtender.Host`) that happen to look
  SWFOC-related but aren't the actual game executable.
- **Adapter's `AttachAsync(profileId)`** runs `SelectProcessForProfileAsync`
  with stricter profile-aware matching. Throws
  `InvalidOperationException` with `ATTACH_NO_PROCESS` if the locator's
  candidate doesn't pass the profile filter.

A naive Live test that does `if (running is null) skip; else attach()`
fails when the locator says "found something" but the adapter says
"actually no" — the test FAILS instead of SKIPPING.

**Why**: this exact flake hit `LiveTacticalToggleWorkflowTests` (iter 120)
and was masked across the suite for an unknown number of runs. Even
after fixing the immediate test, the same pattern existed in 5 other
Live tests (iter 121's preemptive refactor) and 1 non-Live test
(`RuntimeAttachSmokeTests`, iter 123 caught after iter 122's audit).

**How to apply** (when writing or reviewing tests that touch
`ProcessLocator` + `AttachAsync`):

1. **Inline defensive catch**: convert `ATTACH_NO_PROCESS` into a SKIP
   with the same semantic as the initial locator-null check. NOT a FAIL.
2. **Use the shared helper**: `LiveSkip.AttachOrSkipAsync(runtime,
   profileId, output)` in `tests/SwfocTrainer.Tests/Common/LiveSkip.cs`.
   Centralizes the pattern across all 6 `Profiles/Live*Tests.cs`.
3. **Pin the locator at the source**: `Iter122ProcessLocatorSidecarTests.cs`
   pins `ProcessLocator.GetProcessDetection`'s output on synthetic
   `(processName, processPath, commandLine)` tuples. If anyone loosens
   the heuristics, this fires immediately with a clear assertion.
4. **Audit by running the broader suite**: iter 122's verification run
   exposed iter 123's missing test (`RuntimeAttachSmokeTests`). The
   regression guard wasn't just defensive theater — it actively
   surfaced gaps in the previous fix's coverage.

**Anti-pattern to avoid**: do NOT just patch each Live test individually
when it fails. That yields N copies of the same try/catch drifting over
time. Extract the helper, apply across siblings, and add a
locator-level regression test.

**Files involved (iter 120-123 batch)**:

- `tests/SwfocTrainer.Tests/Common/LiveSkip.cs` — `AttachOrSkipAsync` helper
- `tests/SwfocTrainer.Tests/Profiles/Live*Tests.cs` (6 files) — refactored
- `tests/SwfocTrainer.Tests/Profiles/RuntimeAttachSmokeTests.cs` —
  inline fix (no `ITestOutputHelper` dependency)
- `tests/SwfocTrainer.Tests/Profiles/LivePromotedActionMatrixTests.cs` —
  extended existing `ATTACH_PROFILE_MISMATCH` catch to also cover
  `ATTACH_NO_PROCESS`
- `tests/SwfocTrainer.Tests/Regression/Iter122ProcessLocatorSidecarTests.cs`
  — locator-level regression guard
- `src/SwfocTrainer.Runtime/Services/ProcessLocator.cs` —
  `GetProcessDetection` + `ProcessDetection` exposed `internal` for tests