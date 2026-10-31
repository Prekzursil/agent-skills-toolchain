#!/usr/bin/env python3
"""Probe 2: AST except:pass + PowerShell SilentlyContinue + falsifiability sample.

Mechanically different from probe 1 (AST vs regex YAML). A string mention of
`except: pass` must not be counted. Ten JUSTIFIED fixture verdicts must be
falsifiable; a decorative `best effort` site must stay UNACCOUNTED.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

PS1 = HERE / "fixtures" / "ps1" / "silent.ps1"
STRING_PY = HERE / "fixtures" / "mention" / "string_except.py"
SAMPLE = HERE / "fixtures" / "reviewer" / "justified_sample.py"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0023-probe2 {msg}")
    return 1


def main() -> int:
    ps = C.scan_paths(REPO, [PS1])
    silent = [f for f in ps if f.construct == "erroraction-silentlycontinue"]
    if len(silent) < 1:
        return fail("PowerShell -ErrorAction SilentlyContinue not reported")
    if not any("SilentlyContinue" in f.snippet for f in silent):
        return fail("PowerShell hit missing SilentlyContinue snippet")

    string_hits = C.scan_paths(REPO, [STRING_PY])
    if any(f.construct == "bare-except-pass" for f in string_hits):
        return fail("AST counted a string mention of except: pass")
    raw = STRING_PY.read_text(encoding="utf-8")
    if not re.search(r"except:\s*pass", raw):
        return fail("string_except fixture lost the mention")

    sample = C.scan_paths(REPO, [SAMPLE])
    just = [f for f in sample if f.classification == "JUSTIFIED"]
    unacc = [f for f in sample if f.classification == "UNACCOUNTED"]
    if len(just) < 10:
        return fail(f"reviewer fixture JUSTIFIED={len(just)} want>=10")
    if not unacc:
        return fail("decorative best-effort site not UNACCOUNTED")
    bad_just = [f for f in just[:10] if not C.reason_is_falsifiable(f.reason)]
    if bad_just:
        return fail(f"JUSTIFIED reason not falsifiable: {bad_just[0].reason!r}")
    decorative = [f for f in unacc if f.reason and C.DECORATIVE_RE.search(f.reason)]
    if not decorative:
        return fail("decorative UNACCOUNTED site not found")

    live = C.scan_tree(REPO, skip_own_unit=True)
    live_except = [f for f in live if f.construct == "bare-except-pass"]
    if not live_except:
        return fail("live tree AST census found zero except:pass (detector dead)")

    doc = {
        "probe": "probe2-ast-powershell-reviewer",
        "unit_id": "BLD-0023",
        "powershell_silentlycontinue": len(silent),
        "string_mention_except_pass": 0,
        "fixture_justified": len(just),
        "fixture_unaccounted": len(unacc),
        "justified_falsifiable": len(just[:10]),
        "live_except_pass": len(live_except),
        "pass": True,
    }
    print(json.dumps(doc, sort_keys=True))
    print(
        f"ps1={len(silent)} string_ast=0 justified={len(just)} "
        f"unaccounted={len(unacc)} live_except={len(live_except)}"
    )
    print("SUCCESS:BLD-0023-probe2 AST except:pass, PowerShell, falsifiable sample")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
