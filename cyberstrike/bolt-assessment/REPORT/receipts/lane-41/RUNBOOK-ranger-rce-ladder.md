# RUNBOOK — Ranger authed-RCE ladder (Apache Ranger admin plane)
**Lane-41 staged 2026-10-02 · GO-GATED — never fired without explicit owner GO**

| Axis | Value |
|---|---|
| Target | Ranger admin console on the Ranger+MLflow+DataHub shared ingress (internal cluster, vpc-census wave-15) |
| Prior evidence | vault-ranger-final: BOTH doors positively closed from every reachable plane; airflow-ranger: prod fernet per-site (plaintext key = local-dev only); lane-33 control plane 403 |
| Gating | owner GO **AND** msfrpcd estate-side start (operator item D) for MSF-rank modules |
| Budget | <=10 network actions, >=1.25 s pacing, single-attempt per (key,endpoint) |
| Tools | direct REST/curl first; msf (CVE modules) ONLY if msfrpcd revived; browser for console |

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
- O1: authenticated session established on Ranger console (>=1 200 on /login POST or API 2xx)
- O2: policy-list read returns >=1 policy row (read-reach proof)
- O3: any RCE primitive yields command-execution oracle WITHOUT persistence — id-echo only
- O4: zero policy modifications (policy JSON diff before/after = identical)
- O5: full session logout; no artifacts left on target

**AWAITING OWNER GO — DO NOT FIRE**
