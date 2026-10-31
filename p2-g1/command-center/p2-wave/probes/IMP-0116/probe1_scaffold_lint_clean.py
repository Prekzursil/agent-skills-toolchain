#!/usr/bin/env python3
"""IMP-0116 probe1 (source): every scaffold kind generates and lints with zero
findings against the installed-name surface + structural manifest checks."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from marketplace.conformance import check_conformance  # noqa: E402
from marketplace.name_linter import lint_candidate  # noqa: E402
from marketplace.scaffolder import KINDS, scaffold  # noqa: E402

NAMES = {"skill": "quill-narrate-demo", "hook": "quill-trigger-demo",
         "plugin": "quill-bundle-demo", "command": "quill-command-demo"}
REQUIRED = {"skill": "SKILL.md", "hook": "hooks.json", "plugin": "plugin.json", "command": "command.md"}


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="imp0116-p1-"))
    try:
        installed = []
        for base in (REPO / "skills", REPO / ".claude" / "skills", REPO / ".agents" / "skills"):
            if base.is_dir():
                installed += sorted(d.name for d in base.iterdir() if d.is_dir())
        rows = []
        ok = True
        for kind in KINDS:
            root = scaffold(kind, NAMES[kind], work)
            manifest = json.loads((root / "package.json").read_text(encoding="utf-8"))
            name_flags = lint_candidate(manifest["name"], installed)
            required_ok = (root / REQUIRED[kind]).is_file()
            conf = check_conformance(root)
            row = {"kind": kind, "name_flags": len(name_flags), "required_ok": required_ok,
                   "conformance_ok": conf.ok, "manifest_ok": bool(manifest.get("id")) and manifest.get("kind") == kind}
            rows.append(row)
            ok = ok and not name_flags and required_ok and conf.ok and row["manifest_ok"]
        print(json.dumps({"rows": rows, "installed_surface": len(installed), "pass": ok}))
        if not ok:
            print("FAILED:IMP-0116-probe1 scaffold lint findings")
            return 1
        print("SUCCESS:IMP-0116-probe1 all four kinds generate lint-clean on first generation")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
