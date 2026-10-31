#!/usr/bin/env python3
"""IMP-0116 probe2 (verifier + negative control): generated artifacts pass the
CONFORMANCE validator (a different tool, different rules); a deliberately
broken template makes the check go red, and healing the template goes green."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from marketplace.conformance import check_conformance  # noqa: E402
from marketplace.scaffolder import KINDS, scaffold  # noqa: E402


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="imp0116-p2-"))
    try:
        conf_rows = []
        all_ok = True
        for kind in KINDS:
            root = scaffold(kind, "quill-conf-" + kind, work)
            r = check_conformance(root)
            conf_rows.append({"kind": kind, "ok": r.ok})
            all_ok = all_ok and r.ok
        # NEGATIVE CONTROL: break the README template, scaffold again, expect red
        import marketplace.scaffolder as S
        original = S._README
        S._README = "# {name}\n"
        broken = scaffold("skill", "quill-broken-demo", work)
        broken_report = check_conformance(broken)
        S._README = original
        healed = scaffold("skill", "quill-healed-demo", work)
        checks = {
            "conformance_all_kinds_green": all_ok,
            "broken_template_red": broken_report.ok is False,
            "readme_usage_violation_named": any(v.check == "readme-usage" for v in broken_report.violations),
            "healed_template_green": check_conformance(healed).ok is True,
        }
        print(json.dumps({"conformance": conf_rows, "checks": checks}))
        if not all(checks.values()):
            print("FAILED:IMP-0116-probe2 " + json.dumps(checks))
            return 1
        print("SUCCESS:IMP-0116-probe2 conformance green; broken template red; healed green")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
