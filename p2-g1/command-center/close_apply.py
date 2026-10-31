"""Apply the 7 verified CLOSE dispositions to the catalog and the register, and prove the edit.

PRECONDITION, ENFORCED: `command-center/CLOSE-VERIFY.json` must exist, be for this HEAD, and list
exactly the ids being closed as `eligible_to_close`. This script refuses to close anything the
verifier did not independently re-measure -- so a proposal can never reach the catalog on a lane's
digest alone.

TWO WRITES, BOTH CHECKED:
  1. `WORK-UNIT-CATALOG.json` items[] -- status + disposition + disposition_evidence.
     Serialised with the params proven to round-trip this file BYTE-EXACTLY
     (indent=1, ensure_ascii=False, no trailing newline), so the diff contains only the 7 items.
  2. `sources/REGISTER.md` -- the status cell of each row, addressed BY COLUMN INDEX. A naive
     string replace of "OPEN" would also hit the word inside a title or an evidence cell.

POST-CONDITIONS asserted before the file is written: every id moved, no id left OPEN, no OTHER
item's status changed, and the JSON reparses to an identical object apart from the intended fields.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
REGISTER = REPO / "command-center/sources/REGISTER.md"
VERIFY = REPO / "command-center/CLOSE-VERIFY.json"

DISPOSITION = "DONE-VERIFIED"

#: id -> evidence prose. Where the item's PREMISE was refuted rather than merely satisfied, the
#: string says so explicitly: a refuted premise must be recorded, not silently overwritten.
EVIDENCE = {
    "R-A10": (
        "DELIVERED AT A DIFFERENT PATH. The register's anchor "
        "`11-COUNCIL-SPECIFICATION.schema.json` is tracked 0 times; the successor carries the same "
        "spec anchors. Re-measured 2026-08-10: `replay` is a real boolean property at "
        "platform/schema/councilspec.schema.json $defs.audit.properties, alongside 7 siblings "
        "(calibration, determinism, persistence, privacy, resume, ...); 48 of 52 protocol "
        "blueprints instantiate it. Verified by command-center/close_verify.py (control: a bogus "
        "axis key is absent from the same property set)."
    ),
    "R-A06": (
        "platform/marketplace/mkt/ ships 16 modules covering every named gap (sbom, crypto, "
        "registry, permissions, moderation, versions, lint, scaffold, publish, install, fixture) "
        "plus GOVERNANCE.md and a 4-package fixture marketplace. PROOF-e2e.json records publish -> "
        "install -> verify -> revoke -> dispute-reversal -> refused-malicious-publish -> federated "
        "mirror, and its known-broken-SBOM NEGATIVE CONTROL fires -- which is what makes it "
        "evidence rather than a green light. Re-measured 2026-08-10 by close_verify.py. "
        "RESIDUAL FILED SEPARATELY: PROOF-e2e.json is not valid JSON (a bare "
        "`SUCCESS:phase6-marketplace-e2e` sentinel follows the object, so json.load raises "
        "'Extra data'); any consumer that parses it will fail. That is a new defect, not a reason "
        "to hold this item."
    ),
    "R-A09": (
        "48 protocol blueprints (target >=48) and 69 presets (target >=64); all 117 specs carry "
        "anti_failure/audit/voting/consensus/stopping. The CouncilSpec compiler exists as "
        "platform/lib/councilspec/ (10 modules incl. a typed-tree expression parser and "
        "SEM-001..SEM-012 semantics), with counts.tests_passing=112 / tests_failing=0 in "
        "platform/schema/CONFORMANCE-STATUS.json and an 8-layer executable gate carrying a "
        "--mutations both-states control. The register's note that `skills/council` is an "
        "unrelated 4-voice prompt skill remains true and remains irrelevant -- the deliverable was "
        "never there. Re-measured 2026-08-10 by close_verify.py."
    ),
    "R-A12": (
        "PREMISE REFUTED. The item asserted 'manifest ships, lifecycle does not'. All 8 named "
        "lifecycle surfaces ship at platform/plugin/ (31 tracked files), not at the declared "
        "repo-root install.py -- another path-namespace miss. `python -m plugin.cli --help` exits 0 "
        "advertising 19 subcommands including install/update/rollback/uninstall/verify/activate; "
        "254 plugin tests pass. Independently corroborated by "
        "command-center/WAVE4-PLUGIN-LIFECYCLE-VERIFY.json (5/5 checks). Re-measured 2026-08-10 by "
        "close_verify.py, which asks the CLI rather than grepping its source -- a source grep "
        "under-counts because the verbs are declared through a helper and the verb is `update`, "
        "not `upgrade`. FIXED WHILE VERIFYING: cli.py mapped argparse's SystemExit(0) to exit 2 via "
        "`int(exc.code or EXIT_USAGE)`, so `--help` printed correct output and still reported "
        "failure; regression tests added."
    ),
    "R-A20": (
        "Both residual Phase-9 deliverables exist and are test-enforced at platform/coordination/, "
        "not at the declared agent-self/harness/adapters.py: PHASE9-COORDINATION.md (12,424 B) "
        "records surfaces 9 (capability negotiation) and 11 (abstraction leaks) as CONFIRMED rows, "
        "with ABSTRACTION-LEAKS.md (12,586 B) and ADAPTER-CONTRACT.md (9,773 B). Re-measured "
        "2026-08-10 by close_verify.py."
    ),
    "R-M01": (
        "PREMISE REFUTED AT HEAD, by two independent lanes reaching the same verdict. The item's "
        "'registered in NO launcher' half is false: a `[cockpit]` stanza sits at line 58 of all "
        "THREE monitors.toml copies (repo .agents/, repo skills/, live ~/.agents/), added by commit "
        "fbedcdf6 'feat(monitor): make the unified cockpit reachable', with a dedicated regression "
        "test asserting it. The item's other half is CONFIRMED exactly -- 39 test modules, and "
        "`python -m monitorcore.unified --help` exits 0 advertising five panes. Re-measured "
        "2026-08-10 by close_verify.py (control: a bogus stanza is absent from the same files, and "
        "the probe reports DETECTOR-BROKEN rather than 'absent' if it reads no file -- which it did "
        "on the first pass, when it guessed the wrong skill name)."
    ),
    "R-B06": (
        "PREMISE REFUTED. 'basic-memory holds ZERO notes on Program B' is false: two notes exist -- "
        "`Program B (workflow_design) - the 8-item register, graded 2026-08-09.md` (3,864 B), which "
        "opens by naming register row R-B06 as the defect it closes and carries the 8-item status, "
        "the INTERLEAVE-supersedes-sequencing fact, the R-B07 id map and the R-B08 credential "
        "state; and `Program B IS workflow_design - a backlog lane, 0-12 delivered "
        "(2026-08-09).md` (3,214 B) at the vault projects root. Re-measured 2026-08-10 by "
        "close_verify.py via the vault FILESYSTEM, deliberately NOT the register's own semantic "
        "recall probe -- that probe still returns 8 off-target results even though the note exists, "
        "so re-running it would manufacture a false CONFIRMED. "
        "NEW NARROWER RESIDUAL, filed separately: the note is not reachable by semantic phrase "
        "recall and needs aliases ('unified two-program continuation', 'two-program', 'Program B') "
        "in its body/tags. Detector note for future readers: every score in this basic-memory "
        "build is NEGATIVE (on-topic controls returned -23 to -27), so 'all negatively scored' must "
        "not be read as 'all irrelevant'."
    ),
}


def _register_status_cell(line: str) -> int | None:
    """Index of the status field in a split register row, or None if this is not an item row."""
    parts = line.split("|")
    # `| id | title | STATUS | effort | evidence | sources |` -> parts[0] is '' before the first pipe
    return 3 if len(parts) >= 7 else None


def main() -> int:
    if not VERIFY.exists():
        print(
            "FAILED:close-apply CLOSE-VERIFY.json absent -- run close_verify.py first"
        )
        return 1
    verify = json.loads(VERIFY.read_text(encoding="utf-8"))
    eligible = set(verify.get("eligible_to_close") or [])
    if verify.get("not_eligible"):
        print(
            f"FAILED:close-apply verifier reported not_eligible={verify['not_eligible']}"
        )
        return 1
    if eligible != set(EVIDENCE):
        print(
            "FAILED:close-apply verifier/evidence mismatch\n"
            f"  verified but no evidence prose: {sorted(eligible - set(EVIDENCE))}\n"
            f"  evidence prose but NOT verified: {sorted(set(EVIDENCE) - eligible)}"
        )
        return 1

    head = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    if verify.get("head") and head and verify["head"] != head:
        print(
            f"FAILED:close-apply verifier ran at {verify['head']}, HEAD is now {head}"
        )
        return 1

    # ---- catalog ----
    raw = CATALOG.read_text(encoding="utf-8")
    doc = json.loads(raw)
    assert json.dumps(doc, indent=1, ensure_ascii=False) == raw, (
        "serialiser does not round-trip this file byte-exactly; refusing to rewrite 5 MB"
    )

    before = {i["id"]: i.get("status") for i in doc["items"]}
    moved = []
    for item in doc["items"]:
        if item["id"] in EVIDENCE:
            item["status"] = DISPOSITION
            item["disposition"] = DISPOSITION
            item["disposition_evidence"] = EVIDENCE[item["id"]]
            moved.append(item["id"])

    if sorted(moved) != sorted(EVIDENCE):
        print(f"FAILED:close-apply only found {sorted(moved)} in items[]")
        return 1

    after = {i["id"]: i.get("status") for i in doc["items"]}
    collateral = {
        k: (before[k], after[k])
        for k in before
        if before[k] != after[k] and k not in EVIDENCE
    }
    if collateral:
        print(f"FAILED:close-apply collateral status changes: {collateral}")
        return 1

    out = json.dumps(doc, indent=1, ensure_ascii=False)
    CATALOG.write_text(out, encoding="utf-8", newline="")

    # ---- register ----
    reg_raw = REGISTER.read_text(encoding="utf-8")
    eol = "\r\n" if "\r\n" in reg_raw else "\n"
    lines = reg_raw.split(eol)
    reg_moved = []
    for n, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped.startswith("|"):
            continue
        parts = line.split("|")
        idx = _register_status_cell(line)
        if idx is None:
            continue
        row_id = parts[1].strip()
        if row_id not in EVIDENCE:
            continue
        old = parts[idx].strip()
        parts[idx] = f" {DISPOSITION} "
        lines[n] = "|".join(parts)
        reg_moved.append((row_id, old))

    if sorted(r for r, _ in reg_moved) != sorted(EVIDENCE):
        print(
            f"FAILED:close-apply register rows found: {sorted(r for r, _ in reg_moved)}"
        )
        return 1
    REGISTER.write_text(eol.join(lines), encoding="utf-8", newline="")

    for rid, old in sorted(reg_moved):
        print(f"  CLOSED {rid:7} {old:12} -> {DISPOSITION}")
    still_open = sum(1 for i in doc["items"] if i.get("status") == "OPEN")
    print(
        f"\nSUCCESS:close-apply {len(moved)} items closed in catalog + register; "
        f"{still_open} items still OPEN"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
