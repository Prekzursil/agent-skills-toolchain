#!/usr/bin/env python
"""Phase 8 routing CLI - the single gate entry point.

    python platform/routing/cli.py index       # inventory census + fail-closed floors
    python platform/routing/cli.py descriptions # routing-quality report for descriptions
    python platform/routing/cli.py queries      # labelled-set census + gold-id resolution
    python platform/routing/cli.py tune         # re-derive SCORE_FLOOR / Z_THRESHOLD
    python platform/routing/cli.py budget       # injected bytes at k=1,3,5,10
    python platform/routing/cli.py metrics      # the full report (what the doc quotes)
    python platform/routing/cli.py route <q>    # explain one routing decision
    python platform/routing/cli.py all          # every gate, one terminal marker

SELF-BOOTSTRAPPING. `platform/` cannot be a package (`platform` is a stdlib module, so
`platform/__init__.py` would shadow the standard library -- the same conclusion
`platform/lib/wfdsl/conftest.py` reached), so this file puts the BUILD ROOT on `sys.path`
and imports the package by its own name, `routing`. That makes the command above work from
any cwd without PYTHONPATH, which is what a CI gate needs.

Every subcommand ends in a `SUCCESS:<id>` / `FAILED:<id> <reason>` terminal marker
(AGENTS.md 4) and returns a non-zero exit on failure (`ci-hygiene.md` 1).
"""

from __future__ import annotations

import sys
from pathlib import Path

BUILD_ROOT = Path(__file__).resolve().parents[1]
if str(BUILD_ROOT) not in sys.path:
    sys.path.insert(0, str(BUILD_ROOT))

from routing import budget, descriptions, index, metrics, queries, router, tuning  # noqa: E402

#: subcommand -> (callable(argv) -> int, gate id)
COMMANDS = {
    "index": (index.main, "routing-index"),
    "descriptions": (descriptions.main, "routing-descriptions"),
    "queries": (queries.main, "routing-queries"),
    "tune": (tuning.main, "routing-tuning"),
    "budget": (budget.main, "routing-budget"),
    "metrics": (metrics.main, "routing-metrics"),
}

#: The gates `all` runs, in dependency order. `tune` is EXCLUDED: it is a derivation
#: experiment (88 grid points x 57 queries), not a per-commit gate, and re-deriving a
#: constant inside the gate that validates it would be circular.
ALL_GATES = ("index", "descriptions", "queries", "budget", "metrics")


def _route(argv: list[str]) -> int:
    q = " ".join(argv).strip()
    if not q:
        print("FAILED:routing-route empty-query")
        return 1
    r = router.Router.build()
    print(r.explain(q, k=5))
    print("SUCCESS:routing-route")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]

    if cmd == "route":
        return _route(rest)

    if cmd == "all":
        failed: list[str] = []
        for name in ALL_GATES:
            fn, gate = COMMANDS[name]
            print(f"\n{'=' * 30} {name} {'=' * 30}", flush=True)
            try:
                rc = fn([])
            except (
                Exception
            ) as exc:  # a crashed gate is a FAILED gate, never a skipped one
                print(f"FAILED:{gate} exception={type(exc).__name__}: {exc}")
                rc = 1
            if rc != 0:
                failed.append(name)
        if failed:
            print(f"\nFAILED:routing-all gates={','.join(failed)}")
            return 1
        print(f"\nSUCCESS:routing-all gates={len(ALL_GATES)}/{len(ALL_GATES)}")
        return 0

    entry = COMMANDS.get(cmd)
    if entry is None:
        print(
            f"FAILED:routing-cli unknown-subcommand={cmd!r} known={sorted(COMMANDS) + ['route', 'all']}"
        )
        return 2
    return entry[0](rest)


if __name__ == "__main__":
    raise SystemExit(main())
