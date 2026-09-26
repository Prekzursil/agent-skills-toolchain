---
name: autonomous-testing-preference
description: User wants automated live testing without manual game restart/attach
  cycles
type: feedback
permalink: main/claude-memory/downloads-swfoc-memory/feedback-autonomous-testing
---

User does not want to manually close/relaunch the game for every DLL iteration. Build automated test harnesses instead.

**Why:** Manual deploy-restart-attach-test cycles are tedious and break flow. The user wants to be hands-off during testing.

**How to apply:** Create Python scripts that:
1. Kill the game process if running
2. Copy the new DLL to the game directory
3. Launch the game via Steam CLI (`start steam://rungameid/32470`)
4. Wait for StarWarsG.exe to appear and stabilize
5. Run pipe/shared-memory tests automatically
6. Report pass/fail without user intervention