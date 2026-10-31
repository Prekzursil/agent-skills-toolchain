#!/usr/bin/env python3
"""IMP-0133 probe1: a credential-shaped literal in a param default is REFUSED
by agentspec export with the named violation; the refused dest is absent and an
independent raw-byte grep of the dest finds zero token hits."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.export import ExportRefused, export_workflow  # noqa: E402
import agentspec.violations as V  # noqa: E402

TOKEN = "ghp_" + "a1b2c3d4" * 4 + "ef"


def main() -> int:
    # the named violation id, read from the violations module (closed set)
    cred_ids = [v for k, v in vars(V).items()
                if k.startswith("PARAM_CREDENTIAL") and isinstance(v, str)]
    if not cred_ids:
        print("FAILED:IMP-0133-probe1 no PARAM_CREDENTIAL* id exported by agentspec.violations")
        return 1
    cred_id = cred_ids[0]

    dest_dir = Path(tempfile.mkdtemp(prefix="imp0133-"))
    dest = dest_dir / "wf.json"

    wf = SimpleNamespace(
        id="imp0133-literal",
        params=[
            SimpleNamespace(id="owner_token", kind="string", required=True, default=TOKEN,
                            secret_ref=None),
            SimpleNamespace(id="plain", kind="string", required=False, default="hello",
                            secret_ref=None),
        ],
    )
    refused = False
    reason_ids: list[str] = []
    try:
        export_workflow(wf, dest)
    except ExportRefused as exc:
        refused = True
        reason_ids = list(getattr(exc, "ids", []) or [])
    except Exception as exc:  # noqa: BLE001
        print("FAILED:IMP-0133-probe1 unexpected export error: %r" % (exc,))
        return 1

    dest_absent = not dest.exists()
    grep_hits = dest.read_bytes().count(TOKEN.encode()) if dest.exists() else 0
    named = cred_id in reason_ids

    result = {
        "unit_id": "IMP-0133",
        "probe": "probe1-literal-refused",
        "violation_id": cred_id,
        "refused": refused,
        "named_violation": named,
        "reason_ids": reason_ids,
        "refused_dest_absent": dest_absent,
        "independent_grep_hits": grep_hits,
        "pass": refused and named and dest_absent and grep_hits == 0,
    }
    print("RESULT:" + json.dumps(result))
    tail = ("SUCCESS:IMP-0133-probe1 literal refused by export with named violation; "
            "refused dest absent and zero token hits"
            if result["pass"] else
            "FAILED:IMP-0133-probe1 literal export contract broken")
    print(tail)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
