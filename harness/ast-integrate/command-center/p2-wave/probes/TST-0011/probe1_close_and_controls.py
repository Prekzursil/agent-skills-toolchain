#!/usr/bin/env python3
"""Named probe 1: close writes a row; both-states orphan and unregistered controls.

Prints both set-difference counts. Refuses a combined 'looks consistent' pass.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from roundtrip import (  # noqa: E402
    HEX64,
    append_row,
    close_unit,
    digest_file,
    discover_receipts,
    discover_rows,
    independent_path_sets,
    live_sweep,
    print_counts,
    reverse_sweep,
)

UID = "TST-FIX1"
OUT = "command-center/receipts/TST-FIX1.json"
MAN = "command-center/UNIT-ARTIFACT-MANIFEST.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0011-probe1 {msg}")
    return 1


def sweep_tree(root: Path) -> dict:
    rows, errors = discover_rows(root)
    if errors:
        raise RuntimeError(f"manifest parse errors {errors}")
    receipts = discover_receipts(root)
    a = reverse_sweep(root, receipts, rows)
    b = independent_path_sets(root, receipts, rows)
    if a["orphan_row_count"] != b["orphan_row_count"]:
        raise RuntimeError(
            f"signal disagreement orphan {a['orphan_row_count']} vs {b['orphan_row_count']}"
        )
    if a["unregistered_file_count"] != b["unregistered_file_count"]:
        raise RuntimeError(
            f"signal disagreement unregistered {a['unregistered_file_count']} vs "
            f"{b['unregistered_file_count']}"
        )
    return a


def test_close_writes_manifest_row(root: Path) -> dict:
    closed = close_unit(root, UID, OUT)
    row = closed["row"]
    for key in ("path", "sha256", "producing_unit_id"):
        if key not in row:
            raise RuntimeError(f"close row missing {key}")
    if row["path"] != OUT:
        raise RuntimeError(f"close row path {row['path']!r} != {OUT!r}")
    if row["producing_unit_id"] != UID or row["unit_id"] != UID:
        raise RuntimeError(f"producing-unit-id {row.get('producing_unit_id')}")
    if not HEX64.match(str(row["sha256"])):
        raise RuntimeError("close row sha256 is not 64 hex")
    live_sha, live_n = digest_file(root / OUT)
    if row["sha256"] != live_sha or row["bytes"] != live_n:
        raise RuntimeError("close row sha256/bytes do not match file")
    man = json.loads((root / MAN).read_text(encoding="utf-8"))
    matches = [
        r
        for r in man.get("artifacts") or []
        if isinstance(r, dict)
        and r.get("path") == OUT
        and r.get("producing_unit_id") == UID
        and r.get("sha256") == live_sha
    ]
    if len(matches) != 1:
        raise RuntimeError(f"manifest matches={len(matches)} want=1")
    return closed


def test_orphan_manifest_row_detected(root: Path) -> None:
    clean = sweep_tree(root)
    if clean["orphan_row_count"] != 0:
        raise RuntimeError(
            f"detector-control precondition: clean tree already has orphans "
            f"{clean['orphan_row_count']}"
        )
    ghost = {
        "path": "does-not-exist-orphan.json",
        "sha256": "ab" * 32,
        "bytes": 1,
        "present": True,
        "unit_id": "TST-ORPH",
        "producing_unit_id": "TST-ORPH",
        "receipt_path": "does-not-exist-orphan.json",
    }
    append_row(root / MAN, ghost)
    fired = sweep_tree(root)
    print_counts("orphan-planted", fired)
    if fired["orphan_row_count"] < 1:
        raise RuntimeError("planted orphan row did not fire Direction A")
    if not any(r["path"] == ghost["path"] for r in fired["orphan_rows"]):
        raise RuntimeError("planted orphan path absent from Direction A set")
    man = json.loads((root / MAN).read_text(encoding="utf-8"))
    man["artifacts"] = [
        r
        for r in man.get("artifacts") or []
        if not (isinstance(r, dict) and r.get("path") == ghost["path"])
    ]
    (root / MAN).write_text(
        json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    restored = sweep_tree(root)
    print_counts("orphan-restored", restored)
    if restored["orphan_row_count"] != 0:
        raise RuntimeError("orphan detector stayed red after restore")


def test_unregistered_file_detected(root: Path) -> None:
    clean = sweep_tree(root)
    if clean["unregistered_file_count"] != 0:
        raise RuntimeError(
            f"detector-control precondition: clean tree already has unregistered "
            f"{clean['unregistered_file_count']}"
        )
    extra_rel = "command-center/receipts/TST-UNREG.json"
    extra = root / extra_rel
    extra.write_text(
        json.dumps(
            {
                "unit_id": "TST-UNREG",
                "artifacts": [{"path": extra_rel, "role": "primary"}],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    fired = sweep_tree(root)
    print_counts("unregistered-planted", fired)
    if fired["unregistered_file_count"] < 1:
        raise RuntimeError("planted unregistered file did not fire Direction B")
    if extra_rel not in fired["unregistered_files"]:
        raise RuntimeError("planted unregistered path absent from Direction B set")
    extra.unlink()
    restored = sweep_tree(root)
    print_counts("unregistered-restored", restored)
    if restored["unregistered_file_count"] != 0:
        raise RuntimeError("unregistered detector stayed red after restore")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0011-p1-") as tmp:
        root = Path(tmp)
        try:
            closed = test_close_writes_manifest_row(root)
            clean = sweep_tree(root)
            print_counts("close-clean", clean)
            if clean["orphan_row_count"] != 0 or clean["unregistered_file_count"] != 0:
                return fail(
                    "close-clean not empty "
                    f"orphan={clean['orphan_row_count']} "
                    f"unregistered={clean['unregistered_file_count']}"
                )
            test_orphan_manifest_row_detected(root)
            test_unregistered_file_detected(root)
        except RuntimeError as exc:
            return fail(str(exc))

        print(
            json.dumps(
                {
                    "pass": True,
                    "probe": "probe1-close-and-controls",
                    "unit_id": "TST-0011",
                    "close_row": closed["row"],
                    "tests": [
                        "test_close_writes_manifest_row",
                        "test_orphan_manifest_row_detected",
                        "test_unregistered_file_detected",
                    ],
                },
                sort_keys=True,
            )
        )

    # Live print is informational; fixture controls are the pass/fail.
    live = live_sweep(HERE.parents[3])
    print_counts("live-at-probe1", live)
    print(
        "SUCCESS:TST-0011-probe1 close writes path/sha256/producing_unit_id; "
        "both-states orphan and unregistered set differences"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
