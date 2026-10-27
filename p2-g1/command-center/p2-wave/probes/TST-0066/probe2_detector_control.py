#!/usr/bin/env python3
"""TST-0066 probe2: live detector control with REAL 8.3 aliases.

Mechanically different from probe1 (which re-derives the receipt's
recorded matrix): this creates a real long-named file on this volume,
obtains its genuine short name via GetShortPathNameW, and shows the
string-comparing deny guard is bypassed by that real alias while the
canonical guard rejects both forms. Asserts the receipt's
detector_control block (bypassed=true, string verdicts, canonical
verdicts) matches the live outcome."""
from __future__ import annotations

import ctypes
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = REPO / "command-center" / "p2-wave" / "probes" / "TST-0066"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from winpath import _expand_83, canonical, live_long, same_identity  # noqa: E402

UNIT = "TST-0066"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def main() -> int:
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    td = tempfile.mkdtemp(prefix="tst0066-83-")
    try:
        long_file = Path(td) / "a guard denied secret with a very long name.txt"
        long_file.write_text("denied-content\n", encoding="utf-8")
        time.sleep(0.2)
        short_form = live_long(str(long_file))
        chk(bool(short_form and short_form != str(long_file)), "8.3-alias-available", str(short_form))
        if not short_form:
            print("FAILED:" + UNIT + "-probe2 8.3-alias-unavailable")
            return 1
        denied_long = str(long_file)

        def string_deny(cand: str) -> str:
            return "REJECT" if cand == denied_long else "ACCEPT"

        def canonical_deny(cand: str) -> str:
            return "REJECT" if same_identity(cand, denied_long) else "ACCEPT"

        v_long_str = string_deny(denied_long)
        v_short_str = string_deny(short_form)
        v_long_can = canonical_deny(denied_long)
        v_short_can = canonical_deny(short_form)
        # canonicalization must fold the real alias pair to one identity
        chk(canonical(_expand_83(denied_long)) == canonical(_expand_83(short_form)), "canonical-fold-of-real-alias",
            canonical(denied_long) + " vs " + canonical(short_form))
        # the string guard IS bypassed by the real short name (detector control)
        chk(v_long_str == "REJECT" and v_short_str == "ACCEPT", "string-guard-bypassed-by-real-83",
            v_long_str + "/" + v_short_str)
        # the canonical guard rejects both
        chk(v_long_can == "REJECT" and v_short_can == "REJECT", "canonical-guard-holds",
            v_long_can + "/" + v_short_can)
        dc = doc.get("detector_control") or {}
        chk(dc.get("bypassed") is True, "receipt-bypassed-flag")
        sv = dc.get("string_verdicts") or {}
        cv = dc.get("canonical_verdicts") or {}
        chk(str(sv.get("exact")) == "REJECT" and str(sv.get("trailing_dot")) == "ACCEPT" and str(sv.get("short_name")) == "ACCEPT",
            "receipt-string-verdicts-shape", json.dumps(sv))
        chk(all(str(v) == "REJECT" for v in cv.values()), "receipt-canonical-verdicts-shape", json.dumps(cv))
        # trailing-dot alias live: string ACCEPT, canonical REJECT
        dot = denied_long + "."
        chk(string_deny(dot) == "ACCEPT" and canonical_deny(dot) == "REJECT", "trailing-dot-live",
            string_deny(dot) + "/" + canonical_deny(dot))
        out = {
            "probe": "probe2-live-detector-control",
            "real_83_alias": short_form,
            "string_verdicts": {"long": v_long_str, "short": v_short_str, "trailing_dot": string_deny(dot)},
            "canonical_verdicts": {"long": v_long_can, "short": v_short_can, "trailing_dot": canonical_deny(dot)},
        }
    finally:
        time.sleep(0.3)
        shutil.rmtree(td, ignore_errors=True)
    if fails:
        print("FAILED:" + UNIT + "-probe2 " + "; ".join(fails))
        return 1
    print(json.dumps(out, indent=1))
    print("SUCCESS:" + UNIT + "-probe2 live detector control on a real GetShortPathNameW alias: string deny bypassed (short+dot ACCEPT), canonical deny holds (both REJECT); receipt detector_control matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
