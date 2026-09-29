---
description: Attempt/pass ElevenLabs Professional Voice Cloning verification on the agent Chrome (attempt-conserving runbook)
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# /pvc-verify — PVC verification attempt (attempt-conserving)

Reads the authoritative runbook first, then executes it phase by phase:

1. Read `D:\Research\tools\rvc-realtime-voice-changer\docs\PVC-VERIFICATION-RUNBOOK_2026-09-22.md` (incl. the EXECUTION ADDENDUM — counter state, proven/unknown steps).
2. Gate: free RAM >= 4 GB (else STOP — a starved Chrome wedges and risks garbage submissions); live attempt-counter read via REST (count must be < max).
3. Recon (zero submissions): script capture with >= 2 agreeing signals; abort-cost measurement (counter before/after).
4. If and only if recon is clean: synth the exact script via the PRO voice (`scripts/pvc_synth.py`), stage via the virtual-mic patch (pattern proven in `scripts/pvc_mic_dryrun.py`), TEXT GATE, single read, Stop, observe post-Stop UI, API-verify `is_allowed_to_fine_tune`.
5. NEVER submit text that does not exactly match the presented script. NEVER retry-loop during cooldown. Record every state transition to `out/pvc_run_state.json`.

Skill context: `voice-cloning-sota` (§6 = the PVC automation pattern; §6.6 = attempt conservation).
