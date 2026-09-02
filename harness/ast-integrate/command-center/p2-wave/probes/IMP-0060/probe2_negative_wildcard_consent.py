"""Named probe 2: disguised widening, reviewer wildcard, version-specific consent.

NEGATIVE CONTROL: a widening disguised by reordering or renaming still blocks.
Reviewer constructs a wildcard-scope widening the fixture triples did not model.
Consent is persisted and is version-specific, not blanket.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import permission_diff as pd  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0060.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0060-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0060" not in text:
        print("FAILED:IMP-0060-probe2 sentinel absent")
        return 1

    inst, cand = pd.DISGUISED_WIDEN
    delta = pd.compute_delta(inst, cand)
    if delta.verdict != pd.WIDEN or "Bash" not in delta.added:
        print("FAILED:IMP-0060-probe2 disguised widening not detected")
        print(json.dumps(delta.__dict__, default=str)[:2000])
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="imp0060-p2-"))
    dest = tmp / "pkg.json"
    dest.write_text("OLD-BYTES\n", encoding="utf-8")
    store = pd.ConsentStore(tmp / "consent.json")
    blocked = pd.gate_update(
        package_id="demo.plugin",
        from_version="1.0.0",
        to_version="2.0.0",
        installed=inst,
        candidate=cand,
        consent_store=store,
        dest=dest,
        candidate_body=b"SHOULD-NOT-WRITE\n",
    )
    if blocked.proceed or blocked.wrote or dest.read_text(encoding="utf-8") != "OLD-BYTES\n":
        print("FAILED:IMP-0060-probe2 negative control wrote through a disguised widen")
        return 1

    # Reviewer wildcard the implementer's catalog triples did not include.
    r_inst, r_cand = pd.REVIEWER_WILDCARD_WIDEN
    r_delta = pd.compute_delta(r_inst, r_cand)
    if r_delta.verdict != pd.WIDEN:
        print("FAILED:IMP-0060-probe2 reviewer Network(*) wildcard did not widen")
        return 1
    dest_r = tmp / "reviewer.json"
    dest_r.write_text("OLD-BYTES\n", encoding="utf-8")
    r_gate = pd.gate_update(
        package_id="reviewer.plugin",
        from_version="0.9.0",
        to_version="1.0.0",
        installed=r_inst,
        candidate=r_cand,
        dest=dest_r,
        candidate_body=b"WILDCARD\n",
    )
    if r_gate.proceed or dest_r.read_text(encoding="utf-8") != "OLD-BYTES\n":
        print("FAILED:IMP-0060-probe2 reviewer wildcard was not blocked")
        return 1

    w_inst, w_cand = pd.REVIEWER_CREDENTIAL_WILDCARD
    w_delta = pd.compute_delta(w_inst, w_cand)
    if w_delta.verdict != pd.WIDEN:
        print("FAILED:IMP-0060-probe2 Write(*) wildcard did not widen")
        return 1

    # Consent is persisted, version-specific, not blanket.
    dest_c = tmp / "consented.json"
    dest_c.write_text("OLD-BYTES\n", encoding="utf-8")
    granted = pd.gate_update(
        package_id="demo.plugin",
        from_version="1.0.0",
        to_version="2.0.0",
        installed=inst,
        candidate=cand,
        consent_store=store,
        consent_action=True,
        dest=dest_c,
        candidate_body=b"CONSENTED\n",
    )
    if not granted.proceed or dest_c.read_text(encoding="utf-8") != "CONSENTED\n":
        print("FAILED:IMP-0060-probe2 explicit consent did not proceed")
        return 1
    if not store.path or not store.path.is_file():
        print("FAILED:IMP-0060-probe2 consent was not persisted")
        return 1
    disk = json.loads(store.path.read_text(encoding="utf-8"))
    if disk.get("blanket") is not False or len(disk.get("records") or []) != 1:
        print("FAILED:IMP-0060-probe2 consent store is blanket or empty")
        return 1
    dest_later = tmp / "later.json"
    dest_later.write_text("OLD-BYTES\n", encoding="utf-8")
    later = pd.gate_update(
        package_id="demo.plugin",
        from_version="2.0.0",
        to_version="3.0.0",
        installed=inst,
        candidate=cand,
        consent_store=store,
        dest=dest_later,
        candidate_body=b"LATER\n",
    )
    if later.proceed or dest_later.read_text(encoding="utf-8") != "OLD-BYTES\n":
        print("FAILED:IMP-0060-probe2 consent leaked across versions (blanket)")
        return 1

    out = {
        "probe": "probe2-negative-wildcard-consent",
        "unit_id": "IMP-0060",
        "pass": True,
        "disguised_widen_blocked": True,
        "disguised_wrote_nothing": True,
        "reviewer_wildcard_blocked": True,
        "reviewer_write_star_widens": True,
        "consent_persisted": True,
        "consent_version_specific": True,
        "consent_not_blanket": True,
        "reviewer_added": "Network(*) on a Write(src/**) baseline",
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print("SUCCESS:IMP-0060-probe2 negative control + reviewer wildcard + consent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
