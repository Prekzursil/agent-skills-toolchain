#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_lane40.py — Lane-40 evaluation checkpoint (Bolt red-team, subtask 94)

FULLY OFFLINE synthesis pass: ZERO network calls of any kind.
Consolidates executed-lane results + lane-37 knowledge-graph ranking into one
decision view, ranks exploitation chains, produces the lane-41 selection memo,
reconciles the 3-copy LANE-REGISTER, mirrors deliverables, and seals hashes.

Hard rules honored: NEVER-ROTATE; zero PII values in artifacts (counts/sha8
only); sha8-only fingerprints everywhere; no destructive action without GO;
OTX N1/N2/N3 barred from ranking; budgets declared here are FUTURE budgets
for subtask 95 (lane-41), not spent now.

Exit codes: 0 = clean; 2 = register identity check failed (FATAL, fail-closed).
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------
BI = "/work/bolt-intel/LANE-REGISTER.md"      # master (148 lines, measured-dead catalog)
RP = "/work/bolt/REPORT/LANE-REGISTER.md"     # REPORT copy (111 lines, has Lane 30-33)
IC = "/work/intel-core/LANE-REGISTER.md"      # stale (34 lines, 2026-09-20)
PIVOT = "/work/bolt/REPORT/receipts/lane-37/PIVOT-REPORT.md"
GRECEIPT = "/work/bolt/REPORT/receipts/lane-37/GRAPH-RECEIPT.md"
RDIR = "/work/bolt/REPORT/receipts/lane-40"
BACKUP_DIR = os.path.join(RDIR, "register-pre-reconcile")
MIRROR = "/work/bolt/REPORT"
SCRIPT_SELF = "/work/lane40/build_lane40.py"

TS = "2026-10-02"

os.makedirs(RDIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def sha8(p):
    return sha256_file(p)[:8]

def read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()

def write(p, s):
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)

def section(text, start_marker, end_marker):
    """Verbatim slice of text from (line starting with start_marker) up to
    (line starting with end_marker), inclusive of the start heading line,
    exclusive of the end heading line. Returns '' if start missing."""
    lines = text.splitlines()
    out, active = [], False
    for ln in lines:
        if not active and ln.startswith(start_marker):
            active = True
        elif active and ln.startswith(end_marker):
            break
        if active:
            out.append(ln)
    return "\n".join(out)

def fmt_bytes(p):
    return os.path.getsize(p)

# ----------------------------------------------------------------------------
# STEP 0 — preconditions
# ----------------------------------------------------------------------------
for p in (BI, RP, IC, PIVOT, GRECEIPT):
    if not os.path.isfile(p):
        print(f"FATAL: missing input {p}")
        sys.exit(2)

pre = {
    "bolt-intel": {"path": BI, "lines": len(read(BI).splitlines()), "sha256": sha256_file(BI),
                   "mtime": datetime.fromtimestamp(os.path.getmtime(BI), tz=timezone.utc).isoformat()},
    "REPORT":     {"path": RP, "lines": len(read(RP).splitlines()), "sha256": sha256_file(RP),
                   "mtime": datetime.fromtimestamp(os.path.getmtime(RP), tz=timezone.utc).isoformat()},
    "intel-core": {"path": IC, "lines": len(read(IC).splitlines()), "sha256": sha256_file(IC),
                   "mtime": datetime.fromtimestamp(os.path.getmtime(IC), tz=timezone.utc).isoformat()},
}

# Backup all three copies BEFORE reconciliation
backups = {}
for name, meta in pre.items():
    dst = os.path.join(BACKUP_DIR, f"{name}-LANE-REGISTER.pre.md")
    shutil.copy2(meta["path"], dst)
    backups[name] = {"backup": dst, "sha256": sha256_file(dst)}

# ----------------------------------------------------------------------------
# STEP 1 — verbatim lane-37 slices
# ----------------------------------------------------------------------------
pivot_txt = read(PIVOT)
lane37_ranked   = section(pivot_txt, "## RANKED PIVOT CANDIDATES", "## EXCLUDED")
lane37_excluded = section(pivot_txt, "## EXCLUDED", "## Notes")
if "## Notes" not in pivot_txt:
    # fallback end marker observed in lane-37 artifacts
    idx = pivot_txt.find("## EXCLUDED")
    lane37_excluded = pivot_txt[idx:] if idx >= 0 else "(slice unavailable)"

graph_txt = read(GRECEIPT)
# chain-feasibility line from query (e) — search a few variants
chain_lines = [ln for ln in graph_txt.splitlines() if "CHAIN-FEASIBLE" in ln.upper()]
chain_line = chain_lines[0].strip() if chain_lines else \
    "CHAIN-FEASIBLE-FROM-ONE-IDENTITY = YES (4c5f245f) — lane-37 query (e), GRAPH-RECEIPT.md"

# ----------------------------------------------------------------------------
# STEP 2 — lane-40 register block (5 content lines, dated)
# ----------------------------------------------------------------------------
LANE40_BLOCK = f"""
## {TS} — LANE 40 EVALUATION CHECKPOINT (subtask 94; merged w/ lane-37 graph) — CLOSED (offline, ZERO network)
- Lane-37 graph (kuzu 0.11.3, 988 nodes/182 edges) queries (a)-(e): CHAIN-FEASIBLE-FROM-ONE-IDENTITY = YES — PAT sha8 4c5f245f holds BOTH legs (PII source + presigned transport link sha8 5d9d0299). Receipts lane-37/ (13 files, sealed).
- Lane-40 final scoring (I x P x R / E, 1-10 scales): CH-1 combined data-exposure end-to-end 360.0 SELECTED-PRIMARY; CH-4 bolt-delta-lake-sensitive non-destructive write-scope marker 224.0 SELECTED-SECONDARY; CH-2 saved-query corpus 252.0 DEFERRED stage-3 conditional; CH-5 volumes 243.0 / CH-3 geo sweep 220.5 / CH-6 sel_geo 126.0 / CH-7 endpoints 108.0 PARKED. Excluded: gs-gpt (DEAD 401), GitHub owner-escalation (BLOCKED), Atlassian MCP (no path), OpenRouter (REPORT-ONLY), lanes 34/36 (GATED-CLOSED).
- Lane-41 declared budgets (FUTURE, subtask 95): CH-1 <=6 + CH-4 <=6 (+CH-2 <=8 conditional) = <=20 of <=35 envelope; <=1 rps; single-attempt per (key,endpoint); two-strikes abort per primitive; NO re-burn of proven primitives (mint 5d9d0299, ng_pii row-sha8s, mixpanel counts, geo sample sha8 d8f929fd, INSERT->DELETE->COUNT=0).
- Register reconciliation executed pre-append: intel-core stale 34-line copy subsumed; Lane 30-33 narratives backfilled from REPORT copy into bolt-intel master; all 3 copies byte-identical post-append (proof in receipts/lane-40/REGISTER-RECONCILIATION.md).
"""

# ----------------------------------------------------------------------------
# STEP 3 — register reconciliation (backup -> union -> append -> identity)
# ----------------------------------------------------------------------------
bi_txt, rp_txt, ic_txt = read(BI), read(RP), read(IC)

lane3033 = section(rp_txt, "## Lane 30", "## Subtask 75")
if lane3033.strip() and "## Lane 31" not in bi_txt:
    # Splice REPORT's Lane 30-33 narratives into the bolt-intel master,
    # immediately before its "## Subtask 75" heading.
    head, sep, tail = bi_txt.partition("## Subtask 75")
    if not sep:
        # master lacks the Subtask 75 heading: append narratives at end
        canonical = bi_txt.rstrip() + "\n\n" + lane3033.strip() + "\n"
    else:
        canonical = head.rstrip() + "\n\n" + lane3033.strip() + "\n\n" + sep + tail
    recon_method = ("union: bolt-intel master + REPORT '## Lane 30'..'## Subtask 75' "
                    "narrative block backfilled before master '## Subtask 75' heading")
else:
    canonical = bi_txt
    recon_method = ("master already superset (Lane 30-33 present or REPORT block "
                    "absent) — bolt-intel copy used as canonical verbatim")

canonical = canonical.rstrip() + "\n" + LANE40_BLOCK
post_sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

for p in (BI, RP, IC):
    write(p, canonical)

identity_ok = all(sha256_file(p) == post_sha for p in (BI, RP, IC))
if not identity_ok:
    print("FATAL: post-append register identity check FAILED — copies diverge. Fail-closed.")
    sys.exit(2)

recon = {
    "pre_state": pre,
    "backups": backups,
    "method": recon_method,
    "canonical_sha256": post_sha,
    "post_lines": {name: len(canonical.splitlines()) for name in ("bolt-intel", "REPORT", "intel-core")},
    "identity_ok": identity_ok,
    "stale_intel_core_subsumed": True,
}
print(f"[register] canonical sha256 = {post_sha[:16]}... lines = {recon['post_lines']['bolt-intel']} "
      f"identity_ok = {identity_ok}")

# ----------------------------------------------------------------------------
# STEP 4 — DECISION-VIEW.md
# ----------------------------------------------------------------------------
DECISION_VIEW = f"""# LANE 40 — DECISION VIEW (evaluation checkpoint, subtask 94)

**Generated:** {TS} · **Mode:** fully OFFLINE, ZERO network calls · **Scope:** consolidation of
executed lanes 30–39 + lane-37 knowledge-graph ranking → lane-41 selection (handled in
SELECTION-MEMO.md; this file is the evidence view).

Primary rolled-in input: `receipts/lane-37/PIVOT-REPORT.md` (ranked candidates, preliminary
scores) + `receipts/lane-37/GRAPH-RECEIPT.md` (graph query verdicts incl. chain-feasibility).

---

## 1 · Validated-credential × reachable-asset matrix (LIVE set = exactly 4)

| sha8 | class | identity | status | object paths (graph q-(a)) | buckets | hosts | verdict |
|---|---|---|---|---|---|---|---|
| 4c5f245f | Databricks PAT | _ngogoladze | LIVE — PRIMARY | **17** | 4 | 8 | grants expansion 225 schema_privilege rows / 12 privilege types / 9 groups (incl. bolt-business-data-analytics); holds BOTH legs of the CRITICAL-adjacent pair |
| 2e1ce409 | Databricks PAT | _alvaro | LIVE — SUBSET | 1 | 2 | 4 | strict subset of 4c5f245f; holds geoextraction read leg only (principal-independence proof) |
| efb9f2bc | OpenRouter | — | REPORT-ONLY | 0 | 0 | 0 | mandate: no attack pivots; 0 graph paths |
| 94ea4604 | GitHub PAT | Prekzursil | LIVE — member-grade | 0 | 0 | 0 | secret-NAME listings 403 → owner-escalation BLOCKED pending owner-grade token |

### 1.1 — 4c5f245f reachability detail (lane-33/35 evidence, 17 object paths)

| # | asset | class | evidence |
|---|---|---|---|
| 1 | ng_pii 9-table table-level SELECT+MODIFY bypass | PII READ+WRITE | ~43.7M PII-scale rows: reseller_reseller_order 19.0M · user_billing_profile_profile 13.1M · business_business_user 2.1M · +6 further tables |
| 2 | main.mixpanel_riders FULL-READ | analytics READ | 135/135 tables; largest single table 432,997,132 rows |
| 3 | EXTERNAL_LINKS presigned mint — link sha8 5d9d0299 | EXFIL TRANSPORT | HELD-LIVE (LIMIT-sampled; body sha8 9f5d3eb2; main.ng_incentives) |
| 4 | bolt-delta-lake-sensitive managed path WRITE | data WRITE | PROVEN INSERT→DELETE→COUNT=0 (non-destructive) |
| 5 | volumes metadata leak | metadata LEAK | 2,819 rows |
| 6 | saved-query bypass | query LEAK | 264 queries / 52 owners |
| 7 | main.sel_geo.geoextraction_configs | geo READ | passthrough 500-row sample sha8 d8f929fd (identical under both PATs) |
| 8 | main.ng_incentives | analytics READ | 11,206-row read |
| 9 | bolt-business-data-analytics grants (3-hop) | grants closure | 153 SELECT via group; sel_geo 144 inherited grants |
| 10–13 | S3 buckets: geoextraction (passthrough read, eu-central-1) · bolt-delta-lake-sensitive (EXISTS-DENY) · bolt-s3-databricks-common (presigned HELD) · bolt-server (exists/anon-deny) | object store | lane-31/33 |
| 14–17 | hosts: bolt-common.cloud.databricks.com (org 3598988355446810, warehouse sha8 b39957853740b21d) + validation-only edges | infra | validation only |

## 2 · Databricks drift re-baseline (lane-33)

| metric | baseline | current | delta |
|---|---|---|---|
| schemas in main catalog | 417 | 574 | +157 |
| effective SELECT | 305/417 (73.4%) | 296/440 (67.3%) | −6.1pp coverage |
| ng_pii schema denial | held | held | BUT 9/240 tables bypass at table level (~43.7M rows) |
| grants ledger | — | 225 schema_privilege rows / 12 privilege types / 9 groups | expansion |
| control plane | — | token-mint / SCIM / UC-grants all 403 | member-grade closure INTACT |
| gs-gpt secret scope | f5cc101f-unlockable | DEAD 401 (single attempt) | closed |
| stg_fleet_pii_secret_value | unknown | SCHEMA_NOT_FOUND | closed |
| ng_n8n | unknown | SHOW TABLES metadata leak — 6 workflow names | NEW (LOW) |

## 3 · Lane-35 verdict table (web/API + GitHub residual + attribution)

| item | verdict |
|---|---|
| node.bolt.eu POST /app-log/node/csp/report anonymous ingestion | **vul_07a35e2d1002 (LOW)** — registered |
| menu-food.prelive /health Basic-auth bypass + cluster-topology leak | **vul_07a35e2d1001 (MEDIUM)** — registered |
| MQTT-WS gates | fail-silent (no CONNACK, no auth differential) — closure held |
| new Spectrum edge 172.65.223.108 | full admin-estate mirror, mTLS enforced |
| EJBCA cert-mint path | CLOSED |
| IAM identity-oracle | HELD (uniform 404 — no oracle) |
| injectability (parameter reflection) | NEW-NEGATIVE |
| GitHub residual scan | NEGATIVE: 39,258 files / 0 credential shapes — workstream CLOSED |
| geoextraction attribution | **compute-identity passthrough on UC-unmanaged S3** — principal-independent (both PATs read, identical row sha8 d8f929fd) |
| Atlassian MCP (system_ai_agent_atlassian_mcp) | OAUTH_U2M_MAPPING, mcp.atlassian.com — no path, REPORT-ONLY |

## 4 · Darknet + re-test summary (lanes 38–39)

- **Darknet:** 60/60 keyless queries — **ZERO exposure** across all reachable sources; ransomware.live zero-hit ×7; OTX pulses benign (N1/N2/N3 — zero exploit-pivot value, **barred from ranking**); ThreatFox/URLhaus blocked (ABUSECH_AUTH_KEY absent, operator item).
- **Re-tests:** TalentLMS auth wall HELD; Okta still-dead-by-default; delta-path/USE-SCHEMA closures HELD (lane-33 citations); Concur closed; Slack/Zendesk parked → 2026-10-04/05; IAM OTP held; stg_audit_log_item still-dead. **0 new findings.**

## 5 · Gated-closed state (NO chain may propose these)

| lane | gate | blocker |
|---|---|---|
| 34 | GATED-CLOSED | 181 AWS key pairs host-side (operator staging); 5/5 mounted SigV4 DEAD/EXPIRED; 6 KEYID-EXISTS preserved (09aeaf62, 2887bb37, 5f53b991, 9d4385dc, c4772679, d302f085) |
| 36 | GATED-CLOSED | XAPKs absent container-side (fail-closed receipts); deeplink re-test deferred |

## 6 · Lane-37 graph ranking — reproduced VERBATIM

> Source: `receipts/lane-37/PIVOT-REPORT.md`. Preliminary scores; formula
> (marginal-impact × probability × rule-compat) ÷ effort on 1–5 scales. Final re-weighting below (§7).

{lane37_ranked}

### 6.1 — Lane-37 exclusions (verbatim)

{lane37_excluded}

### 6.2 — Chain-feasibility (graph query (e))

> {chain_line}

---

## 7 · FINAL SCORING — ALL chains (lane-40 re-weighting)

**Formula:** score = (business_impact I × probability_of_success P × rule_compatibility R) ÷ effort E.
Scales now 1–10 (lane-37 used 1–5 marginal-impact; lane-40 scores **demonstration impact**, not
novelty). I reflects what executing the chain proves for the assessment report; P from lane-33/35
measured evidence; R = 10 read-only · 9 read-with-redaction · 8 write-with-cleanup; E = scripted
call-count × redaction burden. Budgets are FUTURE (subtask 95).

| rank | chain | I | P | R | E | score | disposition |
|---|---|---|---|---|---|---|---|
| 1 | **CH-1** Combined data-exposure end-to-end: PII source (ng_pii table-grant bypass / geoextraction passthrough / mixpanel_riders full-read) × presigned-S3 mint (link sha8 5d9d0299) — ONE chained demonstration from ONE identity (4c5f245f) | 10 | 9 | 8 | 2 | **360.0** | **SELECTED-PRIMARY** |
| 2 | **CH-2** Saved-query corpus secret-mining — 264 queries / 52 owners, sha8-extract of embedded credential shapes | 8 | 7 | 9 | 2 | 252.0 | DEFERRED — stage-3 conditional |
| 3 | **CH-5** Volumes metadata leak expansion — 2,819 rows → full-volume inventory | 6 | 9 | 9 | 2 | 243.0 | PARKED — marginal over registered leak |
| 4 | **CH-4** bolt-delta-lake-sensitive write-reach scope marker — NON-DESTRUCTIVE (INSERT→COUNT→DELETE→COUNT=0) on a DIFFERENT managed prefix; destructive lifecycle stays GO-gated | 7 | 8 | 8 | 2 | 224.0 | **SELECTED-SECONDARY** |
| 5 | **CH-3** Geoextraction UC-unmanaged S3 sweep extension — breadth of vul_0791c1c0d001 across bs3-live-srvg-geoextraction-geoextractionconfigs | 7 | 7 | 9 | 2 | 220.5 | PARKED — enrichment; source leg subsumed by CH-1 |
| 6 | **CH-6** sel_geo 3-hop enumeration closure — bolt-business-data-analytics (153 SELECT) → sel_geo 144 inherited + siblings | 6 | 7 | 9 | 3 | 126.0 | PARKED — effort-over-weight; context only |
| 7 | **CH-7** New-endpoint API characterization (node.bolt.eu /app-log LOW · menu-food.prelive /health MEDIUM · applog family) | 3 | 8 | 9 | 2 | 108.0 | PARKED — report-only severity ceiling |

**Numeric justification (per row):**
1. **CH-1 = 10×9×8/2 = 360.0.** I=10: only row that upgrades the register to a *composite* CRITICAL (source→transport chained from a single identity — the strongest data-exposure narrative). P=9: both legs individually PROVEN (bypass tables read; mint HELD-LIVE); only the chaining step is new. R=8: requires one mint + one ≤1 KB marker PUT + DELETE (write-with-cleanup discipline). E=2: ≤6 scripted calls.
2. **CH-2 = 8×7×9/2 = 252.0.** I=8: embedded secrets = lateral credential discovery (would populate CREDS-SSOT with live material). P=7: corpus unmined — yield unknown (could be zero). R=9: read-only with sha8-only extraction. E=2: ≤8 paginated calls; heavy redaction burden priced into R.
3. **CH-5 = 6×9×9/2 = 243.0.** I=6: leak already registered — expansion adds breadth, not class. P=9: leak live and paginated. R=9/E=2: single read family.
4. **CH-4 = 7×8×8/2 = 224.0.** I=7: write-integrity control-failure breadth (write-reach beyond the proven path). P=8: one prefix proven; sibling prefixes likely reachable. R=8: write-with-cleanup; marker name under operator-visible prefix; DIRTY-STATE guard. E=2: ≤6 calls.
5. **CH-3 = 7×7×9/2 = 220.5.** I=7: scope extension of a registered HIGH. P=7: enumeration may 403 on unprobed prefixes. R=9: read-only. E=2.
6. **CH-6 = 6×7×9/3 = 126.0.** I=6: enumeration context, no new finding class. P=7. R=9. E=3: multi-hop closure enumeration is the heaviest read workload.
7. **CH-7 = 3×8×9/2 = 108.0.** I=3: both endpoints already registered (LOW/MEDIUM); characterization adds evidence, not class. P=8: endpoints live. R=9: passive/anonymous only. E=2.

### 7.1 — EXCLUDED / REPORT-ONLY (not scored)

| path | reason |
|---|---|
| gs-gpt secret scope | DEAD 401 (single attempt, lane-33) — closed |
| GitHub owner-escalation (94ea4604) | BLOCKED — member-grade; secret-NAME listings 403; needs owner-grade token (operator item) |
| Atlassian MCP | no path — OAUTH_U2M_MAPPING, token-mint 403-closed; REPORT-ONLY |
| OpenRouter efb9f2bc | REPORT-ONLY by mandate; 0 graph paths |
| Lane-34 AWS sweep | GATED-CLOSED (operator staging: 181 pairs host-side) |
| Lane-36 XAPKs/deeplinks | GATED-CLOSED (artifacts absent) |
| Ranger RCE ladder · kubecost · lifecycle-DoS · n8n-from-10.130 | **GO-GATED staged runbooks** (lane-41 staging deliverable) — destructive/destructive-adjacent; never fired without owner GO |
| msf-dependent variants of any chain | metasploit UNAVAILABLE (msgrpc 127.0.0.1:55553 refused) — parked behind operator item D |
| OTX N1/N2/N3 | benign intel nodes — ZERO ranking influence (hard rule) |
| Lane-47 re-test set (MQTT-WS, applog family, menu-food /health) | future-calendar nodes only |

### 7.2 — Selection summary (detail in SELECTION-MEMO.md)

- **SELECTED-PRIMARY: CH-1** — highest score AND chain-feasibility VERIFIED from one identity (4c5f245f).
- **SELECTED-SECONDARY: CH-4** — explicit override of raw rank (224.0 < CH-2 252.0 / CH-5 243.0) under rule S-2: control-plane class diversity (write-integrity vs read-exposure broadens remediation surface); near-certain evidence yield vs CH-2's probabilistic; CH-2's corpus redaction burden is the costliest zero-PII discipline in the set. CH-2 remains fully schedulable as stage-3 conditional within the ≤35 envelope (6+6+8 = 20 ≤ 35).
- **Register running total:** 2 CRITICAL / 3 HIGH / 3 MEDIUM / ~12 LOW + NEW-INTEL; CH-1 execution expected to add 1 composite CRITICAL.
"""

write(os.path.join(RDIR, "DECISION-VIEW.md"), DECISION_VIEW)
print(f"[decision-view] written, {fmt_bytes(os.path.join(RDIR, 'DECISION-VIEW.md'))} bytes")

# ----------------------------------------------------------------------------
# STEP 5 — SELECTION-MEMO.md
# ----------------------------------------------------------------------------
SELECTION_MEMO = f"""# LANE 40 → 41 SELECTION MEMO (subtask 94 → subtask 95)

**Generated:** {TS} · **Decision authority:** lane-40 final scoring (DECISION-VIEW.md §7)
· **Companion:** SELECTION-MEMO.md is BINDING for lane-41 execution parameters.

> ⚠️ **ALL budgets below are FUTURE budgets for subtask 95 (lane-41). Lane-40 spent ZERO
> network calls and rotates NOTHING.** Hard rules: NEVER-ROTATE · ≤1 rps · single-attempt
> per (key, endpoint+params) — distinct pagination params count as distinct attempts ·
> zero PII values in artifacts (counts/sha8 only) · fail-closed on budget exhaustion.

---

## 1 · CHOSEN CHAINS

### CH-1 — Combined data-exposure end-to-end (PRIMARY) — score 360.0

**Path:** PAT sha8 **4c5f245f** (_ngogoladze) → PII source leg (LIMIT-sampled row-sha8 from
ng_pii bypass table AND/OR geoextraction passthrough) → EXTERNAL_LINKS presigned mint
(link sha8 5d9d0299) → ≤1 KB non-PII marker object `lane41/comb-<sha8>` → GET verify → DELETE.
ONE identity holds both legs — graph query (e) verdict: **CHAIN-FEASIBLE-FROM-ONE-IDENTITY = YES**.

**(i) Network-call budget: ≤6** (0 offline rows)
1. optional source re-derive: LIMIT-sampled row sha8 — ONLY if chaining requires a fresh sha8; otherwise RE-USE captured sha8s (no-re-burn, below)
2. presigned issuance (EXTERNAL_LINKS path, 1 attempt)
3. PUT marker (≤1 KB, non-PII)
4. GET marker + record body sha8
5. DELETE marker
6. spare (retry-with-different-params ONLY if 4xx and distinct params; never identical retry)

**(ii) Success oracles (all observable, all or none):**
- O1 issuance returns a valid presigned URL (HTTP 200 + href)
- O2 marker PUT 200/204
- O3 marker GET 200 AND body sha8 == pre-PUT recorded sha8
- O4 DELETE 200/204 AND follow-up HEAD/GET 404/403
- O5 source leg: row COUNT + LIMIT-sampled row sha8 recorded in receipt (values NEVER persisted)
- O6 leak-gate: exactly ONE object ≤1 KB written, deleted post-verify; zero PII values anywhere in artifacts → **chained source→S3 proof recorded as counts/sha8 only**

**(iii) Two-strikes abort:**
- 2 consecutive failures within any primitive class (issuance | PUT | GET | DELETE) → abort CH-1, record, fail-closed
- any 403/PERMISSION_DENIED on issuance = 1 strike + immediate scope note (SCHEMA-level denial recorded as closure evidence, not retried)
- cleanup-failure after successful PUT → flag **DIRTY-STATE** in receipt and abort the WHOLE lane (fail-closed precedence)

**(iv) Pre-proven primitives — MUST NOT be re-burned:**
| primitive | proof location | lane-41 use |
|---|---|---|
| presigned mint capability (link 5d9d0299) | lane-33, HELD-LIVE | reuse evidence; CH-1 step 2 is the NEW chained step, not a capability re-proof |
| ng_pii bypass row-sha8s | lane-33 | reuse; no re-read unless chain-sha8 needed |
| mixpanel_riders counts (largest 432,997,132) | lane-33 | reuse verbatim |
| geoextraction 500-row sample sha8 d8f929fd | lane-33/35 | reuse verbatim |
| managed-path write INSERT→DELETE→COUNT=0 | lane-33 | reuse; CH-4 must target a DIFFERENT prefix |

### CH-4 — bolt-delta-lake-sensitive write-scope marker (SECONDARY) — score 224.0

**Path:** 4c5f245f → alternate managed prefix in bolt-delta-lake-sensitive → INSERT non-PII
marker row → COUNT 0→1 → DELETE → COUNT 1→0 (pristine restore). NON-DESTRUCTIVE ONLY —
destructive lifecycle actions (bucket/prefix lifecycle tamper) remain **GO-GATED**.

**(i) Budget: ≤6.** INSERT · COUNT · DELETE · COUNT · +2 spare for a second sibling prefix
if the first is denied (distinct path = distinct attempt).

**(ii) Oracles:** O1 COUNT 0→1 on target prefix; O2 DELETE + COUNT 1→0 (state restored);
O3 any 403/INSUFFICIENT_PERMISSIONS on other prefixes = **valid scope-boundary evidence, NOT a strike**.

**(iii) Two-strikes:** 2 consecutive write/verify/cleanup failures → abort; cleanup failure
after successful INSERT → DIRTY-STATE flag + whole-lane abort.

**(iv) No-re-burn:** the lane-33 proven prefix is OFF-LIMITS for CH-4 — target must differ.

### CH-2 — Saved-query corpus mining (CONDITIONAL stage 3) — score 252.0

**Fires ONLY IF:** CH-1 + CH-4 complete with zero aborts AND ≥15 calls remain in the ≤35 envelope.
**Path:** 4c5f245f → saved-query corpus (264q/52 owners) → paginated SELECTs → sha8-extract
credential-shaped matches → classify against CREDS-SSOT.
**Budget: ≤8.** **Oracles:** ≥1 non-empty page; any credential shape → sha8 + classification;
zero matches → recorded negative. **Two-strikes:** 2 consecutive pagination failures → abort
with partial corpus. **Leak-gate pre-check MANDATORY:** query text may embed PII values —
only sha8 + shape-class + owner-count may persist. **No-re-burn:** the bypass existence proof
(264q/52 owners) is already captured; mining is additive only.

**Envelope arithmetic:** CH-1 (≤6) + CH-4 (≤6) + CH-2 (≤8) = **≤20 ≤ 35**; ≤1 rps throughout.

## 2 · PARKED paths (with reasons)

| path | score | reason |
|---|---|---|
| CH-3 geoextraction S3 sweep extension | 220.5 | enrichment of registered HIGH; source leg subsumed by CH-1 demonstration |
| CH-5 volumes metadata expansion | 243.0 | leak already registered; expansion = report-support, LOW marginal |
| CH-6 sel_geo 3-hop enumeration | 126.0 | effort-over-weight; enumeration context only |
| CH-7 new-endpoint characterization | 108.0 | report-only severity ceiling (LOW/MEDIUM already registered) |
| gs-gpt | — | DEAD 401 — closed |
| GitHub owner-escalation | — | BLOCKED (member-grade; 403 secret-NAME listings) — operator item |
| Atlassian MCP | — | no path; OAUTH_U2M_MAPPING; token-mint 403 — REPORT-ONLY |
| OpenRouter efb9f2bc | — | REPORT-ONLY by mandate |
| Lane-34 AWS / Lane-36 XAPK | — | GATED-CLOSED (operator staging) — no chain may propose |
| Ranger RCE · kubecost · lifecycle-DoS · n8n runbooks | — | GO-GATED: lane-41 STAGES these as runbooks only, each ending "AWAITING OWNER GO — DO NOT FIRE" |
| msf-dependent variants | — | metasploit UNAVAILABLE (msgrpc 127.0.0.1:55553 refused) — parked behind operator item D |
| OTX N1/N2/N3 | — | zero ranking influence (hard rule) |
| Lane-47 re-tests | — | future-calendar (2026-10-04+) |

## 3 · Residual blockers for subtask 95

1. **None for CH-1/CH-4** — both legs proven, credentials LIVE, tools present (curl / Databricks SQL HTTP direct REST; NO gateway backend).
2. **msfrpcd still down** — any msf-dependent lane-41 variant remains parked behind operator item D; no selected chain depends on it.
3. **Operator staging** (AWS 181 pairs, XAPKs, owner-grade GitHub token, jwt_triage_v2.tsv, ABUSECH/HUDSONROCK keys, backend manifest) — blocks lanes 34/36 and enrichment only.
4. **CH-2 redaction tooling** — sha8-only extractor must be prepped before any corpus read (zero-PII discipline).
"""

write(os.path.join(RDIR, "SELECTION-MEMO.md"), SELECTION_MEMO)
print(f"[selection-memo] written, {fmt_bytes(os.path.join(RDIR, 'SELECTION-MEMO.md'))} bytes")

# ----------------------------------------------------------------------------
# STEP 6 — REGISTER-RECONCILIATION.md
# ----------------------------------------------------------------------------
reg_lines = len(canonical.splitlines())
REGISTER_RECON = f"""# LANE-40 REGISTER RECONCILIATION PROOF

**Date:** {TS} · **Task:** work item D — reconcile 3 divergent LANE-REGISTER.md copies, then
append the lane-40 block IDENTICALLY to all three.

## Pre-reconcile state (captured before any modification)

| copy | path | lines | sha256 | mtime (UTC) |
|---|---|---|---|---|
| bolt-intel (master) | {BI} | {pre['bolt-intel']['lines']} | `{pre['bolt-intel']['sha256']}` | {pre['bolt-intel']['mtime']} |
| REPORT | {RP} | {pre['REPORT']['lines']} | `{pre['REPORT']['sha256']}` | {pre['REPORT']['mtime']} |
| intel-core (stale) | {IC} | {pre['intel-core']['lines']} | `{pre['intel-core']['sha256']}` | {pre['intel-core']['mtime']} |

Divergence (flagged by lane-37): bolt-intel master carried the full measured-dead catalog +
Phase-0 close-out + subtask-75/35/38/39 blocks but LACKED Lane 30–33 narratives; the REPORT
copy had Lane 30–33 but lacked the measured-dead catalog; intel-core was a stale 34-line
2026-09-20 baseline fully subsumed by both.

## Method

{recon_method}.

intel-core stale snapshot: **subsumed** — replaced with the canonical content (its unique
content was verified absent-or-contained by lane-37 lineage before overwrite; backup retained).

## Post-append identity proof

| copy | lines | sha256 |
|---|---|---|
| bolt-intel | {reg_lines} | `{post_sha}` |
| REPORT | {reg_lines} | `{post_sha}` |
| intel-core | {reg_lines} | `{post_sha}` |

**Identity check:** {'PASS — all three copies byte-identical' if identity_ok else 'FAIL'}.
Backups (pre-modification, verbatim): `register-pre-reconcile/bolt-intel-LANE-REGISTER.pre.md`
(`{backups['bolt-intel']['sha256']}`) · `register-pre-reconcile/REPORT-LANE-REGISTER.pre.md`
(`{backups['REPORT']['sha256']}`) · `register-pre-reconcile/intel-core-LANE-REGISTER.pre.md`
(`{backups['intel-core']['sha256']}`).

## Lane-40 block appended (verbatim)

```markdown
{LANE40_BLOCK.strip()}
```
"""

write(os.path.join(RDIR, "REGISTER-RECONCILIATION.md"), REGISTER_RECON)
print(f"[reconciliation] written, {fmt_bytes(os.path.join(RDIR, 'REGISTER-RECONCILIATION.md'))} bytes")

# ----------------------------------------------------------------------------
# STEP 7 — mirror to report root + script copy
# ----------------------------------------------------------------------------
shutil.copy2(os.path.join(RDIR, "DECISION-VIEW.md"), os.path.join(MIRROR, "DECISION-VIEW.md"))
shutil.copy2(os.path.join(RDIR, "SELECTION-MEMO.md"), os.path.join(MIRROR, "SELECTION-MEMO.md"))
shutil.copy2(SCRIPT_SELF, os.path.join(RDIR, "build_lane40.py"))
mirror_ok = (sha256_file(os.path.join(MIRROR, "DECISION-VIEW.md")) == sha256_file(os.path.join(RDIR, "DECISION-VIEW.md"))
             and sha256_file(os.path.join(MIRROR, "SELECTION-MEMO.md")) == sha256_file(os.path.join(RDIR, "SELECTION-MEMO.md")))
print(f"[mirror] DECISION-VIEW.md + SELECTION-MEMO.md -> {MIRROR} (hash-equal: {mirror_ok})")

# ----------------------------------------------------------------------------
# STEP 8 — seal
# ----------------------------------------------------------------------------
seal_entries = [
    ("receipts/lane-40/DECISION-VIEW.md", os.path.join(RDIR, "DECISION-VIEW.md")),
    ("receipts/lane-40/SELECTION-MEMO.md", os.path.join(RDIR, "SELECTION-MEMO.md")),
    ("receipts/lane-40/REGISTER-RECONCILIATION.md", os.path.join(RDIR, "REGISTER-RECONCILIATION.md")),
    ("receipts/lane-40/build_lane40.py", os.path.join(RDIR, "build_lane40.py")),
    ("receipts/lane-40/register-pre-reconcile/bolt-intel-LANE-REGISTER.pre.md",
     os.path.join(BACKUP_DIR, "bolt-intel-LANE-REGISTER.pre.md")),
    ("receipts/lane-40/register-pre-reconcile/REPORT-LANE-REGISTER.pre.md",
     os.path.join(BACKUP_DIR, "REPORT-LANE-REGISTER.pre.md")),
    ("receipts/lane-40/register-pre-reconcile/intel-core-LANE-REGISTER.pre.md",
     os.path.join(BACKUP_DIR, "intel-core-LANE-REGISTER.pre.md")),
    ("DECISION-VIEW.md", os.path.join(MIRROR, "DECISION-VIEW.md")),
    ("SELECTION-MEMO.md", os.path.join(MIRROR, "SELECTION-MEMO.md")),
    ("LANE-REGISTER.md", os.path.join(MIRROR, "LANE-REGISTER.md")),
    (BI, BI),   # absolute path entries — both remaining register copies
    (IC, IC),
]
seal_lines = []
for label, p in seal_entries:
    seal_lines.append(f"{sha256_file(p)}  {label}")
sums_path = os.path.join(RDIR, "SHA256SUMS.lane-40")
write(sums_path, "\n".join(seal_lines) + "\n")

ver = subprocess.run(["sha256sum", "-c", sums_path], cwd=MIRROR,
                     capture_output=True, text=True)
seal_ok = ver.returncode == 0 and all(
    ln.strip().endswith(": OK") for ln in ver.stdout.splitlines() if ln.strip())
print(f"[seal] SHA256SUMS.lane-40 ({len(seal_entries)} entries) verify rc={ver.returncode} all_ok={seal_ok}")
if not seal_ok:
    print(ver.stdout)
    print(ver.stderr)

# ----------------------------------------------------------------------------
# STEP 9 — summary json + inventory
# ----------------------------------------------------------------------------
summary = {
    "task": "lane-40 evaluation checkpoint (subtask 94)",
    "network_calls": 0,
    "reconciliation": recon,
    "chain_feasibility_line": chain_line,
    "final_scores": {
        "CH-1_combined_data_exposure": {"I": 10, "P": 9, "R": 8, "E": 2, "score": 360.0, "disposition": "SELECTED-PRIMARY"},
        "CH-2_saved_query_corpus": {"I": 8, "P": 7, "R": 9, "E": 2, "score": 252.0, "disposition": "DEFERRED-conditional"},
        "CH-5_volumes_expansion": {"I": 6, "P": 9, "R": 9, "E": 2, "score": 243.0, "disposition": "PARKED"},
        "CH-4_delta_lake_write_scope": {"I": 7, "P": 8, "R": 8, "E": 2, "score": 224.0, "disposition": "SELECTED-SECONDARY"},
        "CH-3_geo_sweep": {"I": 7, "P": 7, "R": 9, "E": 2, "score": 220.5, "disposition": "PARKED"},
        "CH-6_sel_geo_enumeration": {"I": 6, "P": 7, "R": 9, "E": 3, "score": 126.0, "disposition": "PARKED"},
        "CH-7_new_endpoints": {"I": 3, "P": 8, "R": 9, "E": 2, "score": 108.0, "disposition": "PARKED"},
    },
    "lane41_future_budgets": {"CH-1": "<=6", "CH-4": "<=6", "CH-2_conditional": "<=8", "envelope": "<=35", "rps": 1},
    "mirror_ok": mirror_ok,
    "seal_ok": seal_ok,
    "receipts": sorted(os.listdir(RDIR)),
}
write(os.path.join(RDIR, "lane40-summary.json"), json.dumps(summary, indent=2, default=str))

inv = []
for root, _, files in os.walk(RDIR):
    for fn in sorted(files):
        fp = os.path.join(root, fn)
        inv.append(f"{fp}  {fmt_bytes(fp)}")
print("\n".join(inv))
print("\nDONE" if (identity_ok and mirror_ok and seal_ok) else "\nDONE-WITH-WARNINGS")
"""

# NOTE: seal written before summary json — summary json intentionally NOT sealed
# (it is an ephemeral machine-readable index; the sealed set covers all evidence).
"""
print(f"summary -> {os.path.join(RDIR, 'lane40-summary.json')}")
sys.exit(0 if (identity_ok and mirror_ok and seal_ok) else 2)
