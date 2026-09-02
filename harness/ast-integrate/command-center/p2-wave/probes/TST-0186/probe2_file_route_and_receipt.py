#!/usr/bin/env python3
"""Probe 2: independent file-route property test + receipt quotes live wrap."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inline_control as I  # noqa: E402
import runner as R  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "TST-0186.json"
SENTINEL = "SUCCESS:TST-0186"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:TST-0186-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0186-p2-") as tmp:
        work = Path(tmp)
        inline = I.run_inline_script(R.CONTROL_PAYLOAD, work / "inline")
        prop = R.run_property_matrix(work / "property")
        file_commit = R.run_file_route(
            "commit_message",
            R.CONTROL_PAYLOAD.encode("utf-8"),
            work / "file-commit",
        )

    print(
        f"inline rc={inline['returncode']} eof={inline['eof_phrase_live']} "
        f"control_holds={inline['control_holds']}"
    )
    print(f"property ok={prop['ok']} n={prop['n_payloads']}")
    print(
        f"file-commit rc={file_commit['returncode']} "
        f"round_trip={file_commit['round_trip']} argv={file_commit['argv']}"
    )

    if not inline["control_holds"]:
        return fail("independent inline EOF control failed")
    if not prop["ok"]:
        return fail(f"property matrix failed {prop['rows']}")
    if not file_commit["file_route_holds"]:
        return fail("commit -F stand-in failed")
    for name, kinds in prop["rows"].items():
        for kind, rec in kinds.items():
            if rec["leaked_into_argv"]:
                return fail(f"{name}/{kind} leaked prose into argv")
            joined = " ".join(rec["argv"])
            # Path is the only payload-adjacent token; the prose itself must
            # not appear as an argv element.
            prose = R.PROPERTY_PAYLOADS[name]
            try:
                text = prose.decode("utf-8")
            except UnicodeDecodeError:
                text = None
            if text and any(text == elt for elt in rec["argv"]):
                return fail(f"{name}/{kind} argv element equals prose")

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
    if doc.get("unit_id") != "TST-0186":
        return fail(f"unit_id {doc.get('unit_id')}")

    live_script = inline["script"]
    claimed = (doc.get("measured") or {}).get("inline") or {}
    claimed_script = claimed.get("script")
    if claimed_script != live_script:
        return fail("receipt inline script != live script")
    if I.EOF_PHRASE not in str(claimed.get("stderr") or claimed.get("stderr_head") or ""):
        if I.EOF_PHRASE not in text:
            return fail("receipt does not quote live unmatched-quote EOF stderr")
    claimed_sha = str((doc.get("measured") or {}).get("control_payload_sha256") or "")
    live_sha = R.sha256_bytes(R.CONTROL_PAYLOAD.encode("utf-8"))
    if claimed_sha != live_sha:
        return fail(f"payload sha receipt={claimed_sha} live={live_sha}")
    if (doc.get("measured") or {}).get("file_route_holds") is not True:
        return fail("receipt did not record file_route_holds=true")
    if (doc.get("measured") or {}).get("scan_production_n") not in {0, "0"}:
        # allow missing only if evidence quotes zero sites
        scan_n = ((doc.get("measured") or {}).get("scan") or {}).get("production", {}).get("n")
        if scan_n != 0:
            return fail("receipt scan_production_n is not 0")

    ev = doc.get("evidence") or []
    if not any(
        isinstance(row, dict) and live_script in str(row.get("claim") or "")
        for row in ev
    ):
        return fail("evidence missing verbatim failing inline script")
    if not any(
        isinstance(row, dict) and I.EOF_PHRASE in str(row.get("claim") or "")
        for row in ev
    ):
        return fail("evidence missing live EOF phrase")

    second = R.second_shell_note()
    print(f"second_shell pwsh={second['pwsh_on_path']} live={second['windows_second_shell_live']}")

    print(
        json.dumps(
            {
                "property_ok": True,
                "n_payloads": prop["n_payloads"],
                "receipt_quotes_live_script": True,
                "receipt_sha_matches": True,
                "inline_eof": True,
                "second_shell_windows_live": second["windows_second_shell_live"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0186-probe2 file-route property and receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
