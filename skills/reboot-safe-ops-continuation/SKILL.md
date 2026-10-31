---
name: reboot-safe-ops-continuation
description: Use when a reboot is required in the middle of migration or repair work
  and you need exact pre-reboot state capture, staged-artifact inventory, and a resumable
  checklist for the next session.
permalink: dqverify-repo-20261013/skills/reboot-safe-ops-continuation/skill
---

# Reboot Safe Ops Continuation

## Overview

Treat a forced reboot as an operation boundary, not an interruption you can remember from context. Capture the exact machine state, staged artifacts, and next safe step before rebooting.

## Reference Map

- Read [references/pre-reboot-capture.md](references/pre-reboot-capture.md) for the minimum evidence set.
- Read [references/resume-checklist.md](references/resume-checklist.md) to structure the post-boot continuation.

## Required Discovery

1. Identify what operation is active and which artifacts are mid-flight.
2. Capture mounted disks, attached devices, temporary paths, and active sessions.
3. Record which steps are complete, partial, or blocked.
4. Preserve the exact next safe command rather than a vague narrative.

## Minimum Capture Set

- active source and target paths
- backup or export artifact locations
- mount or attachment state
- verification already completed
- outstanding blockers and next safe command

## Stop Rules

- Do not reboot without recording in-flight operations.
- Do not rely on memory for mounted-device numbering.
- Do not clean temporary paths before deciding whether they are needed after boot.

## Common Mistakes

- Writing a prose summary without concrete paths or commands.
- Forgetting which rollback assets were preserved.
- Re-deriving state after reboot and accidentally diverging from the safe resume path.