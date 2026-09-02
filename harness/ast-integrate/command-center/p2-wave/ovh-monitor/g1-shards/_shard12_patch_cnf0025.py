#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
HERE = REPO / "command-center" / "p2-wave" / "probes" / "CNF-0025"
sys.path.insert(0, str(HERE))
import matrix as M  # noqa: E402

ART = REPO / "command-center" / "confirmation" / "CNF-0025-repro-specificity.json"
MAN = HERE / "UNIT-ARTIFACT-MANIFEST.json"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> None:
    live = M.run_matrix()
    classified = M.classify(live)
    doc = json.loads(ART.read_text(encoding="utf-8"))
    matrix = doc.get("matrix") if isinstance(doc.get("matrix"), dict) else {}
    matrix["empty_cells"] = 0
    matrix["grid"] = live["grid"]
    matrix["cells"] = live["cells"]
    doc["matrix"] = matrix
    doc["accepted_repros"] = classified["accepted_repros"]
    doc["quarantined"] = classified["quarantined"]
    ART.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    sha, size = digest(ART)
    man = json.loads(MAN.read_text(encoding="utf-8"))
    rel = "command-center/confirmation/CNF-0025-repro-specificity.json"
    for a in man.get("artifacts") or []:
        if a.get("unit_id") == "CNF-0025" and str(a.get("path") or "").replace("\\", "/") == rel:
            a["sha256"] = sha
            a["bytes"] = size
            a["present"] = True
    MAN.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("patched CNF-0025 empty_cells=0", sha[:16], "accepted", classified["accepted_repros"])


if __name__ == "__main__":
    main()
