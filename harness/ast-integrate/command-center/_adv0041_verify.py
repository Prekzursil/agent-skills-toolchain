"""Independent final verification of ADV-0041's delivery. Reads only what is on disk.

This does NOT reuse _adv0041_deliver.py's in-memory state. It re-opens every file, re-runs
the contracted schema gate through a SECOND validator built directly on the jsonschema
package (not the repo CLI), re-runs the repo's predicate, and re-derives the manifest digest.
Every check prints its own detector control, because a check that cannot fail proves nothing.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ART = "command-center/adversarial/ADV-0041-path-and-identity-disclosure.json"
MAN = "command-center/UNIT-ARTIFACT-MANIFEST.json"
SCHEMA = "command-center/schema/privacy-dataflow.schema.json"
MUTANT = "command-center/_adv0041_control_receipt_MUTANT.json"


def hr(t: str) -> None:
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


def main() -> int:
    sys.path.insert(0, str(REPO / "platform" / "lib"))
    import schema_resolver  # noqa: E402

    raw = (REPO / ART).read_bytes()
    receipt = json.loads(raw.decode("utf-8"))
    failures: list[str] = []

    hr("A. ARTIFACT EXISTS, NON-EMPTY, PARSES")
    print(f"path   : {ART}")
    print(f"bytes  : {len(raw)}")
    print(f"sha256 : {hashlib.sha256(raw).hexdigest()}")
    print(f"parses : True (top-level keys={len(receipt)})")
    if len(raw) == 0:
        failures.append("artifact empty")

    hr("B. CONTRACTED GATE - independent jsonschema validator (NOT the repo CLI)")
    errs = schema_resolver.validate_artifact(receipt, SCHEMA)
    print("validator: jsonschema Draft202012Validator via schema_resolver.validate_artifact")
    print(f"errors   : {len(errs)}")
    for e in errs:
        print(f"  {e}")
    print("VERDICT  :", "SUCCESS:schema-valid" if not errs else "FAILED:schema-invalid")
    if errs:
        failures.append(f"schema errors={len(errs)}")

    hr("C. NEGATIVE CONTROL - the validator must REJECT a known-broken input")
    mut = json.loads((REPO / MUTANT).read_bytes().decode("utf-8"))
    merrs = schema_resolver.validate_artifact(mut, SCHEMA)
    print(f"mutant   : {MUTANT} (manifest_registration.registered flipped to false)")
    print(f"errors   : {len(merrs)}")
    for e in merrs:
        print(f"  {e}")
    print("CONTROL  :", "OK - fires on bad, silent on good" if merrs and not errs else "BROKEN")
    if not merrs:
        failures.append("negative control did not fire")

    hr("D. POSITIVE CONTROL - a known-good sibling the harness must PASS")
    sib = REPO / "platform/schema/examples/receipt.valid.example.json"
    if sib.is_file():
        sdata = json.loads(sib.read_bytes().decode("utf-8"))
        serrs = schema_resolver.validate_artifact(
            sdata, "command-center/schema/receipt.schema.json"
        )
        print(f"sibling  : {sib.relative_to(REPO)}")
        print(f"errors   : {len(serrs)}")
        for e in serrs[:5]:
            print(f"  {e}")
        print("CONTROL  :", "OK - harness is not simply failing everything" if not serrs else "SEE ERRORS")
        if serrs:
            failures.append("positive control sibling failed")
    else:
        print("sibling  : ABSENT - positive control NOT-CHECKED")
        failures.append("positive control missing")

    hr("E. MANIFEST REGISTRATION - re-derived off disk")
    man = json.loads((REPO / MAN).read_bytes().decode("utf-8"))
    entry = [e for e in man["artifacts"] if e["path"] == ART]
    print(f"manifest : {MAN}")
    print(f"entries  : {len(man['artifacts'])}")
    if not entry:
        print("ENTRY    : ABSENT")
        failures.append("manifest entry absent")
    else:
        rec = entry[0]["sha256"]
        actual = hashlib.sha256(raw).hexdigest()
        print(f"recorded : {rec}")
        print(f"on disk  : {actual}")
        print(f"MATCH    : {rec == actual}")
        if rec != actual:
            failures.append("manifest digest drift")
    print(f"receipt registered flag: {receipt['manifest_registration']['registered']}")
    print(f"receipt manifest_path  : {receipt['manifest_registration']['manifest_path']}")

    hr("F. BOTH NAMED PROBES FROM evidence_requirement, VERBATIM")
    probes = [p for e in receipt["evidence"] for p in e.get("probes", [])]
    withraw = [p for p in probes if isinstance(p.get("raw_output"), str) and p["raw_output"].strip()]
    print(f"total probes                 : {len(probes)}")
    print(f"probes carrying raw_output   : {len(withraw)}")
    p1 = receipt["evidence"][0]
    p2 = receipt["evidence"][2]
    print(f"PROBE 1 (static bundle scan) : evidence[0] verdict={p1['verdict']} "
          f"probes={len(p1['probes'])} raw_bytes={sum(len(x['raw_output']) for x in p1['probes'])}")
    print(f"PROBE 2 (runtime rendering)  : evidence[2] verdict={p2['verdict']} "
          f"probes={len(p2['probes'])} raw_bytes={sum(len(x['raw_output']) for x in p2['probes'])}")
    if len(withraw) != len(probes):
        failures.append("some probes lack raw_output")

    hr("G. tests_required CONTROL + verdict-per-target")
    t0 = receipt["tests"][0]
    print(f"catalogued control test: {t0['name'][:90]}")
    print(f"  result: {t0['result']}")
    bad_tests = [t["id"] for t in receipt["tests"] if t["result"] != "PASS"]
    print(f"tests total={len(receipt['tests'])} non-PASS={bad_tests or 'none'}")
    ncs = receipt["negative_controls"]
    bad_nc = [c["id"] for c in ncs if not (c["fired_on_bad_state"] and c["silent_on_good_state"])]
    print(f"negative controls={len(ncs)} not-both-states={bad_nc or 'none'}")
    targets = receipt["report"]["verdict_per_enumerated_target"]
    allowed = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
    bad_v = [t["target"] for t in targets if t.get("verdict") not in allowed]
    print(f"enumerated targets={len(targets)} with exactly-one allowed verdict="
          f"{len(targets) - len(bad_v)} bad={bad_v or 'none'}")
    if bad_tests or bad_nc or bad_v:
        failures.append("tests/controls/verdicts incomplete")

    hr("H. SECOND INSTRUMENT - the repo's completion predicate (out of contract)")
    proc = subprocess.run(
        [sys.executable, "platform/lib/completion_predicate.py", ART, "--output-schema", SCHEMA],
        cwd=REPO, capture_output=True, text=True,
    )
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-1]
    print(tail)
    print("(reported, NOT folded into the contract verdict - see the artifact's residuals)")

    hr("VERDICT")
    if failures:
        print("FAILED:ADV-0041 " + "; ".join(failures))
        return 1
    print("SUCCESS:ADV-0041")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
