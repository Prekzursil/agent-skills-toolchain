"""Program B (``workflow_design``) register -- the gate that gives it a CONSUMER.

Register row **R-B05** is ``Zero consumers reach any Program-B artifact``: four
mechanically independent, detector-controlled probes found that nothing in the repo,
the hooks, the skills, the workflows, the agents or the commands tree ever reads a
Program-B artifact. A backlog nobody reads gets dropped -- it was dropped three times.

This suite is the fix. It makes CI read ``docs/program-b/program-b-receipt.json`` on
every pull request, so the register cannot silently drift, silently lose an item, or be
silently deleted. That is a mechanical consumer, not another document.

What it pins, and why each one is load-bearing:

* **Every id survives.** All eight register rows R-B01..R-B08 must be present. An item
  that quietly disappears from the receipt is exactly the failure mode being closed.
* **Status comes from a CLOSED vocabulary.** A free-text status is how ``done`` gets
  asserted without a grade. Sub-items may additionally be ``NOT-CHECKED`` -- typed
  silence is a legitimate terminal state and must never be folded into a pass.
* **The two anti-re-litigation facts stay stated.** The INTERLEAVE decision superseded
  only the SEQUENCING (not the items), and ``workflow_design`` is a session name
  unrelated to Claude Code Workflows. Deleting either sentence is what caused the drop,
  so deleting it now fails a test.
* **The id map is complete.** B3/B4/B5 mean different things in the two authoritative
  documents; an ambiguous id is how an item gets closed twice or never.
* **Owner-only rows say so.** R-B08 is a credential exposure whose remediation is the
  owner's alone (AGENTS.md section 9). The receipt must keep carrying that flag.
* **The prose view agrees with the JSON.** ``README.md`` is the human-readable face of
  the same data; if it stops naming an id, the two have diverged.

DETECTOR CONTROL (rules/common/single-signal-verification.md rule 3b): a suite that
cannot go red measures nothing, so ``test_control_*`` feeds each predicate a synthetic
KNOWN-BAD receipt and requires it to FIRE. A green run is then evidence about the
receipt rather than evidence that the checker stopped working.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs" / "program-b"
README_PATH = DOCS / "README.md"

# The committed receipt is the default and the only thing CI ever reads. The override
# exists so docs/program-b/mutation_probe.py can run the both-states check against a
# COPY in a temp directory -- a probe that mutated the committed artifact in place
# would risk corrupting it on a crash. Fail-closed: a bogus override makes
# test_receipt_and_readme_exist fail rather than silently pass.
RECEIPT_PATH = Path(
    os.environ.get("PROGRAM_B_RECEIPT") or (DOCS / "program-b-receipt.json")
)

EXPECTED_IDS = (
    "R-B01",
    "R-B02",
    "R-B03",
    "R-B04",
    "R-B05",
    "R-B06",
    "R-B07",
    "R-B08",
)
COLLIDING_IDS = ("B3", "B4", "B5")
OWNER_ONLY_IDS = ("R-B08",)


def load_receipt() -> dict[str, Any]:
    return json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------------------
# the predicates, written once so the control tests can run the SAME code on a bad input
# --------------------------------------------------------------------------------------


def missing_ids(receipt: dict[str, Any]) -> list[str]:
    present = {item.get("id") for item in receipt.get("items", [])}
    return [wanted for wanted in EXPECTED_IDS if wanted not in present]


def bad_statuses(receipt: dict[str, Any]) -> list[str]:
    allowed = set(receipt.get("status_vocabulary", ()))
    sub_allowed = set(receipt.get("subitem_status_vocabulary", ()))
    offenders: list[str] = []
    for item in receipt.get("items", []):
        if item.get("status") not in allowed:
            offenders.append(f"{item.get('id')}={item.get('status')!r}")
        for sub in item.get("subitems", []):
            if sub.get("status") not in sub_allowed:
                offenders.append(f"{sub.get('id')}={sub.get('status')!r}")
    return offenders


def missing_id_map_entries(receipt: dict[str, Any]) -> list[str]:
    id_map = receipt.get("id_map", {})
    gaps: list[str] = []
    for key in COLLIDING_IDS:
        entry = id_map.get(key)
        if not isinstance(entry, dict):
            gaps.append(key)
            continue
        if not entry.get("canonical") or not entry.get("stale_backlog_meaning"):
            gaps.append(key)
    return gaps


def unflagged_owner_only(receipt: dict[str, Any]) -> list[str]:
    by_id = {item.get("id"): item for item in receipt.get("items", [])}
    return [
        wanted
        for wanted in OWNER_ONLY_IDS
        if by_id.get(wanted, {}).get("owner_only") is not True
    ]


def missing_interleave_guard(receipt: dict[str, Any]) -> bool:
    """The sequencing was superseded; the ITEMS were not. Both halves must be said."""
    text = json.dumps(receipt).upper()
    return not (
        "INTERLEAVE" in text and "SEQUENCING" in text and "NOT SUPERSEDED" in text
    )


def missing_session_name_guard(receipt: dict[str, Any]) -> bool:
    return receipt.get("session_name") != "workflow_design" or "SESSION NAME" not in (
        receipt.get("note", "").upper()
    )


# --------------------------------------------------------------------------------------
# the real assertions, against the committed receipt
# --------------------------------------------------------------------------------------


def test_receipt_and_readme_exist() -> None:
    assert RECEIPT_PATH.is_file(), f"missing {RECEIPT_PATH}"
    assert README_PATH.is_file(), f"missing {README_PATH}"


def test_receipt_is_valid_json() -> None:
    assert isinstance(load_receipt(), dict)


def test_every_register_row_survives() -> None:
    assert missing_ids(load_receipt()) == []


def test_statuses_come_from_the_closed_vocabulary() -> None:
    assert bad_statuses(load_receipt()) == []


def test_id_collision_map_is_complete() -> None:
    assert missing_id_map_entries(load_receipt()) == []


def test_owner_only_rows_are_flagged() -> None:
    assert unflagged_owner_only(load_receipt()) == []


def test_interleave_supersedes_sequencing_only() -> None:
    assert not missing_interleave_guard(load_receipt())


def test_workflow_design_is_named_as_a_session_name() -> None:
    assert not missing_session_name_guard(load_receipt())


def test_credential_row_never_claims_rotation() -> None:
    """AGENTS.md section 9: an agent must never rotate. The row must say so, and must
    not be gradeable as done while the exposure stands."""
    row = next(i for i in load_receipt()["items"] if i["id"] == "R-B08")
    assert row["status"] in {"OPEN", "IN-FLIGHT"}
    assert "NOT PERFORMED" in row["rotation"].upper()


def test_readme_names_every_id() -> None:
    prose = README_PATH.read_text(encoding="utf-8")
    assert [wanted for wanted in EXPECTED_IDS if wanted not in prose] == []


@pytest.mark.parametrize("item_id", EXPECTED_IDS)
def test_every_item_carries_a_title(item_id: str) -> None:
    row = next(i for i in load_receipt()["items"] if i["id"] == item_id)
    assert row.get("title", "").strip(), f"{item_id} has no title"


# --------------------------------------------------------------------------------------
# DETECTOR CONTROLS -- each predicate must FIRE on a known-bad receipt
# --------------------------------------------------------------------------------------


def test_control_missing_id_is_detected() -> None:
    bad = copy.deepcopy(load_receipt())
    bad["items"] = [i for i in bad["items"] if i["id"] != "R-B03"]
    assert missing_ids(bad) == ["R-B03"]


def test_control_free_text_status_is_detected() -> None:
    bad = copy.deepcopy(load_receipt())
    bad["items"][0]["status"] = "basically done"
    assert bad_statuses(bad)


def test_control_subitem_status_is_also_checked() -> None:
    bad = copy.deepcopy(load_receipt())
    target = next(i for i in bad["items"] if i.get("subitems"))
    target["subitems"][0]["status"] = "probably fine"
    assert bad_statuses(bad)


def test_control_gutted_id_map_is_detected() -> None:
    bad = copy.deepcopy(load_receipt())
    del bad["id_map"]["B4"]
    assert missing_id_map_entries(bad) == ["B4"]


def test_control_half_filled_id_map_is_detected() -> None:
    bad = copy.deepcopy(load_receipt())
    bad["id_map"]["B5"] = {"canonical": "SWFOC"}
    assert missing_id_map_entries(bad) == ["B5"]


def test_control_unflagged_owner_only_is_detected() -> None:
    bad = copy.deepcopy(load_receipt())
    next(i for i in bad["items"] if i["id"] == "R-B08")["owner_only"] = False
    assert unflagged_owner_only(bad) == ["R-B08"]


def test_control_deleting_the_interleave_guard_is_detected() -> None:
    bad = copy.deepcopy(load_receipt())
    bad["authority"]["sequencing"] = "A then B"
    assert missing_interleave_guard(bad)


def test_control_deleting_the_session_name_guard_is_detected() -> None:
    bad = copy.deepcopy(load_receipt())
    bad["note"] = "a program about Claude Code Workflows"
    assert missing_session_name_guard(bad)


def test_control_predicates_pass_on_the_real_receipt() -> None:
    """The other half of the both-states test: the same predicates must be SILENT on
    the good input, so their firing above is about the mutation and not about them
    always firing."""
    good = load_receipt()
    assert missing_ids(good) == []
    assert bad_statuses(good) == []
    assert missing_id_map_entries(good) == []
    assert unflagged_owner_only(good) == []
    assert not missing_interleave_guard(good)
    assert not missing_session_name_guard(good)
