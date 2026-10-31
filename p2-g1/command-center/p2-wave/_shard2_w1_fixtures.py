#!/usr/bin/env python3
"""Rebuild the AUD-0084 use-vs-mention fixture from its asserted contract."""
from __future__ import annotations

import sys
from pathlib import Path

P2 = Path("C:/Users/Prekzursil/p2-g1")
FIXDIR = P2 / "command-center/p2-wave/probes/AUD-0084/fixtures"

LINES = [
    '"""Fixture calibration module for the AUD-0084 use-versus-mention control.',
    "",
    "The paths mentioned in this docstring, like C:/Users/guest/notes.txt and",
    "/home/builder/work, are documentation mentions, not operational uses.",
    '"""',
    "import re",
    "",
    'PATTERN = re.compile(r"C:/Users/[a-z]+/notes")',
    "",
    'CONFIG_HINT = "see ~/.claude/skills for the installed set"',
    "",
    "",
    "def load_portable():",
    '    handle = open("D:/portable/tools/bin/tool.exe", "rb")',
    "    try:",
    "        return handle.read(16)",
    "    finally:",
    "        handle.close()",
    "",
    "",
    "def write_config(target):",
    '    payload = "root: ~/.claude/config.json"',
    '    return target.write_text(payload, encoding="utf-8")',
    "",
    "",
    "def find_skill_docs(root):",
    '    return list(root.glob("*/SKILL.md"))',
    "",
]


def main() -> int:
    FIXDIR.mkdir(parents=True, exist_ok=True)
    fixture = FIXDIR / "use_vs_mention_fixture.py"
    if not fixture.exists():
        fixture.write_text("\n".join(LINES), encoding="utf-8", newline="\n")
        print("fixture WRITTEN", fixture)
    else:
        print("fixture already present")
    sys.path.insert(0, str(FIXDIR.parent))
    import census as C84
    ctrl = C84.evaluate_control()
    print("passed=%s regex=%s doc=%s open=%s glob=%s payload=%s mutant=%s rows=%d"
          % (ctrl["passed"], ctrl["regex_silent"], ctrl["docstring_silent"],
             ctrl["open_flagged"], ctrl["relative_glob_excluded"],
             ctrl["write_text_payload_excluded"],
             ctrl["mutant_context_filter_disabled_goes_red"],
             ctrl["good_row_count"]))
    if not ctrl["passed"]:
        print("good_classes=", ctrl["good_classes"])
        print("good_values=", ctrl["good_values"])
        return 1
    print("CONTROL-GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
