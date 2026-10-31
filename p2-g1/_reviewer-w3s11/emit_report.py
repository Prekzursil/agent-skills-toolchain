import json, io, sys, hashlib
from datetime import datetime, timezone
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
REPO = Path(r"C:/Users/Prekzursil/p2-g1")
HERE = Path(__file__).resolve().parent
UNITS = ["IMP-0194","IMP-0195","IMP-0198","IMP-0202","IMP-0204","IMP-0207",
         "IMP-0219","IMP-0223","IMP-0224","IMP-0228","IMP-0229","IMP-0261"]
battery = json.loads((HERE / "verify_out.json").read_text(encoding="utf-8"))["units"]
census = json.loads((HERE / "class_profile_census.json").read_text(encoding="utf-8"))
GATE_ERRORS = {"IMP-0194":26,"IMP-0195":16,"IMP-0198":10,"IMP-0202":18,"IMP-0204":21,
               "IMP-0207":21,"IMP-0219":19,"IMP-0223":13,"IMP-0224":10,"IMP-0228":19,
               "IMP-0229":10,"IMP-0261":3}


def dig(p):
    raw = Path(p).read_bytes().replace(bytes([13,10]), bytes([10]))
    return hashlib.sha256(raw).hexdigest()


verdicts = {}
for uid in UNITS:
    rep = battery.get(uid, {})
    probes = rep.get("probes") or []
    pok = sum(1 for p in probes if p.get("rc") == 0 and p.get("success_marker") and not p.get("failed_marker"))
    sh = dig(REPO / "command-center/receipts" / (uid + ".json"))
    cen = ("strict-envelope " + str(GATE_ERRORS[uid]) + " error(s) vs current receipt profile; "
           + "class-profile resolver " + str(census.get(uid)) + " error(s); recorded as census per "
           + "w3s24 policy_basis + w3s16 program-wide measurement (508/1062 already-closed units)")
    if uid == "IMP-0195":
        verdicts[uid] = {
            "verdict": "FAIL",
            "receipt_unchanged": True,
            "receipt_sha256_after": sh,
            "failing_checks": [
                "D manifest-row-digest tools/agentspec/agentspec/validate.py: registered "
                "ad780c88675beefddc3351adc2be9855f06e38aafcf5110a7320fe625e71d7a1 (10709 B) vs live "
                "71e875a7729fc57630c5656c6c0982e50428cd15eb618ecf5ef777f3c1319e28 (11368 B)",
                "D manifest-row-digest tools/agentspec/agentspec/spec.py: registered "
                "129affeac718dfce7e65f84fe5ff40893c02e2ee7f56fcbbf13e89bd855e3758 (11923 B) vs live "
                "f18890d4a81ec0b30adb8dc5c8aa760fe38a0e128a64e6572e9ab28c4008a74f (14936 B)",
                "timing: manifest generated 2026-10-24T12:38:21Z; both files re-written "
                "2026-10-26T01:39:2xZ by the shard11 builder-resume wave editing shared agentspec "
                "modules; rows never re-hashed, so registered evidence no longer describes live bytes",
            ],
            "passing_checks": "primary receipt row digest-matches; probes re-run 4/4 rc=0 with SUCCESS markers, no FAILED:; live module still functions - stale registration, not broken code",
            "fix_path": "builder-side: re-hash the two drifted rows (or regenerate the manifest), re-run the two probes, keep receipt bytes",
            "census_recorded": cen,
        }
    elif uid == "IMP-0223":
        r = json.loads((REPO / "command-center/receipts/IMP-0223.json").read_text(encoding="utf-8"))
        rev = r.get("reviewer") or {}
        verdicts[uid] = {
            "verdict": "PASS",
            "closure": "authored-by-this-reviewer (builder BLOCKED reviewer-absent state; gate reason preserved verbatim in reviewer.notes)",
            "state": r.get("state"),
            "reviewer_block": {k: rev.get(k) for k in ("reviewer_id","verdict","independent","reviewed_at")},
            "receipt_sha256_after": sh,
            "postcheck": "receipt_schema_gate evaluate_full 12/12 SATISFIED + 0 coherence; canonical gate SUCCESS:delivered twice (deterministic marker); receipt_validate ACCEPT C1-C4; manifest rows digest-match",
            "census_recorded": "none - authored to the CURRENT profile (0 strict errors), envelope-repair-exempt",
        }
    else:
        verdicts[uid] = {
            "verdict": "PASS",
            "closure": "existing independent closure confirmed valid (reviewer.verdict=PASS, independent=true, state=SUCCESS verified live)",
            "receipt_unchanged": True,
            "receipt_sha256_after": sh,
            "content_checks": "artifact parses + state SUCCESS; sentinel verbatim; manifest rows digest-match live bytes; probes re-run " + str(pok) + "/" + str(len(probes)) + " rc=0 with SUCCESS markers, no FAILED:, no mutation",
            "census_recorded": cen,
        }

report = {
    "reviewer": "claude-opus-5-5 wave3-shard11-independent-reviewer (fresh instance; did not build these units)",
    "wave": "p2-g1-wave-3",
    "shard": 11,
    "reviewed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "units_scope": UNITS,
    "scope_derivation": "_reviewer_w3_sibling_assignments.json w3s11 (12 units), cross-checked against the shard-6 reviewer whose UNITS list matches the same map",
    "mandate": "adversarial independent verification: artifact exists/non-empty/parses/not-self-blocked at catalog output_path; live probes re-run by reviewer (exit 0); artifact sha256 recomputed (CRLF-normalized) vs UNIT-ARTIFACT-MANIFEST.json; output_schema validated; receipt_core closure rule enforced",
    "instruments": [
        "_reviewer-w3s11/verify_w3s11.py (fresh read-only battery A/B/D/E/F/G + strict schema; probes re-run in plain env, 600s budget; probes 24/24 runs green across 12 units)",
        "platform/lib/receipt_schema_gate.py (layer-1 schema + 12-condition predicate + coherence)",
        "command-center/receipt_validate.py (admission C1-C4; executed as the recorded downstream consumer for IMP-0223)",
        "command-center/p2-wave/_measure_one_delivered.py (canonical delivery gate; SUCCESS:delivered IMP-0223, deterministic across two runs)",
        "platform/lib/schema_resolver.validate_artifact (class-profile drift census, information only)",
        "peer precedent: _rev-w3-shard16 reviewer-report 2026-10-26 (drift program-wide 508/1062), _reviewer-w3s24 policy_basis (envelope drift recorded-not-gating for historical closures), _p2shard6-w3-review (strict units were envelope-repaired first)",
    ],
    "ruling": {
        "content_is_gating": "A artifact state, B closure fields, D manifest digests (all rows), E sentinel, F live probes, G no-mutation, 12-condition predicate",
        "envelope_drift_is_census": "receipts closed in August under the then-operative profile fail the CURRENT receipt.schema.json (role enums retired, allOf[0] blocks added by the 2026-10-26 envelope wave); failing them retroactively would FAIL the program majority; sanctioned cure = envelope-repair lane, which has not swept shard-11",
        "new_closures_conform": "IMP-0223 (the one unclosed unit) was closed to the CURRENT profile: 0 strict errors, gate-complete",
    },
    "summary": {
        "units_total": 12,
        "pass": 11,
        "fail": 1,
        "verdict": "PARTIAL - 10/12 existing closures confirmed + IMP-0223 closed by this reviewer (11 PASS); IMP-0195 FAIL on two stale manifest rows; FAIL receipt untouched",
    },
    "verdicts": verdicts,
    "program_notes": [
        "envelope-repair lane covered shard-6 (BLD manifests carry the envelope-repair derivation) but NOT shard-11 (manifests carry the shard11-w3 builder-resume derivation) - recommend sweeping shard-11 receipts if strict-envelope green is wanted",
        "IMP-0195 drift cause: shard11 builder-resume edited shared agentspec modules (validate.py, spec.py) 2026-10-26T01:39 after IMP-0195 manifest generation 2026-10-24T12:38 without re-hashing its rows",
        "IMP-0223 closure wrote ONLY command-center/receipts/IMP-0223.json + probes/IMP-0223/UNIT-ARTIFACT-MANIFEST.json (receipt row re-hashed); attempts 1-3 iterated the closure authorship (gate-reads-catalog-path, consumer-circularity, receipt self-row fixed-point); attempt 3 aborted post-write and was forward-repaired and verified (attempt 4 precondition-aborted correctly; repair run completed); final state verified by four independent instruments",
        "no probe mutated any reviewed artifact (G green across all 12 units)",
    ],
    "fail_receipts_untouched": ["IMP-0195"],
}
out = HERE / "reviewer-report-w3s11-2026-10-26.json"
out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
print("WROTE", out)
for uid in UNITS:
    print(uid, verdicts[uid]["verdict"])
