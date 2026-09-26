---
title: Reframe v1.3 Design-Gate-2 PASSED + formal-plan handoff
type: report
permalink: main/projects/reframe/reframe-v1.3-design-gate-2-passed-formal-plan-handoff
tags:
- reframe
- v1.3
- design-gate
- plan-review
- decision-log
---

# Reframe v1.3 Design-Gate-2 = PASSED (2026-07-04)

readyForPlanning=TRUE; 5/5 APPROVE_WITH_CHANGES; 0 blocks; 0 open user questions. Plan v2:
scratchpad/reframe-v1.3-program-plan-v2.md. Sequencing SOUND (Architect only asks SPLIT G-5, not reorder).
Extends [[reframe-v1-3-program-plan-grill-converged]].

## 8 residual MUST-fixes to fold into formal plan (carry into Plan Review Gate)
1. PROVENANCE archaeology FIRST (blocking): branch package.json=1.1.0 vs released 1.2.0 -> diff released-1.2.0
   tag vs fix/reframe-hardening + recover missing 1.2.0 work before building v1.3.
2. Widen blocking clean-machine acceptance to EVERY table row + per-WS smoke (Director/key-reveal/usage need
   real key or warmed local LLM).
3. Capability matrix: Minimum always-on YuNet/ASD tracker = 'no silent center-crop' WITHOUT ViNet-S (or loud
   notice); reconcile with existing ReadinessRollup/ReadinessBadge/readiness.summary.
4. Split G-5: manifest-registration (CRITICAL, needs sha/final bytes) vs host+verify+loader (parallel); anchor
   sha to ORIGINAL author distribution hash.
5. ensure-callback = llama slot ONLY (provider=='local'), not Ollama/LM-Studio; readiness probe RAISES on
   timeout; opaque ensure() keeps provider.py runner-free; update firstRunGate.test.ts semantic assertion.
6. verify-before-LOAD real: TransNetV2 no per-file sha + pickle backend -> require sha/load-time gate;
   safetensors MANDATORY, torch.load pickle FORBIDDEN.
7. Release-blocking: hashed lockfile (--require-hashes --only-binary --no-deps incl cu124 torch); DPAPI raw key
   never logged in sidecar RPC; realpath data-root check at settings_store.default_config_dir; revealed key
   never in React state/telemetry.
8. Name Director empty-state current-video SOURCE (prop-less DirectorPanel) else Choose-a-video wires to
   nothing; package.json has NO productName (ADD); electron-builder artifactName ${name}=media-studio; audit
   'no user-facing media-studio string'.

## Next: formal plan (WU decomposition, folds the 8) -> Plan Review Gate (3 adversarial) -> user picks
execution method (metaswarm-orchestrated / subagent-driven / parallel-session per CLAUDE.md) -> BUILD.
No open user decisions. Quality>cost; TDD+100% coverage gate; no silent fallbacks.