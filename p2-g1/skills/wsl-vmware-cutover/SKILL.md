---
name: wsl-vmware-cutover
description: Use when moving Linux workloads from WSL into VMware and you need D-first staging, cold backups, rollback checkpoints, and a clear rule that Codex runtime ownership stays on Windows unless explicitly changed.
---

# WSL VMware Cutover

## Overview

Move Linux workloads from WSL into a VMware guest without improvising the order of operations. Stage to a roomy drive first, preserve rollback assets, and keep Codex runtime ownership decisions explicit.

## Reference Map

- Read [references/cutover-checklist.md](references/cutover-checklist.md) for the execution order.
- Read [references/rollback-and-ownership.md](references/rollback-and-ownership.md) for backup policy and Codex ownership boundaries.

## Required Discovery

1. Measure free space on `C:` and the intended staging volume.
2. Record the source WSL distro, target VMware VM, and current Codex canonical store.
3. Decide whether the VMware import path is raw disk conversion, OVA, or guest-side restore.
4. Confirm what is excluded from Linux-home migration, especially Codex stores and caches.

## Execution Order

1. Back up WSL and VM sources.
2. Move large source artifacts off `C:` before expanding or importing disks.
3. Prepare the VMware target and validate bootability.
4. Restore the Linux home into the VMware guest or mounted guest disk.
5. Verify shell, SSH, Git identity, and representative workloads.
6. Only after validation, decide whether to retire or archive the WSL source.

## Stop Rules

- Do not migrate Codex runtime ownership into Linux unless that is an explicit goal.
- Do not delete the source VM or WSL tree before a validated guest boot.
- Do not let low `C:` free space ride while generating new VM artifacts.

## Common Mistakes

- Treating VMware import success as guest validation.
- Copying WSL homes into an undersized guest disk and fixing growth later under pressure.
- Forgetting that VS Code host routing and Codex store ownership are separate decisions.
