#!/usr/bin/env python3
"""Dump specific nested blobs needed for hoist. Not a measurement."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")


def load(rel):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


out = {}

d = load("command-center/audit/AUD-0010-repo-weight-baseline.json")
h = d.get("headline")
out["AUD-0010.headline_type"] = type(h).__name__
if isinstance(h, dict):
    out["AUD-0010.headline_keys"] = sorted(h.keys())
    out["AUD-0010.headline_packed"] = h.get("packed_bytes")
elif isinstance(h, str):
    out["AUD-0010.headline_preview"] = h[:200]
rep_h = (d.get("report") or {}).get("headline") if isinstance(d.get("report"), dict) else None
out["AUD-0010.report.headline_keys"] = sorted(rep_h.keys()) if isinstance(rep_h, dict) else type(rep_h).__name__
out["AUD-0010.has_owner_repos"] = "owner_repos" in d
ext = d.get("extensions") or {}
out["AUD-0010.ext_keys"] = sorted(ext.keys()) if isinstance(ext, dict) else None
leg = ext.get("legacy_root") if isinstance(ext, dict) else None
if isinstance(leg, dict):
    out["AUD-0010.legacy_keys"] = sorted(leg.keys())[:40]
    lh = leg.get("headline")
    out["AUD-0010.legacy.headline"] = sorted(lh.keys()) if isinstance(lh, dict) else type(lh).__name__

d = load("command-center/audit/AUD-0052-test-order-dependence.json")
c = (d.get("report") or {}).get("census") or {}
out["AUD-0052.census_keys"] = sorted(c.keys()) if isinstance(c, dict) else None
out["AUD-0052.seeds"] = c.get("seeds") if isinstance(c, dict) else None
out["AUD-0052.lab_orders_differ"] = c.get("lab_orders_differ") if isinstance(c, dict) else None
cls = (c.get("classification") or {}) if isinstance(c, dict) else {}
out["AUD-0052.order_dependent"] = cls.get("order_dependent")

d = load("command-center/audit/AUD-0090-static-analysis-baseline.json")
out["AUD-0090.report_kind"] = d.get("report_kind")
obs = d.get("observations")
out["AUD-0090.observations_type"] = type(obs).__name__
if isinstance(obs, dict):
    out["AUD-0090.observations_keys"] = sorted(obs.keys())
    ctl = obs.get("control")
    out["AUD-0090.control_keys"] = sorted(ctl.keys()) if isinstance(ctl, dict) else type(ctl).__name__
elif isinstance(obs, list):
    out["AUD-0090.observations_n"] = len(obs)
    out["AUD-0090.obs0"] = obs[0] if obs else None
ext = d.get("extensions") or {}
leg = ext.get("legacy_root") if isinstance(ext, dict) else None
if isinstance(leg, dict):
    out["AUD-0090.legacy_keys"] = sorted(leg.keys())[:30]
    out["AUD-0090.legacy.report_kind"] = leg.get("report_kind")
    lobs = leg.get("observations")
    out["AUD-0090.legacy.obs_type"] = type(lobs).__name__
    if isinstance(lobs, dict):
        out["AUD-0090.legacy.obs_keys"] = sorted(lobs.keys())

d = load("command-center/confirmation/CNF-0029-change-surface.json")
br = (d.get("report") or {}).get("branches") or d.get("branches")
out["CNF-0029.branches_n"] = len(br) if isinstance(br, list) else type(br).__name__
if isinstance(br, list) and br:
    out["CNF-0029.branch0_keys"] = sorted(br[0].keys())
    out["CNF-0029.branch_names"] = [b.get("name") or b.get("id") for b in br]
    out["CNF-0029.branch0"] = {k: br[0].get(k) for k in list(br[0])[:20]}

d = load("command-center/receipts/CNF-0145.json")
ss = (d.get("report") or {}).get("sha256_sets") or d.get("sha256_sets")
out["CNF-0145.sha256_sets"] = ss
ctl = (d.get("report") or {}).get("controls") or d.get("controls")
out["CNF-0145.controls_type"] = type(ctl).__name__
if isinstance(ctl, dict):
    out["CNF-0145.controls_keys"] = sorted(ctl.keys())

d = load("command-center/design/council/CNL-0002-resolve-the-measured-v1-schema-catalogue-non-intersection.md")
out["CNL-0002.decision_top"] = d.get("decision")
out["CNL-0002.report.decision"] = (d.get("report") or {}).get("decision") if isinstance(d.get("report"), dict) else None

d = load("command-center/design/council/CNL-0118-role-enforcement-and-participant-replacement-simulation.md")
mr = (d.get("report") or {}).get("measured_results") or {}
out["CNL-0118.mr_keys"] = sorted(mr.keys()) if isinstance(mr, dict) else None
out["CNL-0118.ticks"] = mr.get("ticks") if isinstance(mr, dict) else None
tests = d.get("tests")
out["CNL-0118.tests_n"] = len(tests) if isinstance(tests, list) else type(tests).__name__
if isinstance(tests, list):
    out["CNL-0118.test_ids"] = [t.get("id") for t in tests if isinstance(t, dict)]

d = load("command-center/receipts/IMP-0200.json")
leg = ((d.get("extensions") or {}).get("legacy_root") or {})
pm = d.get("pairwise_matrix") or leg.get("pairwise_matrix") or {}
pairs = pm.get("pairs") if isinstance(pm, dict) else None
out["IMP-0200.pairs_n"] = len(pairs) if isinstance(pairs, list) else None
out["IMP-0200.pm_keys"] = sorted(pm.keys()) if isinstance(pm, dict) else None
cands = d.get("candidates") or leg.get("candidates")
out["IMP-0200.cands_n"] = len(cands) if isinstance(cands, list) else type(cands).__name__
tour = d.get("tournament") or leg.get("tournament") or {}
out["IMP-0200.tour_cands"] = len(tour.get("candidates") or []) if isinstance(tour, dict) else None
_tp = tour.get("pairs") if isinstance(tour, dict) else None
if isinstance(_tp, list):
    out["IMP-0200.tour_pairs"] = len(_tp)
elif isinstance(_tp, dict):
    out["IMP-0200.tour_pairs"] = len(_tp.get("pairs") or [])
else:
    pm2 = tour.get("pairwise_matrix") if isinstance(tour, dict) else None
    out["IMP-0200.tour_pairs"] = len((pm2 or {}).get("pairs") or []) if isinstance(pm2, dict) else None

d = load("command-center/research/RES-0028.json")
tests = d.get("tests")
out["RES-0028.test_ids"] = [t.get("id") for t in tests] if isinstance(tests, list) else type(tests).__name__
if isinstance(tests, list):
    t1 = next((t for t in tests if t.get("id") == "T1"), None)
    out["RES-0028.T1"] = t1
ra = d.get("ranking_algorithm") or ((d.get("extensions") or {}).get("legacy_root") or {}).get("ranking_algorithm")
out["RES-0028.ranking_keys"] = sorted(ra.keys()) if isinstance(ra, dict) else None
out["RES-0028.cited"] = (ra or {}).get("cited_at_source_file_line") if isinstance(ra, dict) else None
claims = d.get("claims") or ((d.get("extensions") or {}).get("legacy_root") or {}).get("claims")
out["RES-0028.claim_ids"] = [c.get("claim_id") for c in claims] if isinstance(claims, list) else None

d = load("command-center/research/RES-0089.json")
rev = d.get("reviewer") or {}
out["RES-0089.reviewer_keys"] = sorted(rev.keys()) if isinstance(rev, dict) else None
out["RES-0089.reviewers"] = rev.get("reviewers")
leg = (d.get("extensions") or {}).get("legacy_root") or {}
lrev = leg.get("reviewer") if isinstance(leg, dict) else None
out["RES-0089.legacy.reviewer"] = lrev if not isinstance(lrev, dict) else {k: lrev.get(k) for k in list(lrev)[:10]}
if isinstance(lrev, dict):
    out["RES-0089.legacy.reviewers"] = lrev.get("reviewers")
dt = d.get("detector_table") or leg.get("detector_table")
out["RES-0089.dt_n"] = len(dt) if isinstance(dt, list) else type(dt).__name__
ar = d.get("applied_result") or leg.get("applied_result")
out["RES-0089.applied_keys"] = sorted(ar.keys()) if isinstance(ar, dict) else None

d = load("command-center/research/evidence-quality/RES-0144-two-axis-source-quality-rubric.json")
rep = d.get("report") or {}
out["RES-0144.report_keys"] = sorted(rep.keys())[:40] if isinstance(rep, dict) else None
out["RES-0144.report.measurements"] = (rep.get("measurements") if isinstance(rep, dict) else None)
out["RES-0144.report.calibration_keys"] = sorted((rep.get("calibration") or {}).keys()) if isinstance(rep.get("calibration"), dict) else None
ext = d.get("extensions") or {}
leg = ext.get("legacy_root") if isinstance(ext, dict) else None
out["RES-0144.legacy_keys"] = sorted(leg.keys())[:30] if isinstance(leg, dict) else None

d = load("command-center/research/deep-research-design/RES-0165-researcher-count-diminishing-returns.json")
rep = d.get("report") or {}
out["RES-0165.report_keys"] = sorted(rep.keys())[:40] if isinstance(rep, dict) else None
out["RES-0165.has_measurements"] = "measurements" in d or (isinstance(rep, dict) and "measurements" in rep)

d = load("command-center/wfa/WFA-0025-sweep-academic-protocols.json")
prots = d.get("protocols") or ((d.get("extensions") or {}).get("legacy_root") or {}).get("protocols") or []
impl = []
for p in prots:
    if not isinstance(p, dict):
        continue
    est = p.get("estate") or {}
    if est.get("status") == "IMPLEMENTED":
        impl.append({"id": p.get("protocol_id") or p.get("id"), "cand": est.get("implementing_candidate_id")})
out["WFA-0025.implemented"] = impl
out["WFA-0025.n_protocols"] = len(prots)
ioe = d.get("implemented_on_estate") or []
out["WFA-0025.ioe"] = [{"id": x.get("protocol_id"), "cand": x.get("implementing_candidate_id")} for x in ioe if isinstance(x, dict)]

d = load("command-center/foundry/WFA-0153-close-the-unresolved-nodes-in-the-466-node-provenanc.json")
st = d.get("settlement") or ((d.get("extensions") or {}).get("legacy_root") or {}).get("settlement") or {}
out["WFA-0153.settlement"] = {k: st.get(k) for k in ("unresolved_count", "resolved_count", "resolved_ids_sha256", "methods_agree", "resolution_rate")} if isinstance(st, dict) else st
surv = d.get("survivors") or ((d.get("extensions") or {}).get("legacy_root") or {}).get("survivors")
out["WFA-0153.survivors_n"] = len(surv) if isinstance(surv, list) else None

d = load("command-center/synthesis/SYN-0041.final-report.json")
rep = d.get("report") or {}
out["SYN-0041.report_keys"] = sorted(rep.keys())[:30] if isinstance(rep, dict) else None
out["SYN-0041.item_n"] = len(rep.get("items") or []) if isinstance(rep, dict) else None
out["SYN-0041.top_has_items"] = "items" in d
out["SYN-0041.sentinel"] = d.get("sentinel")

d = load("command-center/receipts/IMP-0400.json")
rep = d.get("report") or {}
out["IMP-0400.report_keys"] = sorted(rep.keys())[:30] if isinstance(rep, dict) else None
out["IMP-0400.has_replay"] = "replay" in d or (isinstance(rep, dict) and "replay" in rep)

path = REPO / "command-center/p2-wave/ovh-monitor/g1-shards/_claude28/_s00_blobs.out.json"
path.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
print("wrote", path)
for k, v in out.items():
    s = json.dumps(v, default=str)
    print(f"{k}: {s[:300]}")
