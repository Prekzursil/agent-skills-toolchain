"""Both-states probe for ``ci/tests/test_program_b_register.py``.

A suite that cannot go red measures nothing
(``rules/common/single-signal-verification.md`` rule 3b). This applies one defect at a
time to a COPY of the receipt and requires the suite to FAIL each time.

INTENTIONALLY SEPARATE from the repo's other mutation probes, which are not a shared
library: ``.agents/skills/mutation-check/mutation_check.py`` is an AST mutator for
Python SOURCE (boolean flips, comparison swaps) and cannot mutate a JSON data file,
and ``tools/mcp/mcp-host-supervisor/tests/mutation_probe.py`` is a per-package string
substituter with module-level ``sys.argv`` that is not importable. The name follows the
established per-package convention rather than duplicating an engine.

The committed receipt is NEVER touched: each mutation is written to a temp copy and the
suite is pointed at it with ``PROGRAM_B_RECEIPT``.

Run from the repo root::

    python docs/program-b/mutation_probe.py
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RECEIPT = REPO_ROOT / "docs" / "program-b" / "program-b-receipt.json"
SUITE = "ci/tests/test_program_b_register.py"


def drop_item(doc: dict) -> dict:
    doc["items"] = [i for i in doc["items"] if i["id"] != "R-B05"]
    return doc


def free_text_status(doc: dict) -> dict:
    doc["items"][0]["status"] = "mostly done"
    return doc


def bad_subitem_status(doc: dict) -> dict:
    next(i for i in doc["items"] if i.get("subitems"))["subitems"][0]["status"] = "ok"
    return doc


def gut_id_map(doc: dict) -> dict:
    doc["id_map"].pop("B4", None)
    return doc


def half_fill_id_map(doc: dict) -> dict:
    doc["id_map"]["B3"] = {"canonical": "awesome-game-security"}
    return doc


def unflag_owner_only(doc: dict) -> dict:
    next(i for i in doc["items"] if i["id"] == "R-B08")["owner_only"] = False
    return doc


def erase_interleave_guard(doc: dict) -> dict:
    doc["authority"]["sequencing"] = "run A then B"
    for item in doc["items"]:
        item.pop("what_changed", None)
        item.pop("correction_to_register", None)
    return doc


def erase_session_name_guard(doc: dict) -> dict:
    doc["note"] = "a program about Claude Code Workflows"
    return doc


def claim_rotation_done(doc: dict) -> dict:
    row = next(i for i in doc["items"] if i["id"] == "R-B08")
    row["status"] = "DONE-VERIFIED"
    row["rotation"] = "rotated the keys"
    return doc


def blank_a_title(doc: dict) -> dict:
    doc["items"][2]["title"] = "   "
    return doc


MUTATIONS = {
    "drop-an-item": drop_item,
    "free-text-status": free_text_status,
    "bad-subitem-status": bad_subitem_status,
    "gut-the-id-map": gut_id_map,
    "half-fill-the-id-map": half_fill_id_map,
    "unflag-owner-only": unflag_owner_only,
    "erase-interleave-guard": erase_interleave_guard,
    "erase-session-name-guard": erase_session_name_guard,
    "claim-rotation-done": claim_rotation_done,
    "blank-a-title": blank_a_title,
}


def run_suite(receipt_path: Path | None = None) -> int:
    env = dict(os.environ)
    if receipt_path is None:
        env.pop("PROGRAM_B_RECEIPT", None)
    else:
        env["PROGRAM_B_RECEIPT"] = str(receipt_path)
    return subprocess.run(
        [sys.executable, "-m", "pytest", SUITE, "-q"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    ).returncode


def main() -> int:
    original = json.loads(RECEIPT.read_text(encoding="utf-8"))
    before = RECEIPT.read_bytes()

    if run_suite() != 0:
        print("FAILED:mutation-probe baseline is already red; fix the suite first")
        return 1
    print("baseline (committed receipt) -> PASS")

    survivors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="pb_mut_") as tmp:
        target = Path(tmp) / "program-b-receipt.json"
        # Control: an UNMUTATED copy behind the override must still pass, otherwise a
        # "KILLED" below could just mean the override itself breaks the suite.
        target.write_text(json.dumps(original, indent=2) + "\n", encoding="utf-8")
        if run_suite(target) != 0:
            print("FAILED:mutation-probe the unmutated COPY is red; override is broken")
            return 1
        print("control (unmutated copy via override) -> PASS")

        for name, mutate in MUTATIONS.items():
            doc = mutate(copy.deepcopy(original))
            target.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
            killed = run_suite(target) != 0
            print(f"  {name:26s} -> {'KILLED' if killed else 'SURVIVED'}")
            if not killed:
                survivors.append(name)

    if RECEIPT.read_bytes() != before:
        print("FAILED:mutation-probe the committed receipt changed; it must not")
        return 1
    if survivors:
        print(f"FAILED:mutation-probe survivors={survivors}")
        return 1
    print(f"SUCCESS:mutation-probe {len(MUTATIONS)}/{len(MUTATIONS)} killed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
