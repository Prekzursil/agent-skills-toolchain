#!/usr/bin/env python3
"""TST-0213 probe1: static scan — plant fires; live tree is zero-hit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.lib.credential_mutation import (  # noqa: E402
    PLANTED_CLEAN_PY,
    PLANTED_REVOKE_TOKEN_JS,
    PLANTED_REVOKE_TOKEN_PY,
    detector_fires_on_plant,
    scan_tree,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0213-probe1 {msg}")
    return 1


def main() -> int:
    plant_py = detector_fires_on_plant(PLANTED_REVOKE_TOKEN_PY, "python")
    plant_js = detector_fires_on_plant(PLANTED_REVOKE_TOKEN_JS, "javascript")
    clean_silent = not detector_fires_on_plant(PLANTED_CLEAN_PY, "python")
    live = scan_tree(REPO)
    summary = {
        "probe": "probe1-static-scan",
        "plant_python_fires": plant_py,
        "plant_javascript_fires": plant_js,
        "clean_helper_silent": clean_silent,
        "files_scanned": live.get("files_scanned"),
        "files_by_language": live.get("files_by_language"),
        "languages_scanned": live.get("languages_scanned"),
        "hit_count": live.get("hit_count"),
        "hits": live.get("hits"),
        "skip": live.get("skip"),
    }
    print(json.dumps(summary, sort_keys=True))
    if not plant_py:
        return fail("planted revoke_token() python did not fire (vacuous detector)")
    if not plant_js:
        return fail("planted revoke_token() javascript did not fire (vacuous detector)")
    if not clean_silent:
        return fail("detector fired on a non-mutation helper")
    if int(live.get("files_scanned") or 0) < 2:
        return fail("scan covered too few files")
    langs = set(live.get("languages_scanned") or [])
    if "python" not in langs or "javascript" not in langs:
        return fail(f"did not scan python and javascript: {sorted(langs)}")
    if live.get("hits"):
        return fail(f"live mutation call sites: {live.get('hits')}")
    print("SUCCESS:TST-0213-probe1 plant fires; live tree has zero mutation calls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
