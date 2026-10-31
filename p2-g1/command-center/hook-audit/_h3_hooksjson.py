r"""H3 — what hooks/hooks.json actually wires (the Codex-side plane).

Every command is wrapped in run-with-flags.js, so the REAL target is an
argument, not the first path in the string. H2's first pass matched only the
wrapper and reported 0 dirs -- a detector failure, corrected here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
OUT = REPO / "command-center" / "hook-audit"
PAT = re.compile(r"hooks[/\\]([A-Za-z0-9_.-]+)[/\\]([A-Za-z0-9_.-]+\.(?:py|js|mjs|sh))")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    doc = json.loads((REPO / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    rows, dirs = [], set()
    for ev, groups in doc["hooks"].items():
        for g in groups:
            for hk in g.get("hooks") or []:
                cmd = hk.get("command", "")
                hits = PAT.findall(cmd)
                targets = [f"{a}/{b}" for a, b in hits if a not in ("_dispatch",)]
                wrapper = [f"{a}/{b}" for a, b in hits if a in ("_dispatch",)]
                rows.append(
                    {
                        "event": ev,
                        "matcher": g.get("matcher"),
                        "timeout": hk.get("timeout"),
                        "targets": targets,
                        "wrapper": wrapper,
                        "raw": cmd,
                    }
                )
                dirs.update(t.split("/")[0] for t in targets)
    # control: a known target must be found; a nonsense one must not
    if not dirs:
        print("FAILED:h3 no target dirs extracted -- detector still broken")
        return 1
    (OUT / "H3-HOOKSJSON.json").write_text(
        json.dumps({"rows": rows, "dirs": sorted(dirs)}, indent=2), encoding="utf-8"
    )
    for r in rows:
        print(
            f"{r['event']:19s} {str(r['matcher'])[:24]:24s} to={str(r['timeout']):4s} {r['targets']}"
        )
    print(f"\nDIRS referenced by hooks.json ({len(dirs)}): {sorted(dirs)}")
    print("SUCCESS:h3-hooksjson")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
