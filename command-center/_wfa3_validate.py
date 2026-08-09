"""wfa-3 read-back validation of platform/registry/workflow-candidates-3.json.

Loads the artifact FRESH from disk (never from the builder's memory) and asserts the
contract mechanically. Ends with a BOTH-STATES control: the same checker is run against a
deliberately broken copy and must FAIL there, otherwise a pass here would measure nothing.
"""

import copy
import json
import re
import sys
from pathlib import Path

ART = Path(
    "C:/Users/Prekzursil/source/ast-integrate/platform/registry/workflow-candidates-3.json"
)

VOCAB = {
    "ADOPT-AS-IS",
    "ADOPT-WITH-WRAPPER",
    "TRANSLATE",
    "REPAIR",
    "EXTEND",
    "MERGE",
    "COMPOSE",
    "CLEAN-ROOM-REIMPLEMENT",
    "DISTILL",
    "SPECIALIZE",
    "GENERALIZE",
    "REBUILD-FROM-SPEC",
    "RETIRE",
    "REJECT",
    "UNKNOWN-NEEDS-PROBE",
}
PLACEHOLDER = re.compile(r"UNKNOWN - not yet measured|SKELETON|not yet measured", re.I)
ANCHOR = re.compile(
    r"(C:/|C:\\\\|C:\\|https?://|\.md:\d+|~/|LICENSE|SKILL\.md|plugin\.json|marketplace\.json|settings\.json)"
)


def check(rows):
    """Return a list of violation strings. Empty list == contract satisfied."""
    v = []
    if not isinstance(rows, list):
        return ["top level is not a JSON array"]
    manifest = [r for r in rows if r.get("_manifest")]
    cands = [r for r in rows if not r.get("_manifest")]
    if len(manifest) != 1:
        v.append(f"expected exactly 1 manifest row, found {len(manifest)}")
    counted = [r for r in cands if r.get("counts_toward_range") is True]
    rejected = [r for r in cands if r.get("counts_toward_range") is False]

    if len(counted) != 32:
        v.append(f"counted candidates = {len(counted)}, expected 32")

    ids = [r.get("id") for r in cands]
    if len(set(ids)) != len(ids):
        v.append("duplicate candidate ids")
    if any(not i for i in ids):
        v.append("a candidate has no id")

    idx = sorted(r.get("range_index") for r in counted)
    if idx != list(range(65, 97)):
        v.append(f"counted range_index set is not exactly 65..96: {idx}")

    for r in cands:
        rid = r.get("id", "<no-id>")
        for field in (
            "name",
            "family",
            "candidate_kind",
            "provenance",
            "license",
            "maintenance",
            "classification",
            "classification_rationale",
            "task_fit",
            "stages",
            "roles",
            "tools",
            "stop_rules",
            "failure_behaviour",
            "mechanisms",
        ):
            if field not in r:
                v.append(f"{rid}: missing required field '{field}'")
        cls = r.get("classification")
        if cls not in VOCAB:
            v.append(f"{rid}: classification '{cls}' is not in the 15-term vocabulary")
        prov = r.get("provenance") or {}
        if not isinstance(prov, dict) or not prov:
            v.append(f"{rid}: provenance is empty")
        else:
            blob = json.dumps(prov)
            if not ANCHOR.search(blob):
                v.append(
                    f"{rid}: provenance carries no real anchor (path/URL/file:line)"
                )
        lic = r.get("license") or {}
        if not isinstance(lic, dict) or not lic.get("name"):
            v.append(f"{rid}: license has no name")
        elif r.get("counts_toward_range") and not (
            lic.get("source_file") or lic.get("adoption_constraint")
        ):
            v.append(
                f"{rid}: license has no source_file (licence must cite where it was read)"
            )
        if not (r.get("maintenance") or {}).get("state"):
            v.append(f"{rid}: maintenance has no state")
        if PLACEHOLDER.search(json.dumps(r)):
            v.append(f"{rid}: still contains skeleton placeholder text")
        if not r.get("confidence") and r.get("counts_toward_range"):
            v.append(f"{rid}: counted row has no confidence band")

    if manifest:
        m = manifest[0]
        if m.get("candidates_counted_toward_range") != len(counted):
            v.append("manifest count disagrees with the actual counted rows")
        if m.get("rows_total") != len(cands):
            v.append("manifest rows_total disagrees with the actual candidate rows")
        if m.get("rows_rejected_not_counted") != len(rejected):
            v.append("manifest rejected count disagrees")
    return v


def main():
    raw = ART.read_text(encoding="utf-8")
    rows = json.loads(raw)  # fresh parse from disk
    print(f"file      : {ART}")
    print(f"bytes     : {ART.stat().st_size}")
    print(f"json type : {type(rows).__name__}, len={len(rows)}")

    viol = check(rows)
    cands = [r for r in rows if not r.get("_manifest")]
    counted = [r for r in cands if r.get("counts_toward_range") is True]
    rejected = [r for r in cands if r.get("counts_toward_range") is False]

    print(f"manifest rows      : {len([r for r in rows if r.get('_manifest')])}")
    print(f"candidate rows     : {len(cands)}")
    print(f"COUNTED candidates : {len(counted)}")
    print(f"rejected (recorded): {len(rejected)} -> {[r['id'] for r in rejected]}")
    hist = {}
    for r in cands:
        hist[r["classification"]] = hist.get(r["classification"], 0) + 1
    print(f"classifications    : {hist}")
    kinds = {}
    for r in counted:
        kinds[r["candidate_kind"]] = kinds.get(r["candidate_kind"], 0) + 1
    print(f"counted by kind    : {kinds}")
    fams = {}
    for r in counted:
        fams[r["family"]] = fams.get(r["family"], 0) + 1
    print(f"counted by family  : {fams}")
    nc = sum(1 for r in cands if "NOT-CHECKED" in json.dumps(r))
    print(f"rows carrying an explicit NOT-CHECKED: {nc}")
    corr = sum(
        1
        for r in cands
        if r.get("corrections_vs_prior") or "CORRECTION" in json.dumps(r)
    )
    print(f"rows carrying a correction to prior  : {corr}")

    print()
    if viol:
        print(f"VIOLATIONS ({len(viol)}):")
        for x in viol[:40]:
            print("  -", x)
    else:
        print(
            "[PASS] contract satisfied: 32 counted candidates, indices exactly 65..96, every row has a "
            "real provenance anchor, a licence with its source, a maintenance state, a vocabulary "
            "classification and a confidence band; no placeholder text survives."
        )

    # ---- BOTH-STATES CONTROL: the checker must FIRE on a known-broken copy ----
    print("\n=== detector control (both-states) ===")
    broken = copy.deepcopy(rows)
    target = next(
        r for r in broken if not r.get("_manifest") and r.get("counts_toward_range")
    )
    target["classification"] = "TOTALLY-MADE-UP"
    target["provenance"] = {"vibes": "somewhere on the internet"}
    target["license"] = {"name": "probably fine"}
    target["name"] = "UNKNOWN - not yet measured"
    broken.remove(
        next(
            r
            for r in broken
            if not r.get("_manifest")
            and r.get("counts_toward_range")
            and r["id"] != target["id"]
        )
    )
    bviol = check(broken)
    print(f"violations on the BROKEN copy: {len(bviol)}")
    for x in bviol[:8]:
        print("  -", x)
    control_ok = len(bviol) > 0 and len(viol) == 0
    print(
        f"\ncontrol verdict: checker is silent on the real file ({len(viol)}) and fires on the broken one "
        f"({len(bviol)}) -> {'MEANINGFUL' if control_ok else 'NOT MEANINGFUL'}"
    )

    if viol or not bviol:
        print(
            f"\nFAILED:wfa-3-validate real_violations={len(viol)} broken_violations={len(bviol)}"
        )
        sys.exit(1)
    print(
        f"\nSUCCESS:wfa-3-validate {len(counted)} counted candidates read back from disk; "
        "detector proven in both states"
    )


if __name__ == "__main__":
    main()
