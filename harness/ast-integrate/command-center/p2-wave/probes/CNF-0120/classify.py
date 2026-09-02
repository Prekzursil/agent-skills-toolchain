#!/usr/bin/env python3
"""Three-state NOT-CHECKED integrity classifier for CNF-0120.

ABSENT, EMPTY, and GENUINE_ZERO are different states and must not be merged.

Rule A: an absent artifact directory is not evidence of nothing to check.
Rule B: a gate whose enforcement command cannot run emits NOT-CHECKED, not a silent pass.
Rule C: an unlabelled item with no probe lands in folded-into-pass.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
SELF_OUT = "command-center/confirmation/CNF-0120-not-checked-integrity.json"
FIXTURES = HERE / "fixtures"
ABSENT_DIR = FIXTURES / "absent-dir"
EMPTY_DIR = FIXTURES / "empty-result-set"
EMPTY_ARRAY = FIXTURES / "empty-result-set.json"
PLANTED = FIXTURES / "planted-unlabelled" / "receipt.json"
LABELLED = FIXTURES / "labelled-not-checked" / "receipt.json"
UNRUNNABLE = FIXTURES / "unrunnable-gate" / "gate.json"
GENUINE_SUBJECTS = FIXTURES / "genuine-zero" / "subjects"
GENUINE_RECEIPT = FIXTURES / "genuine-zero" / "receipt.json"
GENUINE_PROBE = HERE / "genuine_zero_probe.py"
UNRUNNABLE_BIN = "cnf-0120-no-such-enforcement-binary"

THREE = frozenset({"ABSENT", "EMPTY", "GENUINE_ZERO"})
INTEGRITY = frozenset({"NOT-CHECKED", "ABSENT", "FOLDED-INTO-PASS", "CHECKED"})
PASS_STATES = frozenset(
    {"SUCCESS", "PASS", "CONFIRMED", "GREEN", "DELIVERED", "OK", "TRUE"}
)

# Distinctive strings probes and emit can anchor.
ABSENT_NEVER_NOTHING_TO_CHECK = (
    "an absent artifact directory is not evidence of nothing to check"
)
UNRUNNABLE_NOT_SILENT_PASS = (
    "a gate whose enforcement command cannot run emits NOT-CHECKED, not a silent pass"
)
PLANTED_FOLDS_IF_UNLABELLED = (
    "unlabelled item with no probe lands in folded-into-pass"
)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def command_runnable(repo: Path, command: str | None) -> bool:
    if not command or not str(command).strip():
        return False
    parts = str(command).split()
    i = 0
    while i < len(parts) and "=" in parts[i] and not parts[i].startswith("-"):
        i += 1
    if i >= len(parts):
        return False
    tokens = parts[i:]
    exe = tokens[0]
    if exe in {"python3", "python"}:
        for tok in tokens[1:]:
            if tok.endswith(".py") and not tok.startswith("-"):
                cand = Path(tok)
                if not cand.is_absolute():
                    cand = repo / tok
                return cand.is_file()
        return shutil.which(exe) is not None
    if exe.endswith(".py"):
        cand = Path(exe) if Path(exe).is_absolute() else repo / exe
        return cand.is_file()
    return shutil.which(exe) is not None


def claims_pass(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    if doc.get("ok") is True:
        return True
    for key in ("state", "status", "verdict", "result"):
        val = str(doc.get(key) or "").strip().upper()
        if val in PASS_STATES:
            return True
    return False


def labelled_not_checked(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    for key in ("state", "status", "verdict", "result", "integrity_class"):
        val = str(doc.get(key) or "").strip().upper()
        if val in {"NOT-CHECKED", "NOT_CHECKED", "UNCHECKED"}:
            return True
    return False


def _probe_lists(doc: Any) -> list[dict[str, Any]]:
    if not isinstance(doc, dict):
        return []
    rows: list[dict[str, Any]] = []
    for key in ("probe", "source_probe", "verifier_probe"):
        rec = doc.get(key)
        if isinstance(rec, dict) and rec:
            rows.append(rec)
    for key in ("named_probes", "probes", "tests"):
        named = doc.get(key)
        if isinstance(named, list):
            rows.extend(x for x in named if isinstance(x, dict))
    return rows


def probe_record(doc: Any) -> dict[str, Any] | None:
    rows = _probe_lists(doc)
    return rows[0] if rows else None


def has_declared_probe(doc: Any) -> bool:
    """A named command or probe object means this is not an item with no probe."""
    if probe_ran(probe_record(doc)):
        return True
    for rec in _probe_lists(doc):
        cmd = rec.get("command") or rec.get("id")
        if cmd:
            return True
    return False


def probe_ran(rec: dict[str, Any] | None) -> bool:
    if not isinstance(rec, dict):
        return False
    if rec.get("ran") is True:
        return True
    if rec.get("probe_ran") is True:
        return True
    if isinstance(rec.get("exit_code"), int):
        return True
    if rec.get("output") or rec.get("stdout") or rec.get("raw_output"):
        return True
    return False


def finding_count_of(doc: Any, rec: dict[str, Any] | None) -> int | None:
    if isinstance(doc, dict):
        for key in ("finding_count", "findings_count"):
            if isinstance(doc.get(key), int):
                return int(doc[key])
        findings = doc.get("findings")
        if isinstance(findings, list):
            return len(findings)
    if isinstance(rec, dict) and isinstance(rec.get("finding_count"), int):
        return int(rec["finding_count"])
    return None


def distinguish(
    three: str,
    *,
    subject_exists: bool,
    is_empty_container: bool,
    ran: bool,
    findings: int | None,
) -> str:
    if three == "ABSENT":
        return (
            f"{ABSENT_NEVER_NOTHING_TO_CHECK}. "
            "why_not_empty: path does not exist, so there is no container to be empty. "
            "why_not_genuine_zero: no probe ran and finding_count is null, not 0."
        )
    if three == "EMPTY":
        return (
            "empty result set is not an absent path and is not a genuine zero. "
            f"why_not_absent: subject_exists={subject_exists}. "
            "why_not_genuine_zero: probe_ran is false or finding_count is null; "
            "an empty container without a completed probe is EMPTY, not 0 findings."
        )
    return (
        "genuine zero requires a completed probe with finding_count=0. "
        f"why_not_absent: subject_exists={subject_exists}. "
        f"why_not_empty: probe_ran={ran} finding_count={findings} "
        f"is_empty_container={is_empty_container}; a counted zero is not an empty unread container."
    )


def shape_for_path(
    path: Path,
    *,
    doc: Any = None,
    rec: dict[str, Any] | None = None,
    ran: bool | None = None,
    findings: int | None = None,
) -> tuple[str, bool, bool]:
    """Return (three_state, subject_exists, is_empty_container)."""
    exists = path.exists()
    if not exists:
        return "ABSENT", False, False
    empty_container = False
    if path.is_dir():
        try:
            children = [p for p in path.iterdir()]
        except OSError:
            children = ["?"]
        empty_container = len(children) == 0
    elif path.is_file() and path.stat().st_size == 0:
        empty_container = True
    elif path.is_file():
        payload = doc if doc is not None else _load_json(path)
        if payload == [] or payload == {}:
            empty_container = True
    ran_flag = probe_ran(rec) if ran is None else ran
    n = finding_count_of(doc, rec) if findings is None else findings
    if ran_flag and n == 0:
        return "GENUINE_ZERO", True, empty_container
    if empty_container:
        return "EMPTY", True, True
    if ran_flag:
        # Completed probe with non-zero findings still has a measured shape;
        # this classifier's three-state axis is about unmeasured vs zero.
        # Non-zero measured items are not GENUINE_ZERO; they are not EMPTY.
        # Treat unread present files without a zero-finding probe as EMPTY
        # only when the container is empty; otherwise ABSENT refers to the
        # missing *probe*, not the subject file. Callers that need the probe
        # shape for a present unprobed file pass rec=None and get ABSENT
        # only when the path is missing. Present + no probe + non-empty
        # content: probe measurement is ABSENT (no probe artifact).
        return "ABSENT", True, False
    # Present non-empty subject, no probe ran: the *measurement* is absent.
    return "ABSENT", True, False


def integrity_for(
    *,
    three: str,
    doc: Any,
    ran: bool,
    command: str | None,
    repo: Path,
    subject_exists: bool,
) -> str:
    declared = has_declared_probe(doc)
    if ran and three == "GENUINE_ZERO":
        return "CHECKED"
    if ran and declared:
        return "CHECKED"
    if labelled_not_checked(doc):
        return "NOT-CHECKED"
    runnable = command_runnable(repo, command) if command else False
    if command and not runnable:
        # Rule B: cannot run => NOT-CHECKED, never a silent pass.
        return "NOT-CHECKED"
    if claims_pass(doc) and not ran and not declared:
        return "FOLDED-INTO-PASS"
    if declared and not ran:
        return "NOT-CHECKED"
    if not subject_exists or three == "ABSENT":
        if not subject_exists:
            return "ABSENT"
        # Present subject, measurement absent, not labelled, not claiming pass.
        return "NOT-CHECKED"
    if three == "EMPTY":
        return "NOT-CHECKED"
    return "NOT-CHECKED"


def item(
    *,
    iid: str,
    kind: str,
    path: str,
    three: str,
    integrity: str,
    evidence: dict[str, Any],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "id": iid,
        "kind": kind,
        "path": path,
        "three_state": three,
        "integrity_class": integrity,
        "evidence": evidence,
    }
    if extra:
        row.update(extra)
    return row


def evidence_blob(
    *,
    three: str,
    subject_exists: bool,
    empty_container: bool,
    ran: bool,
    findings: int | None,
    command: str | None,
    runnable: bool | None,
    claimed: bool,
    path: str,
) -> dict[str, Any]:
    return {
        "subject_exists": subject_exists,
        "probe_ran": ran,
        "finding_count": findings,
        "is_empty_container": empty_container,
        "enforcement_command": command,
        "command_runnable": runnable,
        "claimed_pass": claimed,
        "path": path,
        "why_not_the_other_two": distinguish(
            three,
            subject_exists=subject_exists,
            is_empty_container=empty_container,
            ran=ran,
            findings=findings,
        ),
    }


def classify_file_item(
    *,
    iid: str,
    kind: str,
    rel: str,
    repo: Path,
    command: str | None = None,
    force_doc: Any = None,
) -> dict[str, Any]:
    path = repo / rel if not Path(rel).is_absolute() else Path(rel)
    # Fixture paths live under the probe dir; accept repo-relative OR absolute.
    if not path.exists() and rel.startswith("command-center/p2-wave/probes/"):
        path = repo / rel
    doc = force_doc
    if doc is None and path.is_file() and path.stat().st_size > 0:
        doc = _load_json(path)
    rec = probe_record(doc) if isinstance(doc, dict) else None
    cmd = command
    if cmd is None and isinstance(doc, dict):
        cmd = (
            doc.get("enforcement_command")
            or doc.get("command")
            or (rec or {}).get("command")
        )
        if isinstance(cmd, str) is False:
            cmd = None
    ran = probe_ran(rec)
    findings = finding_count_of(doc, rec)
    three, exists, empty_c = shape_for_path(
        path, doc=doc, rec=rec, ran=ran, findings=findings
    )
    # Unrunnable gate with a present JSON that claims pass: measurement is
    # still not a genuine zero (probe did not run). three_state stays ABSENT
    # (no completed probe) unless the file is an empty container.
    if exists and empty_c and not ran:
        three = "EMPTY"
    elif exists and ran and findings == 0:
        three = "GENUINE_ZERO"
    elif not exists:
        three = "ABSENT"
    elif not ran:
        three = "ABSENT"
    runnable = command_runnable(repo, cmd) if cmd else False
    claimed = claims_pass(doc)
    integ = integrity_for(
        three=three,
        doc=doc,
        ran=ran,
        command=cmd,
        repo=repo,
        subject_exists=exists,
    )
    ev = evidence_blob(
        three=three,
        subject_exists=exists,
        empty_container=empty_c,
        ran=ran,
        findings=findings,
        command=cmd,
        runnable=runnable if cmd else None,
        claimed=claimed,
        path=rel,
    )
    return item(
        iid=iid,
        kind=kind,
        path=rel,
        three=three,
        integrity=integ,
        evidence=ev,
        extra={"enforcement_command": cmd} if cmd else None,
    )


def ensure_fixtures() -> None:
    EMPTY_DIR.mkdir(parents=True, exist_ok=True)
    leftover = [p for p in EMPTY_DIR.iterdir()]
    for p in leftover:
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            shutil.rmtree(p)
    if ABSENT_DIR.exists():
        # Must stay missing. Do not delete a non-empty surprise tree.
        if ABSENT_DIR.is_dir() and not any(ABSENT_DIR.iterdir()):
            ABSENT_DIR.rmdir()
    EMPTY_ARRAY.parent.mkdir(parents=True, exist_ok=True)
    if not EMPTY_ARRAY.is_file():
        EMPTY_ARRAY.write_text("[]\n", encoding="utf-8")
    PLANTED.parent.mkdir(parents=True, exist_ok=True)
    LABELLED.parent.mkdir(parents=True, exist_ok=True)
    UNRUNNABLE.parent.mkdir(parents=True, exist_ok=True)
    GENUINE_SUBJECTS.mkdir(parents=True, exist_ok=True)


def run_genuine_zero(repo: Path) -> dict[str, Any]:
    p = subprocess.run(
        [sys.executable, "-B", str(GENUINE_PROBE)],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=60,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    payload = None
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{") and "finding_count" in line:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                payload = None
            if payload:
                break
    if payload is None and GENUINE_RECEIPT.is_file():
        payload = _load_json(GENUINE_RECEIPT)
    if not isinstance(payload, dict):
        payload = {
            "probe_ran": False,
            "finding_count": None,
            "exit_code": p.returncode,
            "output_tail": text[-500:],
        }
    payload.setdefault("probe", {})
    if isinstance(payload["probe"], dict):
        payload["probe"]["ran"] = p.returncode == 0
        payload["probe"]["exit_code"] = p.returncode
        payload["probe"]["command"] = (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
            "command-center/p2-wave/probes/CNF-0120/genuine_zero_probe.py"
        )
    payload["exit_code"] = p.returncode
    return payload


def catalog_confirmation_paths(repo: Path) -> list[dict[str, str]]:
    data = _load_json(CATALOG)
    rows: list[dict[str, str]] = []
    if not isinstance(data, dict):
        return rows
    for u in data.get("work_units") or []:
        if not isinstance(u, dict):
            continue
        uid = str(u.get("id") or "")
        out = str(u.get("output_path") or "").replace("\\", "/")
        if not out.startswith("command-center/confirmation/"):
            continue
        if out == SELF_OUT:
            continue
        rows.append({"id": uid or out, "path": out})
    rows.sort(key=lambda r: r["id"])
    return rows


def fixture_items(repo: Path) -> list[dict[str, Any]]:
    ensure_fixtures()
    gz = run_genuine_zero(repo)
    if GENUINE_RECEIPT.is_file():
        # classify_file_item will read receipt; keep gz as force if needed
        pass
    rel_absent = str(ABSENT_DIR.relative_to(repo)).replace("\\", "/")
    rel_empty_dir = str(EMPTY_DIR.relative_to(repo)).replace("\\", "/")
    rel_empty_arr = str(EMPTY_ARRAY.relative_to(repo)).replace("\\", "/")
    rel_planted = str(PLANTED.relative_to(repo)).replace("\\", "/")
    rel_labelled = str(LABELLED.relative_to(repo)).replace("\\", "/")
    rel_gate = str(UNRUNNABLE.relative_to(repo)).replace("\\", "/")
    rel_gz = str(GENUINE_RECEIPT.relative_to(repo)).replace("\\", "/")

    items = [
        classify_file_item(
            iid="FIXTURE-ABSENT-DIR",
            kind="fixture",
            rel=rel_absent,
            repo=repo,
        ),
        classify_file_item(
            iid="FIXTURE-EMPTY-DIR",
            kind="fixture",
            rel=rel_empty_dir,
            repo=repo,
        ),
        classify_file_item(
            iid="FIXTURE-EMPTY-ARRAY",
            kind="fixture",
            rel=rel_empty_arr,
            repo=repo,
        ),
        classify_file_item(
            iid="FIXTURE-PLANTED-UNLABELLED",
            kind="fixture",
            rel=rel_planted,
            repo=repo,
        ),
        classify_file_item(
            iid="FIXTURE-LABELLED-NOT-CHECKED",
            kind="fixture",
            rel=rel_labelled,
            repo=repo,
        ),
        classify_file_item(
            iid="FIXTURE-UNRUNNABLE-GATE",
            kind="fixture",
            rel=rel_gate,
            repo=repo,
            command=UNRUNNABLE_BIN,
        ),
        classify_file_item(
            iid="FIXTURE-GENUINE-ZERO",
            kind="fixture",
            rel=rel_gz,
            repo=repo,
            force_doc=gz if isinstance(gz, dict) else None,
        ),
    ]
    return items


def live_items(repo: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rec in catalog_confirmation_paths(repo):
        rows.append(
            classify_file_item(
                iid=rec["id"],
                kind="confirmation",
                rel=rec["path"],
                repo=repo,
            )
        )
    rows.append(
        classify_file_item(
            iid="CLAIM-INVENTORY",
            kind="claim-inventory",
            rel="command-center/CLAIM-REGISTRY.json",
            repo=repo,
        )
    )
    rows.append(
        classify_file_item(
            iid="GATE-READY-UNITS-OUTPUT",
            kind="gate",
            rel="command-center/READY-UNITS.json",
            repo=repo,
            command="python3 command-center/ready_units.py",
        )
    )
    rows.append(
        classify_file_item(
            iid="GATE-CLAIM-VERIFY",
            kind="gate",
            rel=".agents/skills/claim-verify-gate/scripts/claim_gate.py",
            repo=repo,
            command="python3 .agents/skills/claim-verify-gate/scripts/claim_gate.py",
        )
    )
    leftover = "command-center/p2-wave/P2-CLOUD-LEFTOVER_2026-08-24.json"
    leftover_doc = _load_json(repo / leftover)
    # Inventory file exists and records claimed-green counts, but its own
    # prose refuses G-1. Treat as NOT-CHECKED rather than a pass only if it
    # does not set ok=true / state=SUCCESS. classify_file_item reads the file.
    rows.append(
        classify_file_item(
            iid="GATE-P2-CLOUD-LEFTOVER",
            kind="gate",
            rel=leftover,
            repo=repo,
        )
    )
    _ = leftover_doc
    return rows


def by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(i["id"]): i for i in items}


def controls(items: list[dict[str, Any]]) -> dict[str, Any]:
    idx = by_id(items)
    absent = idx.get("FIXTURE-ABSENT-DIR") or {}
    empty_dir = idx.get("FIXTURE-EMPTY-DIR") or {}
    empty_arr = idx.get("FIXTURE-EMPTY-ARRAY") or {}
    planted = idx.get("FIXTURE-PLANTED-UNLABELLED") or {}
    labelled = idx.get("FIXTURE-LABELLED-NOT-CHECKED") or {}
    gate = idx.get("FIXTURE-UNRUNNABLE-GATE") or {}
    zero = idx.get("FIXTURE-GENUINE-ZERO") or {}

    absent_ok = (
        absent.get("three_state") == "ABSENT"
        and absent.get("integrity_class") == "ABSENT"
        and absent.get("three_state") != "GENUINE_ZERO"
        and absent.get("three_state") != "EMPTY"
    )
    empty_ok = (
        empty_dir.get("three_state") == "EMPTY"
        and empty_arr.get("three_state") == "EMPTY"
        and empty_dir.get("three_state") != "ABSENT"
        and empty_dir.get("three_state") != "GENUINE_ZERO"
    )
    zero_ok = (
        zero.get("three_state") == "GENUINE_ZERO"
        and zero.get("integrity_class") == "CHECKED"
        and zero.get("evidence", {}).get("probe_ran") is True
        and zero.get("evidence", {}).get("finding_count") == 0
    )
    planted_ok = planted.get("integrity_class") == "FOLDED-INTO-PASS"
    labelled_ok = labelled.get("integrity_class") == "NOT-CHECKED"
    gate_ok = (
        gate.get("integrity_class") == "NOT-CHECKED"
        and gate.get("integrity_class") != "FOLDED-INTO-PASS"
        and gate.get("evidence", {}).get("command_runnable") is False
        and gate.get("evidence", {}).get("claimed_pass") is True
    )
    distinct = (
        {absent.get("three_state"), empty_dir.get("three_state"), zero.get("three_state")}
        == {"ABSENT", "EMPTY", "GENUINE_ZERO"}
    )
    return {
        "absent_dir_not_nothing_to_check": bool(absent_ok),
        "empty_not_absent_or_zero": bool(empty_ok),
        "genuine_zero_distinct": bool(zero_ok),
        "unrunnable_gate_not_silent_pass": bool(gate_ok),
        "planted_unlabelled_caught": bool(planted_ok),
        "labelled_not_checked_not_folded": bool(labelled_ok),
        "three_states_unmerged": bool(distinct),
        "all_passed": all(
            [
                absent_ok,
                empty_ok,
                zero_ok,
                planted_ok,
                labelled_ok,
                gate_ok,
                distinct,
            ]
        ),
        "rule_a": ABSENT_NEVER_NOTHING_TO_CHECK,
        "rule_b": UNRUNNABLE_NOT_SILENT_PASS,
        "rule_c": PLANTED_FOLDS_IF_UNLABELLED,
    }


def summary(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "not_checked": 0,
        "absent": 0,
        "folded_into_pass": 0,
        "checked": 0,
        "genuine_zero": 0,
        "empty": 0,
        "three_absent": 0,
        "item_count": len(items),
    }
    for it in items:
        integ = it.get("integrity_class")
        if integ == "NOT-CHECKED":
            counts["not_checked"] += 1
        elif integ == "ABSENT":
            counts["absent"] += 1
        elif integ == "FOLDED-INTO-PASS":
            counts["folded_into_pass"] += 1
        elif integ == "CHECKED":
            counts["checked"] += 1
        three = it.get("three_state")
        if three == "GENUINE_ZERO":
            counts["genuine_zero"] += 1
        elif three == "EMPTY":
            counts["empty"] += 1
        elif three == "ABSENT":
            counts["three_absent"] += 1
    return counts


def run_audit(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    ensure_fixtures()
    items = fixture_items(repo) + live_items(repo)
    # Stable order: fixtures first (named), then live by id.
    ctrl = controls(items)
    return {
        "items": items,
        "summary": summary(items),
        "controls": ctrl,
        "index": by_id(items),
    }


def naive_absent_as_zero(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mutant: missing paths reported as genuine zero / nothing-to-check."""
    out = []
    for it in items:
        row = dict(it)
        if row.get("three_state") == "ABSENT":
            row["three_state"] = "GENUINE_ZERO"
            row["integrity_class"] = "CHECKED"
            ev = dict(row.get("evidence") or {})
            ev["finding_count"] = 0
            ev["probe_ran"] = True
            ev["why_not_the_other_two"] = "mutant: absent directory counted as 0"
            row["evidence"] = ev
        out.append(row)
    return out


def naive_unrunnable_as_pass(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mutant: ok=true on an unrunnable gate kept as a pass."""
    out = []
    for it in items:
        row = dict(it)
        if row.get("id") == "FIXTURE-UNRUNNABLE-GATE":
            row["integrity_class"] = "FOLDED-INTO-PASS"
        out.append(row)
    return out


def main() -> int:
    audit = run_audit(REPO)
    ctrl = audit["controls"]
    sm = audit["summary"]
    print(
        json.dumps(
            {
                "item_count": sm["item_count"],
                "summary": sm,
                "controls": {
                    k: v
                    for k, v in ctrl.items()
                    if not str(k).startswith("rule_")
                },
            },
            sort_keys=True,
        )
    )
    if not ctrl.get("all_passed"):
        print("FAILED:CNF-0120-classify detector-control")
        return 1
    print("SUCCESS:CNF-0120-classify")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
