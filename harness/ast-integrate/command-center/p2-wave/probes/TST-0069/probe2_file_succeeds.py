#!/usr/bin/env python3
"""TST-0069 probe 2: same apostrophe payload succeeds via the file route.

Independent of probe 1: re-runs argv / -F / grep -F -f, requires lint silence
on file-route commands (both-states), and checks the catalog receipt quoted
the live failing wrap verbatim.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import transport as T  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "TST-0069.json"
SENTINEL = "SUCCESS:TST-0069"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:TST-0069-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0069-p2-") as tmp:
        matrix = T.run_matrix(Path(tmp))
    files = matrix["file"]
    for name, row in files.items():
        print(
            f"shape={name} rc={row['returncode']} round_trip={row['round_trip']} "
            f"file_route_holds={row['file_route_holds']} lint_ok={row['lint']['ok']}"
        )
        if not row["file_route_holds"]:
            return fail(
                f"{name} file route did not hold rc={row['returncode']} "
                f"stdout={row['stdout']!r} stderr={row['stderr'][:200]!r}"
            )
        if T.APOSTROPHE in row["command"]:
            return fail(f"{name} command still contains an apostrophe")
    if not matrix["lint"]["good_all_silent"]:
        return fail(f"lint fired on file-route corpus {matrix['lint']['good']}")
    if not matrix["lint"]["bad_all_fired"]:
        return fail("lint both-states missing: planted inline commands were silent")
    if matrix["payload_sha256"] != T.payload_sha256():
        return fail("payload sha drifted")

    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        return fail("catalog receipt absent")
    text = RECEIPT.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"receipt-unparseable {exc}")
    if not isinstance(doc, dict):
        return fail("receipt-not-object")
    state = str(doc.get("state") or "").upper()
    if state in NOT_DELIVERING:
        return fail(f"self-declared:{state}")
    if doc.get("unit_id") != "TST-0069":
        return fail(f"unit_id {doc.get('unit_id')}")

    measured = doc.get("measured")
    if not isinstance(measured, dict) or not measured:
        measured = (doc.get("report") or {}).get("measured") or {}
    live_wrap = matrix["inline"]["python-c"]["wrapped_script"]
    claimed_inline = (measured.get("inline") or {}).get("python-c") or {}
    claimed_wrap = claimed_inline.get("wrapped_script")
    if claimed_wrap != live_wrap:
        return fail("receipt python-c wrap != live wrap")
    claimed_sha = str(measured.get("payload_sha256") or "")
    if claimed_sha != matrix["payload_sha256"]:
        return fail(
            f"payload_sha256 receipt={claimed_sha} live={matrix['payload_sha256']}"
        )
    file_ok = measured.get("file_route_holds")
    if file_ok is not True:
        return fail("receipt did not record file_route_holds=true")
    ev = doc.get("evidence") or []
    if not any(
        isinstance(row, dict)
        and live_wrap in str(row.get("claim") or row.get("detail") or "")
        for row in ev
    ):
        return fail("evidence missing verbatim failing python-c wrap")

    print(
        json.dumps(
            {
                "file_shapes_ok": sorted(files),
                "payload_sha256": matrix["payload_sha256"],
                "lint_good_silent": True,
                "lint_bad_fired": True,
                "receipt_quotes_live_wrap": True,
                "receipt_sha_matches": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0069-probe2 apostrophe payload succeeds via the file route")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
