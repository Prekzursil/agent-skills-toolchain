"""Cost of widening the published-command gate corpus to `platform/`.

The shipped gate scans tracked `.md` under `command-center/` and `docs/` only.
`platform/` is outside it -- which is exactly how 14 published `python <path>`
commands pointing at files that existed on ONE disk shipped without the gate
saying a word. Widening is the structural fix; this measures what it costs
BEFORE proposing it, by monkeypatching the SHIPPED module's `INCLUDE_PREFIXES`
and calling its own `scan()`, rather than reimplementing the resolver.

Controls, because "0 new violations" from a scanner that scanned nothing looks
identical to a clean result:
  C1 the widened corpus is a STRICT SUPERSET of the shipped one
  C2 the widened corpus is strictly LARGER (it actually picked platform/ up)
  C3 the shipped scope reproduces the gate's own live number
  C4 a uuid target inside a real citer resolves as UNRUNNABLE (the detector fires)

Run:  python command-center/slop-report/_r3_widen.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parents[1]
OUT = Path(__file__).with_suffix(".out.json")

spec = importlib.util.spec_from_file_location(
    "_shipped_gate", HERE / "check_published_commands.py"
)
gate = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(gate)


def corpus_and_findings(prefixes: tuple[str, ...]) -> tuple[list[str], list[dict], int]:
    """`scan()` returns (findings, total, examples); every finding IS unrunnable."""
    original = gate.INCLUDE_PREFIXES
    gate.INCLUDE_PREFIXES = prefixes
    try:
        root = gate.repo_root()
        tracked = {
            gate.norm(p) for p in gate.git(root, "ls-files").splitlines() if p.strip()
        }
        corpus = sorted(p for p in tracked if p.endswith(".md") and gate.in_corpus(p))
        findings, total, _examples = gate.scan(root, tracked, corpus)
    finally:
        gate.INCLUDE_PREFIXES = original
    return corpus, findings, total


def key(row: dict) -> tuple[str, str]:
    return (row["citer"], row["target"])


def main() -> int:
    shipped_corpus, shipped_bad, shipped_total = corpus_and_findings(
        ("command-center/", "docs/")
    )
    wide_corpus, wide_bad, wide_total = corpus_and_findings(
        ("command-center/", "docs/", "platform/")
    )

    seen = {key(r) for r in shipped_bad}
    new_bad = [key(r) for r in wide_bad if key(r) not in seen]

    # C4: the detector must fire on a target that cannot exist.
    ghost = f"platform/{uuid.uuid4().hex}.py"
    root = gate.repo_root()
    tracked = {
        gate.norm(p) for p in gate.git(root, "ls-files").splitlines() if p.strip()
    }
    ghost_ok, _ = gate.resolve(ghost, "command-center/README.md", tracked)
    real_ok, _ = gate.resolve(
        "command-center/slop-report/check_published_commands.py",
        "command-center/README.md",
        tracked,
    )

    controls = {
        "c1_widened_is_superset": set(shipped_corpus) <= set(wide_corpus),
        "c2_widened_is_strictly_larger": len(wide_corpus) > len(shipped_corpus),
        "c3_shipped_corpus_nonempty": len(shipped_corpus) > 0,
        "c4_ghost_target_unrunnable": ghost_ok is False,
        "c4b_real_target_runnable": real_ok is True,
    }

    payload = {
        "shipped_corpus_docs": len(shipped_corpus),
        "widened_corpus_docs": len(wide_corpus),
        "platform_docs_added": len(set(wide_corpus) - set(shipped_corpus)),
        "shipped_commands_scanned": shipped_total,
        "widened_commands_scanned": wide_total,
        "shipped_unrunnable": len(shipped_bad),
        "widened_unrunnable": len(wide_bad),
        "NEW_unrunnable_from_widening": len(new_bad),
        "new_unrunnable_sample": [list(r) for r in new_bad[:25]],
        "controls": controls,
        "all_controls_pass": all(controls.values()),
    }
    OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    print(
        f"corpus {payload['shipped_corpus_docs']} -> {payload['widened_corpus_docs']} docs "
        f"(+{payload['platform_docs_added']} from platform/)"
    )
    print(
        f"unrunnable {payload['shipped_unrunnable']} -> {payload['widened_unrunnable']} "
        f"(NEW from widening: {payload['NEW_unrunnable_from_widening']})"
    )
    for r in payload["new_unrunnable_sample"]:
        print(f"   NEW  {r[0]}  ->  {r[1]}")
    for k, v in controls.items():
        print(f"  control {k}: {v}")
    if not payload["all_controls_pass"]:
        print("FAILED:r3-widen a control did not pass")
        return 1
    print(f"SUCCESS:r3-widen -> {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
