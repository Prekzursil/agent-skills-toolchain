#!/usr/bin/env python3
"""Probe 2: determinism clause + certified-executable required set.

Both-states:
  * replayable=true encoding: two dry-runs produce identical plan bytes
  * a second blueprint's plan differs (equality is not vacuous)
  * certified_executable=true missing roles is rejected
  * certified_executable=false may omit roles
  * prompt_transport other than file is rejected
  * dsl.py dry-run path imports none of time/random/socket/uuid
"""
from __future__ import annotations

import ast
import copy
import inspect
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dsl as D  # noqa: E402

BANNED_IMPORTS = frozenset(
    {
        "time",
        "datetime",
        "random",
        "secrets",
        "socket",
        "uuid",
        "getpass",
        "platform",
    }
)


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0082-probe2 {msg}")
    return 1


def _banned_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in BANNED_IMPORTS:
                    hits.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".", 1)[0]
            if root in BANNED_IMPORTS:
                hits.append(node.module)
    return hits


def main() -> int:
    schema = D.load_contract()
    hits = _banned_imports(HERE / "dsl.py")
    print(f"dsl_banned_imports={hits}")
    if hits:
        return fail(f"host-clock-imports:{hits}")
    src = inspect.getsource(D.dry_run)
    for name in BANNED_IMPORTS:
        if f"import {name}" in src:
            return fail(f"dry_run-imports:{name}")

    rows = D.encode_corpus()
    a, b = rows[0], rows[1]
    enc_a = a["encoded"]
    run1 = D.dry_run(enc_a)
    run2 = D.dry_run(enc_a)
    print(
        f"replayable={enc_a.get('replayable')} "
        f"dry1={run1['sha256'][:16]} dry2={run2['sha256'][:16]} equal={run1['sha256'] == run2['sha256']}"
    )
    if enc_a.get("replayable") is not True:
        return fail("corpus-not-replayable")
    if run1["sha256"] != run2["sha256"] or run1["bytes"] != run2["bytes"]:
        return fail("replayable-plans-diverged")
    run_b = D.dry_run(b["encoded"])
    print(f"vacuity other={run_b['sha256'][:16]} distinct={run_b['sha256'] != run1['sha256']}")
    if run_b["sha256"] == run1["sha256"]:
        return fail("plan-equality-vacuous")

    good_err = D.validate_instance(enc_a, schema)
    print(f"good_accepted={not good_err} nerr={len(good_err)}")
    if good_err:
        return fail("good-instance-rejected:" + " | ".join(good_err[:6]))

    drop_roles = copy.deepcopy(enc_a)
    drop_roles.pop("roles", None)
    e1 = D.validate_instance(drop_roles, schema)
    print(f"certified_missing_roles rejected={bool(e1)} n={len(e1)}")
    if not e1:
        return fail("certified-missing-roles-accepted")

    sketch = copy.deepcopy(enc_a)
    sketch["certified_executable"] = False
    sketch.pop("roles", None)
    sketch.pop("tool_policy", None)
    sketch.pop("parameters", None)
    sketch.pop("retries", None)
    # replayable still true => resume stays
    e2 = D.validate_instance(sketch, schema)
    print(f"uncertified_omit_roles accepted={not e2} n={len(e2)}")
    if e2:
        return fail("uncertified-rejected:" + " | ".join(e2[:6]))

    inline = copy.deepcopy(enc_a)
    inline["prompt_transport"] = "inline"
    e3 = D.validate_instance(inline, schema)
    print(f"inline_transport rejected={bool(e3)} n={len(e3)}")
    if not e3:
        return fail("inline-transport-accepted")

    no_resume = copy.deepcopy(enc_a)
    no_resume.pop("resume", None)
    e4 = D.validate_instance(no_resume, schema)
    print(f"replayable_without_resume rejected={bool(e4)} n={len(e4)}")
    if not e4:
        return fail("replayable-without-resume-accepted")

    print("SUCCESS:ARC-0082-probe2 determinism+certified-required both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
