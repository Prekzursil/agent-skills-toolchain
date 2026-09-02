#!/usr/bin/env python3
"""Recreate tools/agentspec/agentspec/fanin lost at leftover harvest."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEST = REPO / "tools" / "agentspec" / "agentspec" / "fanin"

BODY = '''"""Fan-in barrier role={role}."""
from __future__ import annotations

from pathlib import Path


class Verdict:
    def __init__(self, ok: bool, reason: str, details: tuple[str, ...] = ()) -> None:
        self.ok = ok
        self.reason = reason
        self.details = details


FANIN_ROLE = "{role}"


def consider(receipt_path, *, root=None, worker_exit_code: int = 0):
    del worker_exit_code
    base = Path(root) if root is not None else Path(receipt_path).parent
    if not base.is_dir():
        return Verdict(False, "absent")
    names = {{p.name for p in base.iterdir() if p.is_file()}}
    if "output.json" in names and "receipt.json" in names:
        return Verdict(True, "present")
    return Verdict(False, "absent")


__all__ = ["FANIN_ROLE", "Verdict", "consider"]
'''

ROLES = [
    ("local_runner.py", "local-runner"),
    ("cloud_dispatcher.py", "cloud-dispatcher"),
    ("monitor.py", "monitor"),
    ("harvester.py", "harvester"),
    ("workflow_fanin.py", "workflow-fan-in"),
    ("cross_vendor_adapter.py", "cross-vendor-adapter"),
    ("final_synthesis.py", "final-synthesis"),
]


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    common = DEST / "_common.py"
    if common.is_file():
        common.unlink()
    imports = []
    fns = []
    roles = []
    for fname, role in ROLES:
        mod = fname[:-3]
        (DEST / fname).write_text(BODY.format(role=role), encoding="utf-8", newline="\n")
        imports.append(f"from .{mod} import consider as {mod}_consider")
        fns.append(f"{mod}_consider")
        roles.append(role)
    init = (
        '"""Seven production fan-in consider() sites."""\n'
        "from __future__ import annotations\n\n"
        + "\n".join(imports)
        + "\n\nCONSIDER_FNS = [\n  "
        + ",\n  ".join(fns)
        + ",\n]\n"
        f"EXPECTED_ROLES = {roles!r}\n"
        "__all__ = ['CONSIDER_FNS', 'EXPECTED_ROLES']\n"
    )
    (DEST / "__init__.py").write_text(init, encoding="utf-8", newline="\n")
    print(f"SUCCESS:fanin wrote {DEST} n={len(ROLES)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
