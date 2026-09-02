#!/usr/bin/env python3
"""Probe 2: planted local predicate must be caught (detector control).

Independent reviewer signal: re-runs the census with a mechanically
different pattern (regex) against the same planted file the AST census
already flags. The unmutated live site must stay silent on both patterns.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3] / "tools"))

from completion.census import census_file  # noqa: E402
from scenario import PLANTED_SOURCE, REPO, SITES_DIR  # noqa: E402


def main() -> int:
    live = SITES_DIR / "local_runner.py"
    live_ast = census_file(live, root=REPO, detector="ast")
    live_re = census_file(live, root=REPO, detector="regex")
    if live_ast or live_re:
        print(
            json.dumps(
                {"pass": False, "live_ast": live_ast, "live_regex": live_re},
                indent=2,
                sort_keys=True,
            )
        )
        print("FAILED:IMP-0417-probe2 live site already has a local predicate")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0417-plant-") as tmp:
        planted = Path(tmp) / "local_runner.py"
        planted.write_text(PLANTED_SOURCE, encoding="utf-8")
        ast_hits = census_file(planted, root=Path(tmp), detector="ast")
        regex_hits = census_file(planted, root=Path(tmp), detector="regex")

    ast_fired = any(
        h.get("kind") in {"exit-zero-compare", "local-complete-return"} for h in ast_hits
    )
    regex_fired = any(h.get("kind") == "exit-zero-regex" for h in regex_hits)
    ok = bool(ast_fired and regex_fired and not live_ast and not live_re)
    payload = {
        "probe": "probe2-planted-predicate",
        "unit_id": "IMP-0417",
        "pass": ok,
        "ast_fired_on_planted": ast_fired,
        "regex_fired_on_planted": regex_fired,
        "ast_hits": ast_hits,
        "regex_hits": regex_hits,
        "live_ast_hits": live_ast,
        "live_regex_hits": live_re,
        "reviewer_pattern": "regex (exit_code==0 co-occurring with COMPLETE)",
        "author_pattern": "ast (Compare exit_code==0 and COMPLETE return without judge)",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not ast_fired:
        print("FAILED:IMP-0417-probe2 AST census missed planted predicate")
        return 1
    if not regex_fired:
        print("FAILED:IMP-0417-probe2 regex census missed planted predicate")
        return 1
    print(
        "SUCCESS:IMP-0417-probe2 planted local predicate caught by AST and "
        "regex; live site silent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
