"""Register ADV-0034's artifact in command-center/UNIT-ARTIFACT-MANIFEST.json, then RE-VERIFY it
with the repo's own condition-11 function under a both-states control.

Same mechanism as command-center/_adv0041_register.py (STRUCTURAL-CONDITION-11.md option 1: a
per-unit manifest that receipts may append to). ARTIFACT-MANIFEST.json is a RENDERED file over a
fixed 14-name tuple and cannot hold a unit output. This script MERGES the ADV-0034 row into the
existing manifest WITHOUT clobbering any other unit's row (e.g. ADV-0041), records the artifact's
TRUE LF sha256, and then calls platform/lib/completion_predicate.py::_c11_manifest in-process:
GOOD state (row present) must be SATISFIED and BAD state (row absent) must NOT be SATISFIED.

RUN
    python command-center/_register_adv0034.py            # register + verify (both-states)
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
ART_REL = "command-center/adversarial/ADV-0034-resource-exhaustion-dos-bounds.json"
MAN_REL = "command-center/UNIT-ARTIFACT-MANIFEST.json"
BAD_REL = "command-center/_adv0034_control_manifest_EMPTY.json"
UNIT = "ADV-0034"


def _serialise(obj: Any) -> bytes:
    return (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _write(rel: str, obj: Any) -> None:
    p = REPO / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as fh:
        fh.write(_serialise(obj))


def _load_predicate():
    libdir = str(REPO / "platform" / "lib")
    if libdir not in sys.path:
        sys.path.insert(0, libdir)
    spec = importlib.util.spec_from_file_location(
        "cp_adv34", REPO / "platform/lib/completion_predicate.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def run_c11(receipt: dict[str, Any], man_path_override: str | None = None) -> tuple[str, str]:
    cp = _load_predicate()
    opts = cp.PredicateOptions(repo_root=REPO, output_schema="command-center/schema/exploit-proof.schema.json")
    rec = json.loads(json.dumps(receipt))
    if man_path_override is not None:
        rec["manifest_registration"]["manifest_path"] = man_path_override
    outcome, basis, _detail = cp._c11_manifest(rec, opts)
    return (str(getattr(outcome, "value", outcome)), basis)


def main() -> int:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    raw = (REPO / ART_REL).read_bytes()
    true_sha = hashlib.sha256(raw).hexdigest()
    receipt = json.loads(raw.decode("utf-8"))

    # ---- MERGE into the existing manifest (preserve every other unit's row) --------------------
    man_path = REPO / MAN_REL
    if man_path.is_file():
        man = json.loads(man_path.read_text(encoding="utf-8"))
    else:
        man = {"schema_version": 1, "kind": "unit-artifact-manifest", "artifacts": []}
    man.setdefault("artifacts", [])
    row = {
        "path": ART_REL,
        "unit_id": UNIT,
        "present": True,
        "bytes": len(raw),
        "sha256": true_sha,
        "eol": "LF",
        "registered_at": now,
    }
    others = [e for e in man["artifacts"] if isinstance(e, dict) and e.get("path") != ART_REL]
    man["artifacts"] = others + [row]
    man["generated_at"] = now
    _write(MAN_REL, man)
    print(f"registered {UNIT}: true LF sha256={true_sha[:16]} bytes={len(raw)} "
          f"(manifest now holds {len(man['artifacts'])} unit rows: "
          f"{[e.get('unit_id') for e in man['artifacts']]})")

    # ---- GOOD state --------------------------------------------------------------------------
    good_outcome, good_basis = run_c11(receipt)
    print("condition 11 (GOOD state):", good_outcome, "|", good_basis)

    # ---- BAD state (both-states control): same receipt, manifest with ADV-0034 removed --------
    bad_man = json.loads(json.dumps(man))
    bad_man["artifacts"] = [e for e in bad_man["artifacts"] if e.get("path") != ART_REL]
    _write(BAD_REL, bad_man)
    bad_outcome, bad_basis = run_c11(receipt, man_path_override=BAD_REL)
    print("condition 11 (BAD  state):", bad_outcome, "|", bad_basis)

    ok = good_outcome == "SATISFIED" and bad_outcome != "SATISFIED"
    print("SUCCESS:adv0034-register" if ok else "FAILED:adv0034-register")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
