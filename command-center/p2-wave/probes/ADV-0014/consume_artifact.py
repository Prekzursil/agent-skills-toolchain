"""ADV-0014 downstream consumer: fresh parse of the committed artifact."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(artifact_path: str) -> int:
    p = Path(artifact_path)
    doc = json.loads(p.read_text(encoding="utf-8"))
    checks = {
        "unit_id_is_ADV-0014": doc.get("unit_id") == "ADV-0014",
        "has_state": isinstance(doc.get("state"), str),
        "has_both_probe_evidence": len(doc.get("evidence", [])) >= 2,
        "answer_present": "answer" in doc.get("extensions", {}),
        "bytes_ge_min": p.stat().st_size >= doc.get("min_bytes_threshold", 1),
    }
    ok = all(checks.values())
    print(("SUCCESS:consume-ADV-0014 " if ok else "FAILED:consume-ADV-0014 ")
          + " ".join(f"{k}={v}" for k, v in checks.items()))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
