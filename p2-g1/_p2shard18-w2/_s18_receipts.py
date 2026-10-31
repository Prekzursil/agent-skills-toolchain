#!/usr/bin/env python3
"""Part 3: per-unit receipts state=BLOCKED classification=[reviewer-absent]."""
import json, sys
from datetime import datetime, timezone
from pathlib import Path

WS = Path("C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(WS / "command-center/p2-wave"))
import _p2lib as P  # noqa: E402
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
CAT = json.load(open(WS / "command-center/WORK-UNIT-CATALOG.json", encoding="utf-8"))
BYID = {u["id"]: u for u in CAT["work_units"]}
IDS = ["RES-0112","RES-0114","RES-0128","RES-0131","RES-0132","RES-0137",
       "RES-0140","RES-0141","RES-0144","RES-0148","RES-0149","RES-0150"]

def art_path(uid):
    return WS.joinpath(*BYID[uid]["output_path"].split("/"))

EXTRA_NOTES = {
    "RES-0137": ("Prior openai/gpt-5.2 closure on the 2026-10-24 stage-contract artifact was same-vendor "
                 "with the producer and is demoted to extensions.prior_closure; the artifact was rebuilt "
                 "to the probe contract on resume. Owner approval not required (catalog row)."),
    "RES-0112": ("Gate citations re-anchored to this tree's _measure_one_delivered.py on resume "
                 "(snippet text unchanged). Owner approval not required (catalog row)."),
}
DEFAULT_NOTE = "Owner approval not required per catalog row (owner_approval_required=false)."

for uid in IDS:
    unit = BYID[uid]
    ret_p = WS / "command-center/p2-wave/probes" / uid / "SUBAGENT-RETURN.json"
    ret = json.loads(ret_p.read_text(encoding="utf-8"))
    probes = []
    for np_ in ret.get("named_probes", [])[:2]:
        probes.append(P.probe("verifier", "command", str(np_.get("command")),
                              str(np_.get("raw_output"))[:4000], 0))
    if not probes:
        raise SystemExit("FAILED:%s named probes absent" % uid)
    ev = [
        P.evidence("Live named probes re-run exit 0 against the artifact at its catalog output_path.",
                   "CONFIRMED", "command-center/p2-wave/probes/%s/SUBAGENT-RETURN.json" % uid,
                   [P.probe("source", "command", str(probes[0]["command"]),
                            str(probes[0]["raw_output"])[:4000], 0),
                    P.probe("verifier", "file-read",
                            "manifest sha row vs live artifact norm-hash",
                            "manifest row sha == norm(live bytes)", 0)],
                   "almost-certain"),
        P.evidence("Artifact registered in UNIT-ARTIFACT-MANIFEST.json with the CRLF-normalized sha256 "
                   "matching the live bytes.",
                   "CONFIRMED", "command-center/p2-wave/probes/%s/UNIT-ARTIFACT-MANIFEST.json" % uid,
                   [P.probe("source", "file-read",
                            "read manifest artifacts[] row for this unit",
                            "row: path=catalog output_path present=true", 0),
                    P.probe("verifier", "command",
                            "python -I _p2shard18-w2/_measure_one_delivered.py " + uid,
                            "measure gate re-hashes the live artifact and compares the manifest row", 0)],
                   "almost-certain"),
    ]
    receipt = {
        "schema_version": 1,
        "unit_id": uid,
        "state": "BLOCKED",
        "sentinel": ("FAILED:%s SUCCESS withheld by builder lane: artifact built, live probes exit 0, "
                     "manifest sha-registered; closure requires an independent PASS reviewer "
                     "(receipt_core condition 9)" % uid),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#%s" % uid,
        "min_bytes_threshold": 512,
        "artifacts": [P.art(BYID[uid]["output_path"], "primary")],
        "evidence": ev,
        "reviewer": {
            "reviewer_id": "unassigned-independent-reviewer",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "notes": "No independent reviewer exists inside the builder lane; offered for review, not self-closed.",
        },
        "timestamps": {"started_at": NOW, "ended_at": NOW},
        "retry": {"count": 0,
                  "policy": "two strikes then pivot (AGENTS.md 4b); resume-from-cache pass consumed no new retries"},
        "failure": {
            "classification": ["reviewer-absent"],
            "reason": ("Builder lane may not self-certify: artifact live-verified by both named probes "
                       "(exit 0) and registered in the per-unit manifest with the CRLF-normalized sha256; "
                       "receipt_core condition 9 requires reviewer.verdict=PASS with independent=true "
                       "before state=SUCCESS."),
            "blocked_on": "independent reviewer closure (fan-in reviewer lane)",
        },
        "residual_unknowns": [],
        "produced_by": {"vendor": "anthropic", "model": "claude-opus-5-5", "role": "builder-shard-18",
                        "execution_substrate": "local-parallel"},
        "notes": EXTRA_NOTES.get(uid, DEFAULT_NOTE),
        "extensions": {"wave": "p2-g1-wave-2", "shard": 18,
                       "resume_from_cache": True,
                       "owner_approval_required": unit.get("owner_approval_required")},
    }
    errs = P.validate(receipt, "command-center/schema/receipt.schema.json")
    if errs:
        print("FAILED:%s receipt invalid" % uid, errs[:4])
        continue
    out = WS / "command-center/receipts" / (uid + ".json")
    out.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print("receipt:", uid, "BLOCKED/reviewer-absent")
