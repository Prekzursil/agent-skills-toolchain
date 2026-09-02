#!/usr/bin/env python3
"""Probe 1: static scan (both-states) + live unmatched-quote EOF control."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import inline_control as I  # noqa: E402
import runner as R  # noqa: E402
import scan as S  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0186-probe1 {msg}")
    return 1


def main() -> int:
    scanned = S.run_scan()
    print(
        f"scan production_n={scanned['production']['n']} "
        f"mutant_n={scanned['mutant']['n']} kinds={scanned['mutant']['kinds']} "
        f"clean_n={scanned['clean_fixture']['n']}"
    )
    if not scanned["production"]["ok"]:
        return fail(f"production inline sites {scanned['production']['findings'][:6]}")
    if not scanned["mutant"]["ok"]:
        return fail(f"mutant did not fire kinds={scanned['mutant']}")
    if not scanned["clean_fixture"]["ok"]:
        return fail(f"clean fixture fired {scanned['clean_fixture']['findings']}")

    with tempfile.TemporaryDirectory(prefix="tst0186-p1-") as tmp:
        work = Path(tmp)
        inline = I.run_inline_script(R.CONTROL_PAYLOAD, work / "inline")
        print(
            f"inline rc={inline['returncode']} eof={inline['eof_phrase_live']} "
            f"control_holds={inline['control_holds']}"
        )
        print(f"  script={inline['script']!r}")
        print(f"  stderr_head={inline['stderr_head']!r}")
        if not inline["control_holds"]:
            return fail(
                f"inline control did not hold rc={inline['returncode']} "
                f"stderr={inline['stderr'][:300]!r}"
            )
        if R.CONTROL_PAYLOAD in (inline["stdout"] or ""):
            return fail("payload leaked to stdout on the inline route")

        file_ok = []
        for kind in R.KINDS:
            rec = R.run_file_route(
                kind, R.CONTROL_PAYLOAD.encode("utf-8"), work / "file" / kind
            )
            print(
                f"file kind={kind} rc={rec['returncode']} "
                f"round_trip={rec['round_trip']} leaked={rec['leaked_into_argv']} "
                f"argv={rec['argv']}"
            )
            if not rec["file_route_holds"]:
                return fail(f"{kind} file route failed {rec}")
            if R.CONTROL_PAYLOAD in rec["argv"]:
                return fail(f"{kind} argv still contains prose")
            file_ok.append(kind)

    print(
        json.dumps(
            {
                "scan_production_n": 0,
                "mutant_fired": True,
                "inline_eof": True,
                "eof_phrase": I.EOF_PHRASE,
                "file_kinds_ok": file_ok,
                "payload_sha256": R.sha256_bytes(R.CONTROL_PAYLOAD.encode("utf-8")),
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0186-probe1 scan silent, inline EOF, file route")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
