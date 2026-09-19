"""C11 lane: cross-consumer probe -- does completion_predicate._c11_manifest
(the STRONG condition-11 consumer: membership + digest, not just file-exists)
read the new manifest shape correctly? A registered=true row's artifact must
score SATISFIED, and the same receipt against an empty manifest must go red.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
LIB = ROOT / "platform/lib"
sys.path.insert(0, str(LIB))

spec = importlib.util.spec_from_file_location("cp", LIB / "completion_predicate.py")
cp = importlib.util.module_from_spec(spec)
sys.modules["cp"] = cp  # dataclasses resolves cls.__module__ through sys.modules
spec.loader.exec_module(cp)

man = json.loads(
    (ROOT / "command-center/UNIT-ARTIFACT-MANIFEST.json").read_text(encoding="utf-8")
)
row = next(r for r in man["artifacts"] if r["receipt_registered"] is True)
probe = {
    "unit_id": row["unit_id"],
    "state": "SUCCESS",
    "artifacts": [
        {
            "path": row["path"],
            "sha256": row["sha256"],
            "bytes": row["bytes"],
            "role": "primary",
            "eol": "LF",
        }
    ],
    "manifest_registration": {
        "registered": True,
        "manifest_path": "command-center/UNIT-ARTIFACT-MANIFEST.json",
    },
}


def cond11(receipt, root):
    opts = (
        cp.PredicateOptions(repo_root=root) if hasattr(cp, "PredicateOptions") else None
    )
    fn = cp._c11_manifest
    try:
        out = fn(receipt, opts)
    except TypeError:
        out = fn(receipt)
    # _c11_manifest returns (Outcome, reason, detail) per the grep of its shape
    if isinstance(out, tuple):
        return f"{out[0]}: {out[1]}" if len(out) > 1 else str(out[0])
    return str(out)


print("good-state (repo root):", cond11(probe, ROOT))
with tempfile.TemporaryDirectory() as td:
    empty_root = pathlib.Path(td)
    (empty_root / "command-center").mkdir()
    (empty_root / "command-center/UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps({"artifacts": []}), encoding="utf-8"
    )
    print("bad-state (empty manifest):", cond11(probe, empty_root))
print("SUCCESS:c11-crossconsumer probe complete")
