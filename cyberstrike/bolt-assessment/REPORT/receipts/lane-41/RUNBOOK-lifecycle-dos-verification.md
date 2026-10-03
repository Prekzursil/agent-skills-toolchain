# RUNBOOK — S3 lifecycle-DoS verification (NON-DESTRUCTIVE, verification-only)
**Lane-41 staged 2026-10-02 · GO-GATED — destructive-adjacent class; verification must stay read-only**

| Axis | Value |
|---|---|
| Target | lifecycle-policy write reachability on managed buckets (bolt-delta-lake-sensitive et al.) via the proven SQL write path |
| Prior evidence | lane-33: write reach PROVEN (INSERT->DELETE->COUNT=0) at tested prefix; lifecycle policy surface never probed |
| Gating | owner GO **AND** written operator confirmation that policy GET is in scope; policy PUT/DELETE is PROHIBITED even under GO |
| Budget | <=4 network actions, >=1.25 s pacing, single-attempt per (key,endpoint) |
| Tools | SQL statement API only (read primitives); boto3 get_bucket_lifecycle_configuration ONLY if a LIVE AWS key exists (none currently mountable) |

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
- O1: visibility into any lifecycle/policy metadata via SQL (information_schema/volume metadata) -> exposure mapped
- O2: no write primitive touches policy state — metadata re-read before/after = identical
- O3: if a policy-write primitive is INFERRED (not exercised), document inference chain with sha8 evidence and stop

**AWAITING OWNER GO — DO NOT FIRE**
