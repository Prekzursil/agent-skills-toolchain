# RUNBOOK — n8n fleet from 10.130.x vantage (internal-only secret reuse)
**Lane-41 staged 2026-10-02 · GO-GATED — requires internal network position**

| Axis | Value |
|---|---|
| Target | n8n fleet editors + n8n-fp OIDC-Enterprise editor on 10.130.x subnet (SSOT: live-plaintext secret, internal-only) |
| Prior evidence | megawave: n8n-fleet secret live-plaintext but internal-only (10.130.x NEW subnet); fleet secrets reclassified = 114,419 unmasked Canadian driver licences (PII — ZERO value reads permitted) |
| Gating | owner GO **AND** authorized route to 10.130.x (operator-provided vantage; container has no route today) AND PII-read prohibition re-acknowledged |
| Budget | <=8 network actions, >=1.25 s pacing, single-attempt per (key,endpoint) |
| Tools | curl to editor endpoints; secret used ONLY for editor auth, never echoed; container-local jq for response triage |

## Technique ladder
1. Sentinel + health checks first; fail-closed on any deviation before technique steps.
2. Read-only enumeration of the target plane (sha8 fingerprints only, zero PII).
3. The single strongest technique step per SSOT prior evidence (see rows above).
4. Non-destructive marker/oracle verification only; any state change must be declared-scope + reversible.
5. Cleanup + before/after state diff (identical = clean exit).

## Abort criteria (fail-closed)
- 2 strikes on any primitive class; any 429; >=3 consecutive transport failures; any unintended state change beyond declared marker scope (immediate full rollback + residue re-verify + lane abort).
- NEVER-ROTATE all credentials; sha8-only fingerprints in chat/artifacts; zero PII values.

## Success oracles
- O1: editor session established (login 200/session cookie) from 10.130.x vantage
- O2: workflow LIST returns >=1 workflow (sha8 names only — fleet PII tables are NEVER read)
- O3: secret validity verdict LIVE/DEAD recorded; secret value stays in 0600 vault, sha8 in chat
- O4: zero workflow executions, zero credential-node reads, zero PII reads

**AWAITING OWNER GO — DO NOT FIRE**
