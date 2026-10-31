# debt-burndown-orchestrator

## Purpose

Potential future skill for analyzer backlog reduction in small, governed batches.

## Why this is not a live skill yet

- The live architecture skill already defines the debt burn-down lane.
- A dedicated orchestration skill should wait until the batching model, rule allowlists, and reviewer-only areas are stable across repeated use.

## Likely scope

- batch by tool, rule family, language, and directory
- maintain zero-touch allowlists and reviewer-only denylists
- define PR size caps and open-PR concurrency caps
- separate governance changes from code cleanup

## Planned resources

- sample batching matrix
- rule classification template
- examples of machine-generated evidence for issue reduction
