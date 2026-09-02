#!/usr/bin/env python3
"""Regenerate RES-0144 / RES-0165 measurements and SYN-0041 report. Not a G-1 measure."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")


def dump(path: Path, doc: dict) -> None:
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    path.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))


def res0144() -> None:
    probe = REPO / "command-center/p2-wave/probes/RES-0144"
    sys.path.insert(0, str(probe))
    import score as S  # noqa: E402

    live = S.run()
    rel = "command-center/research/evidence-quality/RES-0144-two-axis-source-quality-rubric.json"
    path = REPO / rel
    doc = json.loads(path.read_text(encoding="utf-8"))
    ka = live["kappa_authority"]
    ki = live["kappa_independence"]
    kj = live["kappa_joint"]
    doc["measurements"] = {
        "sample_size": 40,
        "kappa_authority": ka["kappa"] if isinstance(ka, dict) else ka,
        "kappa_independence": ki["kappa"] if isinstance(ki, dict) else ki,
        "kappa_joint": kj["kappa"] if isinstance(kj, dict) else kj,
    }
    cal = doc.get("calibration") if isinstance(doc.get("calibration"), dict) else {}
    if not cal:
        cal = (doc.get("report") or {}).get("calibration") if isinstance(doc.get("report"), dict) else {}
        cal = dict(cal) if isinstance(cal, dict) else {}
    cal["authority_disagree_n"] = ka["disagree_n"] if isinstance(ka, dict) else cal.get("authority_disagree_n")
    cal["independence_disagree_n"] = ki["disagree_n"] if isinstance(ki, dict) else cal.get("independence_disagree_n")
    doc["calibration"] = cal
    if "SUCCESS:RES-0144" not in json.dumps(doc):
        doc["completion_sentinel"] = "SUCCESS:RES-0144"
    dump(path, doc)
    print(f"RES-0144 measurements sample_size=40 kappa_a={doc['measurements']['kappa_authority']}")


def res0165() -> None:
    probe = REPO / "command-center/p2-wave/probes/RES-0165"
    if str(probe) in sys.path:
        sys.path.remove(str(probe))
    sys.path.insert(0, str(probe))
    import measure as M  # noqa: E402
    from contract import SENTINEL  # noqa: E402

    live = M.run()
    flat = live["flatten"]
    floor = live["noise_floor"]
    rel = (
        "command-center/research/deep-research-design/"
        "RES-0165-researcher-count-diminishing-returns.json"
    )
    path = REPO / rel
    doc = json.loads(path.read_text(encoding="utf-8"))
    meas = doc.get("measurements") if isinstance(doc.get("measurements"), dict) else {}
    meas["flatten"] = {
        "landscape_n": flat["landscape_n"],
        "targeted_n": flat["targeted_n"],
        "targeted_flattens_earlier": flat["targeted_flattens_earlier"],
        "landscape_contradiction_coverage_at_flatten": flat["landscape_contradiction_coverage_at_flatten"],
        "targeted_contradiction_coverage_at_flatten": flat["targeted_contradiction_coverage_at_flatten"],
    }
    meas["noise_floor"] = {
        "clustered_added": floor["clustered_added"],
        "naive_added": floor["naive_added"],
    }
    doc["measurements"] = meas
    if SENTINEL not in json.dumps(doc):
        doc["completion_sentinel"] = SENTINEL
    dump(path, doc)
    print(
        f"RES-0165 flatten landscape_n={flat['landscape_n']} "
        f"targeted_n={flat['targeted_n']} clustered_added={floor['clustered_added']}"
    )


def syn0041() -> None:
    probe = REPO / "command-center/p2-wave/probes/SYN-0041"
    # Drop other probe dirs so generate imports its siblings.
    sys.path[:] = [p for p in sys.path if "p2-wave" not in p.replace("\\", "/") or p == str(probe)]
    sys.path.insert(0, str(probe))
    from generate import OUT_REL, build_report, dumps  # noqa: E402

    doc = build_report(REPO)
    text = dumps(doc)
    out = REPO / OUT_REL
    out.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))
    print(f"SYN-0041 wrote {OUT_REL} bytes={len(text.encode('utf-8'))}")


def main() -> int:
    res0144()
    res0165()
    syn0041()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
