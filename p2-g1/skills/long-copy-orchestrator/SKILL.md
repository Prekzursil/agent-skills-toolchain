---
name: long-copy-orchestrator
description: Use when moving large trees between Windows, WSL, VMs, or mounted disks and you need to choose rsync, tar, robocopy, or offline copy, track progress, detect stalls, and resume safely.
---

# Long Copy Orchestrator

## Overview

Choose the copy mechanism that matches the topology instead of defaulting to the first familiar command. Bias toward resumable, observable transfers with explicit exclusions and stall detection.

## Reference Map

- Read [references/mechanism-selection.md](references/mechanism-selection.md) to choose between `rsync`, tar, `robocopy`, and offline disk attachment.
- Read [references/progress-and-stall-handling.md](references/progress-and-stall-handling.md) to decide when a transfer is merely quiet versus truly stuck.
- Run [scripts/copy_strategy.py](scripts/copy_strategy.py) for mechanism recommendations and read-only file growth monitoring.

## Required Discovery

1. Identify source and target boundary: same host, cross-host, cross-filesystem, or offline-mounted disk.
2. Decide whether exclusions affect transfer cost on the source side or only the archive output.
3. Confirm whether resumability matters more than raw throughput.
4. Measure progress from the artifact that is actually growing.

## Preferred Mechanisms

- `rsync`: large directory trees where excludes and resumability matter.
- tar: bounded archive creation or transport where one file artifact is useful.
- `robocopy`: Windows-native directory copies where restartable mirror semantics are needed.
- offline attach: VHDX, VMDK, or ext4 work where booting the guest is riskier than editing the mounted disk.

## Stop Rules

- Do not restart a long transfer just to add progress output unless the current run is proven stuck.
- Do not assume tar exclusions save source-side traversal work.
- Do not run multiple heavy copy paths against the same backing disk without a reason.
- Stop and re-evaluate if throughput falls to zero across multiple sample windows.

## Output Contract

Return the selected mechanism, rationale, observed progress, exclusions, and the resume strategy if interruption is required.

## Common Mistakes

- Using tar where exclusion-aware directory copy is required.
- Measuring the wrong file or process when estimating progress.
- Mixing migration work and host-diagnostic work on the same disk at the same time.
