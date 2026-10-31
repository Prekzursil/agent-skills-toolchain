# wsl-control-plane-repair

## Purpose

Potential future skill for workflows that repair `wslservice`, broken `wsl -t`, mirrored networking drift, and reboot-threshold control-plane failures.

## Why this is not a live skill yet

- The trigger is real, but the workflow needs more repeated pressure-tested evidence before promotion.
- The current first wave already covers the higher-frequency incidents more directly.

## Likely scope

- repair `wslservice`, broken `wsl -t`, mirrored networking drift, and reboot-threshold control-plane failures.
- define stop rules and evidence requirements for the workflow
- identify whether the value is mostly references, scripts, or both

## Planned resources

- one concise reference on discovery and guardrails
- one workflow checklist or scoring rubric
- scripts only after a repeated deterministic task is proven
