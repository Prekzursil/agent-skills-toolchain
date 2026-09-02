#!/usr/bin/env python3
"""Named probe 1: idempotent canonical round-trip over every fixture/node type.

Signal: export(import(export(w))) == export(w) byte-for-byte for every fixture,
including Subworkflow, Loop, HumanCheckpoint, and DynamicFanOut.

Both-states control: a one-byte content mutation of an export must fail equality;
the unmutated twin must pass. Dropping a Phase-7 kind from the loaded set must
fail the required-kinds assertion.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))
sys.path.insert(0, str(HERE))

from agentspec.canonical import (  # noqa: E402
    CanonicalError,
    export,
    import_workflow,
    round_trip_bytes,
    round_trip_workflow,
)
from agentspec.spec import NEW_NODE_KINDS  # noqa: E402
from scenario import FIXTURES, kinds_in, required_kinds  # noqa: E402

FIXDIR = HERE / "fixtures"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0146-probe1 {msg}")
    return 1


def load_file_fixtures() -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    if not FIXDIR.is_dir():
        return out
    for path in sorted(FIXDIR.glob("*.json")):
        out[path.stem] = path.read_bytes()
    return out


def main() -> int:
    required = required_kinds()
    union_kinds: set[str] = set()
    rows: list[dict] = []

    for name, wf in FIXTURES.items():
        e1 = export(wf)
        if b"\r" in e1:
            return _fail(f"export-contains-cr {name}")
        if not e1.endswith(b"\n"):
            return _fail(f"export-missing-lf {name}")
        e2 = round_trip_workflow(wf)
        if e1 != e2:
            return _fail(f"roundtrip-mismatch object:{name}")
        # export(import(export(w))) already equals e1; also import the bytes.
        restored = import_workflow(e1)
        e3 = export(restored)
        if e3 != e1:
            return _fail(f"reexport-mismatch object:{name}")
        kinds = kinds_in(wf)
        union_kinds |= kinds
        rows.append(
            {
                "name": name,
                "source": "object",
                "bytes": len(e1),
                "sha256": _sha(e1),
                "kinds": sorted(kinds),
                "equal": True,
            }
        )

    file_fix = load_file_fixtures()
    if not file_fix:
        return _fail("fixture-files-absent")
    for name, raw in file_fix.items():
        try:
            wf = import_workflow(raw)
        except CanonicalError as exc:
            return _fail(f"fixture-import {name} {exc}")
        e1 = export(wf)
        e2 = round_trip_bytes(raw)
        if e1 != e2:
            return _fail(f"roundtrip-mismatch file:{name}")
        # File may be CRLF; canonical export is LF. Round-trip of the file
        # bytes must equal export of the imported object.
        kinds = kinds_in(wf)
        union_kinds |= kinds
        rows.append(
            {
                "name": name,
                "source": "file",
                "bytes": len(e1),
                "sha256": _sha(e1),
                "kinds": sorted(kinds),
                "equal": True,
                "source_had_crlf": b"\r\n" in raw,
            }
        )

    missing = sorted(required - union_kinds)
    if missing:
        return _fail(f"missing-kinds {missing}")
    missing_new = sorted(NEW_NODE_KINDS - union_kinds)
    if missing_new:
        return _fail(f"missing-new-node-types {missing_new}")

    # Both-states: content mutation fails; unmutated twin passes.
    baseline = export(FIXTURES["all-kinds"])
    good = round_trip_bytes(baseline) == baseline
    mutated = bytearray(baseline)
    idx = mutated.find(b"wf.all-kinds")
    if idx < 0:
        return _fail("mutation-anchor-absent")
    mutated[idx] = mutated[idx] ^ 0x01
    try:
        bad_equal = round_trip_bytes(bytes(mutated)) == baseline
    except CanonicalError:
        bad_equal = False
    if not good or bad_equal:
        return _fail(f"mutation-control good={good} bad_equal={bad_equal}")

    # Dropping a Phase-7 kind from the observed set must fail the detector.
    dropped = union_kinds - {"Loop"}
    drop_fires = not NEW_NODE_KINDS.issubset(dropped)
    if not drop_fires:
        return _fail("kind-drop-detector-silent")

    summary = {
        "probe": "probe1-roundtrip",
        "unit_id": "IMP-0146",
        "fixtures_objects": len(FIXTURES),
        "fixtures_files": len(file_fix),
        "kinds": sorted(union_kinds),
        "new_node_types": sorted(NEW_NODE_KINDS),
        "required_kinds_present": True,
        "mutation_control": {
            "unmutated_equal": good,
            "mutated_equal": bad_equal,
            "kind_drop_fires": drop_fires,
        },
        "rows": rows,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"objects={len(FIXTURES)} files={len(file_fix)} "
        f"kinds={sorted(union_kinds)} mutation_fires={not bad_equal}"
    )
    print("SUCCESS:IMP-0146-probe1 idempotent round trip including new node types")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
