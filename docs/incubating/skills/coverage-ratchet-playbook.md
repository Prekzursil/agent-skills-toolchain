---
title: coverage-ratchet-playbook
type: note
permalink: dqverify-repo-20261013/docs/incubating/skills/coverage-ratchet-playbook
---

# coverage-ratchet-playbook

## Purpose

Potential future skill for designing and tuning coverage-only improvement loops without allowing broad refactors to hide inside the lane.

## Why this is not a live skill yet

- The first live skill already covers coverage ratchets as one lane in a larger architecture.
- A dedicated skill needs more repeated evidence for thresholds, scope caps, and provider-specific coverage workflows.

## Likely scope

- choose diff coverage versus project coverage rules
- size ratchets by PR size or changed executable lines
- set stop rules based on covered-line gain
- reject fake wins such as exclusions or threshold changes

## Planned resources

- coverage heuristics reference
- provider comparison notes for Codacy, Codecov, and custom coverage scripts
- prompt templates for test-only and seam-limited changes