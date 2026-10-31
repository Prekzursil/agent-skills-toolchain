---
title: progress-and-stall-handling
type: note
permalink: dqverify-repo-20261013/skills/long-copy-orchestrator/references/progress-and-stall-handling
---

# Progress And Stall Handling

Sample the artifact that actually grows: archive file, destination tree, or transfer report.

## Quiet is not stuck

A transfer can be healthy while CPU is low and stdout is silent. Treat it as stuck only when the destination artifact, process CPU time, and byte counters all stop moving across multiple samples.

## Resume policy

Prefer resumable mechanisms for multi-hour work. If the current mechanism is not resumable, protect the partial artifact before stopping it.