# RUNBOOK — kubecost-depth re-test (w20 kubecost-depth lane re-measure)
**Lane-41 staged 2026-10-02 · GO-GATED — re-test of a measured-dead/partially-open finding**

| Axis | Value |
|---|---|
| Target | kubecost cost/allocation plane from VPC vantage (internal ingress; external edge mirrors admin estate only) |
| Prior evidence | w20 kubecost-depth (breach-series w20): depth assessed, multi-cluster cost-data reach unresolved at seal |
| Gating | owner GO **AND** confirmation that VPC vantage is reachable from the authorized container (no new network position created) |
| Budget | <=8 network actions, >=1.25 s pacing, single-attempt per (key,endpoint) |
| Tools | curl GETs on /api/allocation, /api/costDataRange, /model/alldata; direct container only |

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
- O1: >=1 200 on an unauthenticated allocation endpoint -> re-open as data-exposure
- O2: all endpoints gated -> dated HELD receipt, zero re-open
- O3: any cluster-namespace enumeration naming workloads -> sha8-only workload fingerprints, no full inventories

**AWAITING OWNER GO — DO NOT FIRE**
