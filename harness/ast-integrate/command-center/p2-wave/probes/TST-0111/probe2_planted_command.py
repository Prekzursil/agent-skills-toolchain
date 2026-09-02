#!/usr/bin/env python3
"""Probe 2: extractor finds a planted command (detector control).

Independent of probe 1's coverage walk: this probe matches the unique plant
token against the fixture bytes, then asks the extractor for the same token,
and proves a naive unlabeled-only extractor is silent on a language-tagged
fence.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import checker as K  # noqa: E402
from extract import extract_text, naive_unlabeled_only  # noqa: E402

ART = REPO / "command-center/receipts/TST-0111.json"
PLANTED = "echo TST-0111-PLANTED-FENCE"
PLANTED_MD = HERE / "fixtures" / "planted.md"
HAND = HERE / "fixtures" / "hand-count-planted.json"
BASH_PLANT_RE = re.compile(
    r"```bash\s*\n" + re.escape(PLANTED) + r"\s*\n```",
    re.MULTILINE,
)
PYTHON_PRINT_RE = re.compile(
    r"```python\s*\nprint\(" + re.escape(f'"{PLANTED}"') + r"\)",
    re.MULTILINE,
)


def main() -> int:
    if not ART.is_file():
        print("FAILED:TST-0111-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = K.check_artifact(doc)
    print(f"artifact_ok={ok} {why}")
    if not ok:
        print("FAILED:TST-0111-probe2 checker")
        return 1

    raw = PLANTED_MD.read_text(encoding="utf-8").replace("\r\n", "\n")
    bash_hit = bool(BASH_PLANT_RE.search(raw))
    python_hit = bool(PYTHON_PRINT_RE.search(raw))
    print(f"byte_bash_plant={bash_hit} byte_python_print={python_hit}")
    if not bash_hit:
        print("FAILED:TST-0111-probe2 planted.md lost the bash fence")
        return 1
    if not python_hit:
        print("FAILED:TST-0111-probe2 planted.md lost the python mention")
        return 1

    rel = "command-center/p2-wave/probes/TST-0111/fixtures/planted.md"
    rows = extract_text(raw, rel)
    cmds = [r.get("command") for r in rows]
    print(f"extracted={cmds}")
    if PLANTED not in cmds:
        print("FAILED:TST-0111-probe2 extractor missed planted command")
        return 1
    if any("print" in str(c) for c in cmds):
        print("FAILED:TST-0111-probe2 python mention extracted as command")
        return 1

    naive = naive_unlabeled_only(raw, rel)
    naive_cmds = [r.get("command") for r in naive]
    print(f"naive_unlabeled={naive_cmds}")
    if PLANTED in naive_cmds:
        print("FAILED:TST-0111-probe2 naive extractor unexpectedly found plant")
        return 1

    hand = json.loads(HAND.read_text(encoding="utf-8"))
    if int(hand.get("fenced_shell_command_count") or -1) != len(rows):
        print(
            "FAILED:TST-0111-probe2 hand-count "
            f"{hand.get('fenced_shell_command_count')} != {len(rows)}"
        )
        return 1
    if hand.get("must_contain") != PLANTED:
        print("FAILED:TST-0111-probe2 hand-count token drift")
        return 1

    stripped = BASH_PLANT_RE.sub("```bash\necho TST-0111-NOT-THE-PLANT\n```", raw, count=1)
    after = [r.get("command") for r in extract_text(stripped, rel)]
    print(f"after_strip={after}")
    if PLANTED in after:
        print("FAILED:TST-0111-probe2 plant still found after bash fence stripped")
        return 1

    empty = extract_text(
        (HERE / "fixtures" / "empty.md").read_text(encoding="utf-8"),
        "empty.md",
    )
    if empty:
        print(f"FAILED:TST-0111-probe2 empty.md yielded {empty}")
        return 1

    planted_ctrl = (doc.get("controls") or {}).get("planted") or {}
    if planted_ctrl.get("found_plant") is not True:
        print("FAILED:TST-0111-probe2 receipt plant flag stale")
        return 1
    if planted_ctrl.get("naive_unlabeled_found_plant") is not False:
        print("FAILED:TST-0111-probe2 receipt naive flag stale")
        return 1

    print("found_plant=True naive_silent=True python_excluded=True")
    print("SUCCESS:TST-0111-probe2 planted command detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
