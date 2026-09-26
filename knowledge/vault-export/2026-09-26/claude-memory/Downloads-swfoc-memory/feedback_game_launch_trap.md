---
name: SWFOC test sweep can silently launch the real game
description: RuntimeWave11CoverageTests.GameLaunchService_LaunchAsync_NoGameRoot_ReturnsFailure
  was a test-sweep footgun that actually started StarWarsG on dev machines with the
  game installed
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-game-launch-trap
---

During an autonomous run of `tools/run_editor_tests_v2.ps1` on 2026-04-10, the SWFOC game actually launched mid-sweep. Root cause: `tests/SwfocTrainer.Tests/Runtime/RuntimeWave11CoverageTests.cs :: GameLaunchService_LaunchAsync_NoGameRoot_ReturnsFailure` constructed a real `GameLaunchService()` and called `LaunchAsync()` expecting "CI machines won't find a game root" — but on a dev machine with `D:\SteamLibrary\steamapps\common\Star Wars Empire at War\corruption\swfoc.exe` actually installed, `GameLaunchService.ResolveRoot()` falls through to `DefaultRoots.FirstOrDefault(Directory.Exists)` and `StartProcess` fires a real `Process.Start(swfoc.exe)`. The test then silently passed because it only asserted `if (!result.Succeeded)`.

**Fix applied 2026-04-10**: the test now sets `SWFOC_GAME_ROOT` to an empty temp directory before calling `LaunchAsync`, so it hits `exe_missing` without reaching `Process.Start`. The sibling tests in `GameLaunchServiceTests.cs` already used this pattern correctly.

**Why:** Any test that instantiates `GameLaunchService` directly (vs. `StubGameLaunchService`) without setting `SWFOC_GAME_ROOT` to a sandbox directory risks launching the real game on developer workstations. `GameLaunchService.ResolveRoot` silently falls through to `DefaultRoots` hard-coded at `D:\SteamLibrary\...` and `C:\Program Files (x86)\Steam\...`.

**How to apply:**
1. Before running a full editor test sweep on a machine with SWFOC installed, close any running game instance first.
2. When writing new tests that touch `GameLaunchService`, prefer `StubGameLaunchService` (`tests/SwfocTrainer.Tests/Core/ContractsAndModelsCoverageTests.cs:15` has the pattern). If you MUST construct the real service, set `SWFOC_GAME_ROOT` to an empty `Path.GetTempPath()` subdirectory in a try/finally.
3. If an autonomous agent sees SWFOC start unexpectedly during a test run, suspect `RuntimeWave*CoverageTests` or any test that calls `new GameLaunchService()` without an env override. Grep: `grep -rn "new GameLaunchService()" tests/`.
4. `GameLaunchService.TerminateKnownTargets()` kills `sweaw / swfoc / StarWarsG` processes — that's separate from the launch bug but worth knowing during cleanup.