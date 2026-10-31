#!/usr/bin/env python3
"""Build the canonical SHARD10-REVIEW-RETURN.json from the fresh independent
battery results (rerun/independent_results.json), preserving the prior run as
provenance. Read-only on all receipts."""
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
res = json.loads((REPO / "_reviewer10w2/rerun/independent_results.json").read_text(encoding="utf-8"))

ERR_COUNTS = {}
units = []
for r in res:
    sch = [f for f in r["fails"] if f.startswith("output-schema")]
    adm = [f for f in r["fails"] if f.startswith("repo-admission")]
    n = 0
    if sch:
        try:
            n = int(sch[0].split("[")[1].split("]")[0].split()[0])
        except Exception:
            n = -1
    ERR_COUNTS[r["unit"]] = n
    units.append({
        "id": r["unit"],
        "artifact": r["artifact"],
        "verdict": "FAIL",
        "probes_rc": list(r["probes_rc"].values()),
        "manifest_sha_match": True,
        "failing_check": (
            "output-schema-valid vs command-center/schema/receipt.schema.json "
            "(%d errors) + repo-admission-validator C2 REJECT" % n
        ),
        "admission_line": (adm[0].split(":: ", 1)[1] if adm else ""),
    })

ret = {
    "schema_version": 1,
    "shard": "10",
    "wave": 2,
    "phase": "review",
    "reviewed_at": "2026-10-25T21:40:00Z",
    "reviewer": "independent-reviewer wave-2 shard-10 RE-RUN (fresh battery, fresh context; did not build these units)",
    "units": units,
    "summary": (
        "Re-run verdict 0/12 closable, identical to the 2026-10-25T19:35Z run by an "
        "instrument written independently by this reviewer (not a re-execution of the "
        "prior script): catalog entries present for all 12 (no owner gates); artifacts "
        "exist/non-empty/parse/state=SUCCESS/not self-blocked; August-era reviewer "
        "closures structurally valid (verdict=PASS + independent=true); all 24 named "
        "probes re-run BY THE REVIEWER exit 0 with SUCCESS:<uid> markers; "
        "UNIT-ARTIFACT-MANIFEST rows recomputed under CRLF->LF normalization match the "
        "live artifacts 12/12 (receipts byte-stable post-probe, so receipts UNCHANGED). "
        "The single failing check on every unit is output-schema-valid: these receipts "
        "were written 2026-08-25 against the then-current receipt.schema.json and "
        "predate its tightened contract (artifacts rows need bytes/sha256 + role enum "
        "primary|supporting|log|fixture|control; evidence probes need fingerprint; "
        "downstream_consumers + residual_unknowns required; reviewer/manifest_registration "
        "extension props now forbidden). Two mechanically independent instruments agree: "
        "the reviewer battery (jsonschema Draft 2020-12 with local-ref resolver) and the "
        "repo's own command-center/receipt_validate.py (C2 schema-invalid REJECT on all "
        "12). Both-states calibration: the same admission gate ADMITS the wave-2-BUILT "
        "sibling receipts RES-0184, RES-0020, AUD-0043, TST-0007 clean (re-verified this "
        "run, rc=0 x4), so the gate is satisfiable and the debt is real receipt "
        "migration debt in this shard, not a broken instrument. Per the fail-closed "
        "contract: verdict FAIL with the precise failing check, receipts unchanged."
    ),
    "honest_caveats": [
        "Receipts NOT modified by either reviewer run: rewriting them would change the "
        "bytes the manifests hash and would make the reviewer the author of the artifact "
        "it approves. Remediation (rebuild the 12 receipts to the current "
        "receipt.schema.json following the proven sibling-shard pattern, re-register "
        "manifests, then fresh independent review) belongs to a builder lane.",
        "Prior run preserved verbatim at _reviewer10w2/reviewer_wave2_results.json + the "
        "superseded 19:35Z return embedded in git-less history of this file's prior "
        "content; this run's evidence at _reviewer10w2/rerun/ (battery + results).",
        "Secondary output_schemas (divergence-decision/probe-control/error-taxonomy/"
        "lockfile/permissions) were NOT validated this run: that advisory pass only "
        "executes when the primary receipt.schema.json check passes, which none did.",
        "Probes were re-run live and all exit 0, but several probes are themselves "
        "self-referential (they re-parse the receipt they certify); the schema gap is "
        "invisible to them because they predate the tightened schema - the two "
        "schema instruments above are the load-bearing signals.",
    ],
    "conclusion": (
        "FAILED:shard10-wave2-reviewer 0/12 closable (re-run, agrees with prior run) - "
        "all 12 units FAIL output-schema-valid against the CURRENT "
        "command-center/schema/receipt.schema.json (both instruments agree); probes "
        "24/24 exit 0; manifest sha256 12/12 match (CRLF->LF); receipts unchanged."
    ),
}

out = REPO / "_reviewer10w2" / "SHARD10-REVIEW-RETURN.json"
out.write_text(json.dumps(ret, indent=2), encoding="utf-8")
print("written:", out)
print("units:", len(units), "verdicts:", set(u["verdict"] for u in units))
print("err counts:", ERR_COUNTS)
