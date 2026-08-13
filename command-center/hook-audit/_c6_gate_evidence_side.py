"""Control the citation gate from the OTHER side.

`--self-test` mutates the EXPECTED value, i.e. it simulates the DOC drifting. But the
defect that actually happened (C3) was the EVIDENCE drifting: a probe re-run deleted the
timing key while the document sat unchanged. Those are opposite sides of the same
comparison, and a control that only exercises one of them has not been shown to catch the
other.

This tampers with a committed evidence file in the two shapes C1/C3 actually took --
(a) a key deleted, (b) a value changed -- runs the real gate, requires a RED for each, and
restores the byte-exact original, verifying the sha256 before and after. Fails closed and
restores if anything goes wrong.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
GATE = REPO / "command-center" / "hook-audit" / "check_citations.py"
TARGET = REPO / "command-center" / "hook-audit" / "N1-LIVE-STATE-E2E.json"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


UNBACKED = re.compile(r"(\d+)\s+citations checked,\s+(\d+)\s+unbacked")


def gate() -> tuple[int, int]:
    """Return (exit_code, unbacked_count).

    The COUNT, not just the exit code, is what makes this control differential. This probe
    cannot require a green baseline: the document cites this probe's own output, so on a
    first run that artifact does not exist yet and the baseline is legitimately red. Worse,
    a red baseline for ANY unrelated reason would mask the thing under test -- a gate that
    was already failing would "go red" when tampered and prove nothing. Comparing unbacked
    COUNTS isolates the effect of the tamper from whatever else is broken.
    """
    p = subprocess.run(
        [sys.executable, str(GATE)], capture_output=True, cwd=str(REPO), timeout=300
    )
    m = UNBACKED.search(p.stdout.decode("utf-8", "replace"))
    return p.returncode, (int(m.group(2)) if m else -1)


def main() -> int:
    original = TARGET.read_bytes()
    before = sha(TARGET)
    results = {}
    try:
        baseline, base_n = gate()
        results["baseline_untampered"] = baseline
        results["baseline_unbacked"] = base_n
        if base_n < 0:
            print("FAILED:c6-gate-evidence could not parse the gate's own count -- the")
            print("       comparison below would be meaningless, so nothing is claimed")
            return 1

        # (a) DELETE the cited key -- the C3 shape.
        blob = json.loads(original.decode("utf-8"))
        gone = json.loads(json.dumps(blob))
        gone["filter_on"].pop("wall_ms", None)
        TARGET.write_text(json.dumps(gone, indent=2), encoding="utf-8")
        results["key_deleted"], results["key_deleted_unbacked"] = gate()

        # (b) CHANGE the cited value -- the silent-drift shape.
        moved = json.loads(json.dumps(blob))
        moved["filter_on"]["wall_ms"] = 99999.9
        TARGET.write_text(json.dumps(moved, indent=2), encoding="utf-8")
        results["value_changed"], results["value_changed_unbacked"] = gate()
    finally:
        TARGET.write_bytes(original)

    after = sha(TARGET)
    results["sha_before"] = before
    results["sha_after"] = after
    results["restored_byte_exact"] = before == after
    # DERIVED, and deliberately the only fields the document cites. The raw baseline is
    # NOT citable: the doc cites this artifact, so the artifact citing its own baseline
    # would need three runs to converge on a fixed point. These two are stable.
    results["tamper_detected_key_deleted"] = (
        results["key_deleted"] != 0
        and results["key_deleted_unbacked"] > results["baseline_unbacked"]
    )
    results["tamper_detected_value_changed"] = (
        results["value_changed"] != 0
        and results["value_changed_unbacked"] > results["baseline_unbacked"]
    )
    results["reading"] = (
        "each tamper produced a NEW unbacked citation relative to the same run's own "
        "baseline -- so the gate sees drift on the EVIDENCE side, not only on the "
        "document side that --self-test exercises"
    )
    (TARGET.parent / "C6-GATE-EVIDENCE-SIDE.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    print(json.dumps(results, indent=2))

    if before != after:
        print("FAILED:c6-gate-evidence the evidence file was NOT restored byte-exact")
        return 1
    base_n = results["baseline_unbacked"]
    bad = [
        k
        for k in ("key_deleted", "value_changed")
        if results[k] == 0 or results[k + "_unbacked"] <= base_n
    ]
    if bad:
        print(f"FAILED:c6-gate-evidence no NEW failure appeared for {bad} -- the gate")
        print(
            "       cannot see evidence-side drift, the direction C1/C3 actually took"
        )
        return 1
    print("both evidence-side shapes went RED, and the file is byte-identical again")
    print("SUCCESS:c6-gate-evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
