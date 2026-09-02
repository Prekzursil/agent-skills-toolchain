---
name: windows-virtualization-conflict-triage
description: Use when Hyper-V, VBS, VMware Workstation, vmware-vmx, vmrun, Docker, or WSL conflict on a Windows host and you need a safe diagnosis before changing host virtualization settings.
---

# Windows Virtualization Conflict Triage

## Overview

Diagnose virtualization conflicts from the host outward. Verify whether Hyper-V or VBS is active, classify the VMware failure mode, and only then decide between coexistence, import fallback, or host reconfiguration.

## Reference Map

- Read [references/conflict-map.md](references/conflict-map.md) to classify the host stack.
- Read [references/fallback-matrix.md](references/fallback-matrix.md) for OVA, raw-disk, and host-change fallback choices.

## Required Discovery

1. Determine whether Hyper-V or VBS is active.
2. Capture the exact VMware failure mode: import failure, `vmware-vmx` crash, guest-tools issue, or `vmrun` guest-auth issue.
3. Separate host-level launch failure from guest-level boot failure.
4. Decide whether an OVA fallback or staged import is sufficient before touching host settings.

## Preferred Flow

1. Read host virtualization status.
2. Reproduce the VMware failure with logs.
3. Check whether a different import path avoids the failure.
4. Treat host setting changes as a deliberate maintenance window, not an inline experiment.

## Stop Rules

- Do not disable Hyper-V or VBS without capturing current host state and rollback steps.
- Do not treat `vmrun` guest-auth failure as proof that the guest never booted.
- Do not keep iterating on raw VMX edits when an OVA path is cleaner.

## Common Mistakes

- Mixing host and guest failures into one diagnosis.
- Forgetting that Docker Desktop and WSL also depend on the host virtualization stack.
