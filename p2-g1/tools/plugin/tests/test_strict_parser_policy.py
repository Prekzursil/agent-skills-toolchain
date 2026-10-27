#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
REPO = PLUGIN.parents[1]
if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))

import compat_linter as cl  # noqa: E402
import strict_parser as sp  # noqa: E402

LIVE = REPO / ".claude-plugin" / "plugin.json"
BARE = "experimentalFlag"
XKEY = "x-experimentalFlag"


def main() -> int:
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    bad = dict(live)
    bad[BARE] = True
    bad_result = sp.parse_manifest(bad)
    assert not bad_result["ok"]
    assert BARE in " ".join(bad_result["errors"])
    lint_bad = cl.lint_manifest(bad)
    assert not lint_bad["ok"]
    assert BARE in lint_bad["additive_rejected"]
    good = dict(live)
    good[XKEY] = {"forward": True}
    good_result = sp.parse_manifest(good)
    assert good_result["ok"], good_result
    live_result = sp.parse_path(LIVE)
    assert live_result["ok"], live_result
    print("SUCCESS:IMP-0007-tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
