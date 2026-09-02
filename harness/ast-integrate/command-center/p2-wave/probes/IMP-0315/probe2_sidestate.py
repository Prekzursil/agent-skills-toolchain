#!/usr/bin/env python3
"""Named probe 2: side-state negative control + process-restart audit.

Starts from the tests, not the author's summary (reviewer_requirement).

1) Audit tools/council/artifacts/store.py for mutable module attributes that
   would survive a process restart. The honest store must have none.
2) Negative control: inject one extra vote as side state into a mutant
   rebuild. The mutant artifact MUST diverge from rebuild_from_log. The
   unmutated rebuild MUST still match the recorded artifact.
3) Append-only: rewrite() is refused; tampering with one historical line
   in a copy of the log must trip IntegrityError.
4) Subprocess restart: a child process that only imports the module must
   see the same empty mutable-survivor list.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from scenario import fixture_root, write_fixtures  # noqa: E402
from tools.council.artifacts.store import (  # noqa: E402
    AppendOnlyError,
    EventStore,
    IntegrityError,
    artifact_from_state,
    audit_module_side_state,
    canonical_bytes,
    fold_events,
    load_events,
    rebuild_from_log,
)

ART = REPO / "command-center/receipts/IMP-0315.json"
CHILD = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from tools.council.artifacts.store import audit_module_side_state
print(json.dumps(audit_module_side_state()))
"""


def _check_receipt() -> str | None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "receipt missing"
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"receipt unparseable: {exc}"
    if "SUCCESS:IMP-0315" not in text:
        return "sentinel absent"
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared {st}"
    return None


def mutant_rebuild(log: Path) -> bytes:
    """Rebuild that consults one piece of side state not in the log."""
    state = fold_events(load_events(log))
    ghost = {
        "seq": 999,
        "round": 99,
        "actor": "ghost-side-state",
        "choice": "invented-vote",
        "ts": "not-in-log",
    }
    state["votes"] = list(state["votes"]) + [ghost]
    return canonical_bytes(artifact_from_state(state))


def main() -> int:
    rec_err = _check_receipt()
    if rec_err:
        print(f"FAILED:IMP-0315-probe2 {rec_err}")
        return 1

    write_fixtures(fixture_root())

    audit = audit_module_side_state()
    if not audit["clean"] or audit["mutable_survivors"]:
        print("FAILED:IMP-0315-probe2 module side-state survivors")
        print(json.dumps(audit, indent=2)[:4000])
        return 1

    child = subprocess.run(
        [sys.executable, "-B", "-c", CHILD, str(REPO)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if child.returncode != 0:
        print("FAILED:IMP-0315-probe2 child audit rc", child.returncode, child.stderr[-1500:])
        return 1
    child_audit = json.loads(child.stdout.strip().splitlines()[-1])
    if child_audit.get("survives_process_restart"):
        print("FAILED:IMP-0315-probe2 child saw surviving side state")
        print(child.stdout)
        return 1

    log = fixture_root() / "c-split-dissent" / "events.jsonl"
    original = (fixture_root() / "c-split-dissent" / "artifact.json").read_bytes()
    if not log.is_file():
        print("FAILED:IMP-0315-probe2 fixture missing; run probe1 first")
        return 1
    clean = rebuild_from_log(log)
    dirty = mutant_rebuild(log)
    diverged = dirty != clean
    clean_matches = clean == original
    if not diverged:
        print("FAILED:IMP-0315-probe2 side-state injection did not diverge (control inert)")
        return 1
    if not clean_matches:
        print("FAILED:IMP-0315-probe2 clean rebuild drifted from recorded artifact")
        return 1
    if hashlib.sha256(dirty).hexdigest() == hashlib.sha256(clean).hexdigest():
        print("FAILED:IMP-0315-probe2 mutant hash collided")
        return 1

    store = EventStore(log)
    rewrite_refused = False
    try:
        store.rewrite()
    except AppendOnlyError:
        rewrite_refused = True
    if not rewrite_refused:
        print("FAILED:IMP-0315-probe2 rewrite was not refused")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0315-p2-") as tmp:
        tampered = Path(tmp) / "tampered.jsonl"
        lines = log.read_text(encoding="utf-8").splitlines()
        if len(lines) < 4:
            print("FAILED:IMP-0315-probe2 log too short to tamper")
            return 1
        obj = json.loads(lines[2])
        obj["payload"] = dict(obj.get("payload") or {}, text="TAMPER")
        lines[2] = json.dumps(obj, sort_keys=True)
        tampered.write_text("\n".join(lines) + "\n", encoding="utf-8")
        fired = False
        try:
            rebuild_from_log(tampered)
        except IntegrityError:
            fired = True
        if not fired:
            print("FAILED:IMP-0315-probe2 tamper was not detected")
            return 1

    out = {
        "pass": True,
        "probe": "probe2-side-state-negative-control",
        "unit_id": "IMP-0315",
        "audit_clean": audit["clean"],
        "mutable_survivors": audit["mutable_survivors"],
        "child_restart_clean": not child_audit.get("survives_process_restart"),
        "side_state_diverged": diverged,
        "clean_matches_original": clean_matches,
        "rewrite_refused": rewrite_refused,
        "tamper_integrity_fired": True,
        "reviewer_id": "IMP-0315-probe2-sidestate",
        "reviewer_verdict": "PASS",
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:IMP-0315-probe2 side-state negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
