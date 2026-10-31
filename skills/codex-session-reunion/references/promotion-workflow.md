---
title: promotion-workflow
type: note
permalink: dqverify-repo-20261013/skills/codex-session-reunion/references/promotion-workflow
---

# Promotion Workflow

## Read-only phase

Run inventory against every reachable root first. Record the canonical destination and the date of the scan.

## Comparison phase

Compare duplicates by rollout filename. Record line count, size, and parse status for every candidate.

## Promotion phase

Promote only the winning copy. If the target already exists and loses, archive it rather than deleting it in place.

## Verification phase

Recount the canonical tree and spot-check promoted sessions before declaring the reunion finished.