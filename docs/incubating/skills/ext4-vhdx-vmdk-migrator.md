---
title: ext4-vhdx-vmdk-migrator
type: note
permalink: dqverify-repo-20261013/docs/incubating/skills/ext4-vhdx-vmdk-migrator
---

# ext4-vhdx-vmdk-migrator

## Purpose

Potential future skill for workflows that move Linux filesystems across WSL VHDX, VirtualBox VDI, and VMware VMDK while preserving rollback.

## Why this is not a live skill yet

- The trigger is real, but the workflow needs more repeated pressure-tested evidence before promotion.
- The current first wave already covers the higher-frequency incidents more directly.

## Likely scope

- move Linux filesystems across WSL VHDX, VirtualBox VDI, and VMware VMDK while preserving rollback.
- define stop rules and evidence requirements for the workflow
- identify whether the value is mostly references, scripts, or both

## Planned resources

- one concise reference on discovery and guardrails
- one workflow checklist or scoring rubric
- scripts only after a repeated deterministic task is proven