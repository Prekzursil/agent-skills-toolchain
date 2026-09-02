"""Probe 2: external checker with egress blocked reports UNREACHABLE, not 404.

Mechanically different from probe 1 (no git cat-file). Uses unshare -n
around the same classifier that maps HTTP 404/410 to WRONG.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import egress_detector  # noqa: E402

ART = REPO / "command-center/receipts/TST-0255.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0255-probe2 {msg}")
    return 1


def check_artifact() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0255" not in text:
        return "artifact sentinel absent"
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"artifact self-declared {st}"
    return None


def main() -> int:
    err = check_artifact()
    if err:
        return fail(err)

    live = egress_detector()
    summary = {k: live[k] for k in live if k not in {"open_ok", "open_404", "open_410", "blocked_404", "blocked_ok"}}
    print(json.dumps(summary, sort_keys=True))
    print(
        f"open_ok={live['open_ok']['classification']} "
        f"open_404={live['open_404']['classification']} "
        f"open_410={live['open_410']['classification']} "
        f"blocked_404={live['blocked_404']['classification']} "
        f"blocked_ok={live['blocked_ok']['classification']}"
    )
    if not live["unblocked_ok_is_OK"]:
        return fail("unblocked /ok was not OK")
    if not live["unblocked_404_is_WRONG"]:
        return fail("unblocked 404 was not WRONG")
    if not live["unblocked_410_is_WRONG"]:
        return fail("unblocked 410 was not WRONG")
    if not live["blocked_404_is_UNREACHABLE"]:
        return fail("blocked 404 was not UNREACHABLE")
    if not live["blocked_404_is_not_WRONG"]:
        return fail("blocked 404 was folded into WRONG")
    if not live["blocked_ok_is_UNREACHABLE"]:
        return fail("blocked /ok was not UNREACHABLE")
    if not live["broken_folder_reports_WRONG_on_block"]:
        return fail("broken folder control did not map block to WRONG")
    if not live["pass"]:
        return fail("egress detector did not pass")
    err_txt = str((live["blocked_404"] or {}).get("error") or "")
    err_type = str((live["blocked_404"] or {}).get("error_type") or "")
    if "unreachable" not in err_txt.lower() and "101" not in err_txt and "URLError" not in err_type:
        return fail(f"blocked error not network-unreachable {err_type} {err_txt}")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        rec = doc.get("egress") or {}
        if rec.get("blocked_404_is_UNREACHABLE") is not True:
            return fail("artifact egress.blocked_404_is_UNREACHABLE drift")
        if rec.get("blocked_404_is_not_WRONG") is not True:
            return fail("artifact egress.blocked_404_is_not_WRONG drift")
        if rec.get("unblocked_404_is_WRONG") is not True:
            return fail("artifact egress.unblocked_404_is_WRONG drift")
        if rec.get("pass") is not True:
            return fail("artifact egress.pass drift")
        tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
        row = tests.get("detector-egress-unreachable-not-404")
        if not row or row.get("result") != "PASS":
            return fail("artifact test detector-egress-unreachable-not-404 not PASS")

    print("SUCCESS:TST-0255-probe2 egress blocked UNREACHABLE not 404")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
