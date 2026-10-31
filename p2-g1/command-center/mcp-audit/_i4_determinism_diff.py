#!/usr/bin/env python3
"""Name the fields on which the regenerated disposition differs from the committed blob."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent


def main() -> int:
    tmp = pathlib.Path(tempfile.mkdtemp()) / "d.json"
    subprocess.run(
        [sys.executable, "rank_disposition.py", "--base", str(HERE), "-o", str(tmp)],
        cwd=HERE,
        capture_output=True,
        check=True,
    )
    regen = json.loads(tmp.read_text(encoding="utf-8"))
    shipped = json.loads(
        subprocess.run(
            ["git", "show", "HEAD:command-center/mcp-audit/disposition.json"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )

    top = set(regen) | set(shipped)
    for k in sorted(top):
        a, b = (
            json.dumps(regen.get(k), sort_keys=True),
            json.dumps(shipped.get(k), sort_keys=True),
        )
        if a != b and k != "rows":
            print(f"  TOP-LEVEL {k}: regen={a[:120]}  shipped={b[:120]}")

    ra = {r["name"]: r for r in regen["rows"]}
    rb = {r["name"]: r for r in shipped["rows"]}
    print(
        f"  rows regen={len(ra)} shipped={len(rb)}  names differ={sorted(set(ra) ^ set(rb))}"
    )
    fields: dict[str, int] = {}
    example: dict[str, tuple[str, str]] = {}
    for name in sorted(set(ra) & set(rb)):
        for f in sorted(set(ra[name]) | set(rb[name])):
            x, y = ra[name].get(f), rb[name].get(f)
            if json.dumps(x, sort_keys=True) != json.dumps(y, sort_keys=True):
                fields[f] = fields.get(f, 0) + 1
                example.setdefault(f, (f"{name}: {x!r}"[:150], f"{name}: {y!r}"[:150]))
    for f, n in sorted(fields.items(), key=lambda kv: -kv[1]):
        print(f"  FIELD {f}: differs on {n}/{len(set(ra) & set(rb))} rows")
        print(f"        regen   {example[f][0]}")
        print(f"        shipped {example[f][1]}")
    print(f"SUCCESS:i4-determinism-diff {len(fields)} differing field(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
