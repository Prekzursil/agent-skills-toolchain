"""Discrepancy triage router (CNF-0013 / spec 11039).

A recorded discrepancy cannot reach status=closed without exactly one
disposition from the five-way set. implementation-defect and
confirmation-defect each open a severity-tagged defect. accepted-residual
requires a named settling experiment. The original implementer may contest
in writing and cannot close; the confirmation author cannot close; closure
requires a second confirmer who authored neither.

naive_close() is the pre-gate control that demonstrates the hole: it mutates
JSON to status=closed and leaves disposition null. persist() refuses that
state. close() refuses a null or blank disposition.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

DISPOSITIONS: tuple[str, ...] = (
    "implementation-defect",
    "confirmation-defect",
    "specification-ambiguity",
    "environment-difference",
    "accepted-residual",
)

NULL_DISPOSITION_REFUSAL = "REFUSED:null-disposition"
EMPTY_DISPOSITION_REFUSAL = "REFUSED:empty-disposition"
UNKNOWN_DISPOSITION_REFUSAL = "REFUSED:unknown-disposition"
SETTLING_EXPERIMENT_REFUSAL = "REFUSED:missing-settling-experiment"
IMPLEMENTER_CLOSE_REFUSAL = "REFUSED:implementer-cannot-close"
CONFIRMATION_AUTHOR_CLOSE_REFUSAL = "REFUSED:confirmation-author-cannot-close"
CLOSER_NOT_SECOND_REFUSAL = "REFUSED:closer-not-second-confirmer"
CLOSER_NOT_DISTINCT_REFUSAL = "REFUSED:closer-not-distinct"
SILENT_CLOSE_REFUSAL = "REFUSED:silent-close"
MISSING_ID_REFUSAL = "REFUSED:missing-id"

# File:line evidence: this snippet is the armed null-disposition gate.
GATE_SNIPPET = "raise CloseRefused(NULL_DISPOSITION_REFUSAL)"

ROLE_IMPLEMENTER = "original-implementer"
ROLE_CONFIRMATION_AUTHOR = "confirmation-author"
ROLE_SECOND_CONFIRMER = "second-confirmer"

DEFECT_DISPOSITIONS = frozenset(
    {"implementation-defect", "confirmation-defect"}
)
SEVERITY_BY_KIND = {
    "implementation-defect": "P1",
    "confirmation-defect": "P1",
}

SOURCE_PROBE_ID = "probe1-null-disposition"
VERIFIER_PROBE_ID = "probe2-full-close"
SOURCE_PROBE_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0013/probe1_null_disposition.py"
)
VERIFIER_PROBE_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0013/probe2_full_close.py"
)


class CloseRefused(Exception):
    """A close or persist was refused. ``code`` is the machine token."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(detail or code)


def _disposition_present(disposition: Any) -> bool:
    if disposition is None:
        return False
    if isinstance(disposition, str) and disposition.strip() == "":
        return False
    return True


def _normalize_disposition(disposition: Any) -> str | None:
    if not _disposition_present(disposition):
        return None
    return str(disposition).strip()


def probe_fingerprint(probe_id: str, command: str) -> str:
    payload = json.dumps(
        {"probe_id": probe_id, "command": command, "method": "command"},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def default_census_roots(repo: Path) -> list[Path]:
    return [
        repo / "command-center" / "confirmation",
        repo / "command-center" / "receipts",
        repo / "command-center" / "discrepancies",
        repo / "command-center" / "audit",
    ]


def is_closed_without_disposition(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    status = str(obj.get("status") or "").strip().lower()
    if status != "closed":
        return False
    return not _disposition_present(obj.get("disposition"))


def census_closed_without_disposition(roots: list[Path]) -> list[dict[str, Any]]:
    """Walk JSON files under roots; return closed records with a null disposition."""
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        paths = [root] if root.is_file() else sorted(root.rglob("*.json"))
        for path in paths:
            if not path.is_file():
                continue
            rel = str(path)
            if rel in seen:
                continue
            seen.add(rel)
            try:
                raw = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if not raw.strip():
                continue
            try:
                doc = json.loads(raw)
            except json.JSONDecodeError:
                continue
            candidates: list[Any]
            if isinstance(doc, list):
                candidates = doc
            elif isinstance(doc, dict):
                candidates = [doc]
                inner = doc.get("records") or doc.get("discrepancies")
                if isinstance(inner, list):
                    candidates.extend(inner)
            else:
                continue
            for item in candidates:
                if is_closed_without_disposition(item):
                    rec_id = ""
                    if isinstance(item, dict):
                        rec_id = str(
                            item.get("id")
                            or item.get("discrepancy_id")
                            or item.get("unit_id")
                            or ""
                        )
                    found.append(
                        {
                            "path": rel,
                            "id": rec_id,
                            "status": "closed",
                            "disposition": None
                            if isinstance(item, dict)
                            else None,
                        }
                    )
    return found


def naive_close(record: dict[str, Any]) -> dict[str, Any]:
    """Pre-gate JSON mutation: status=closed, disposition left null.

    This is the hole the gate closes. It does not raise.
    """
    out = dict(record)
    out["status"] = "closed"
    return out


def _require_closer(record: dict[str, Any], actor_id: str, actor_role: str) -> None:
    if actor_role == ROLE_IMPLEMENTER:
        raise CloseRefused(IMPLEMENTER_CLOSE_REFUSAL)
    if actor_role == ROLE_CONFIRMATION_AUTHOR:
        raise CloseRefused(CONFIRMATION_AUTHOR_CLOSE_REFUSAL)
    if actor_role != ROLE_SECOND_CONFIRMER:
        raise CloseRefused(CLOSER_NOT_SECOND_REFUSAL)
    implementer = str((record.get("implementer") or {}).get("id") or "")
    confirmer = str((record.get("confirmer") or {}).get("id") or "")
    if actor_id and actor_id in {implementer, confirmer}:
        raise CloseRefused(CLOSER_NOT_DISTINCT_REFUSAL)


def _open_defect(record: dict[str, Any], disposition: str) -> dict[str, Any]:
    rec_id = str(record.get("id") or "DSC-unknown")
    kind = disposition
    return {
        "id": f"DEF-{rec_id}",
        "severity": SEVERITY_BY_KIND.get(kind, "P2"),
        "kind": kind,
        "status": "open",
        "title": (
            f"Discrepancy {rec_id} routed to {kind}; a severity-tagged defect "
            "is required for this disposition."
        ),
    }


def close(
    record: dict[str, Any],
    *,
    actor_id: str,
    actor_role: str,
    disposition: Any = None,
    settling_experiment: str | None = None,
) -> dict[str, Any]:
    """Armed close. Refuses a null/blank disposition and forbidden actors."""
    rec_id = str(record.get("id") or "").strip()
    if not rec_id:
        raise CloseRefused(MISSING_ID_REFUSAL)

    if disposition is None and "disposition" not in record:
        raise CloseRefused(NULL_DISPOSITION_REFUSAL)
    if disposition is None:
        disposition = record.get("disposition")
    if disposition is None:
        raise CloseRefused(NULL_DISPOSITION_REFUSAL)
    if isinstance(disposition, str) and disposition.strip() == "":
        raise CloseRefused(EMPTY_DISPOSITION_REFUSAL)

    disp = _normalize_disposition(disposition)
    if disp is None:
        raise CloseRefused(NULL_DISPOSITION_REFUSAL)
    if disp not in DISPOSITIONS:
        raise CloseRefused(f"{UNKNOWN_DISPOSITION_REFUSAL}:{disp}")

    experiment = settling_experiment
    if experiment is None:
        experiment = record.get("settling_experiment")
    if disp == "accepted-residual" and not str(experiment or "").strip():
        raise CloseRefused(SETTLING_EXPERIMENT_REFUSAL)

    _require_closer(record, actor_id, actor_role)

    out = dict(record)
    out["status"] = "closed"
    out["disposition"] = disp
    if experiment:
        out["settling_experiment"] = str(experiment).strip()
    out["closer"] = {"id": actor_id, "role": actor_role}
    if disp in DEFECT_DISPOSITIONS:
        out["defect"] = _open_defect(out, disp)
    return out


def contest(
    record: dict[str, Any],
    *,
    actor_id: str,
    actor_role: str,
    text: str,
) -> dict[str, Any]:
    """Implementer may contest in writing. Contest does not close."""
    if actor_role != ROLE_IMPLEMENTER:
        raise CloseRefused("REFUSED:contest-not-implementer")
    out = dict(record)
    notes = list(out.get("contests") or [])
    notes.append({"actor_id": actor_id, "role": actor_role, "text": text})
    out["contests"] = notes
    if out.get("status") == "closed" and not _disposition_present(out.get("disposition")):
        raise CloseRefused(SILENT_CLOSE_REFUSAL)
    # Contest never flips status to closed.
    if str(out.get("status") or "") == "closed" and actor_role == ROLE_IMPLEMENTER:
        out["status"] = str(record.get("status") or "open")
    return out


def persist(path: Path, record: dict[str, Any]) -> None:
    """Write a record. A closed record with a null disposition is refused."""
    if str(record.get("status") or "").strip().lower() == "closed":
        if not _disposition_present(record.get("disposition")):
            raise CloseRefused(SILENT_CLOSE_REFUSAL)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _caught(code_attr: str, fn) -> tuple[bool, str]:
    try:
        fn()
    except CloseRefused as exc:
        return True, exc.code
    return False, ""


def _base_record(rec_id: str) -> dict[str, Any]:
    return {
        "id": rec_id,
        "status": "open",
        "disposition": None,
        "implementer": {"id": "cnf-0013-implementer", "role": ROLE_IMPLEMENTER},
        "confirmer": {"id": "cnf-0013-confirmer", "role": ROLE_CONFIRMATION_AUTHOR},
    }


def run_gate_controls(ledger: Path) -> dict[str, Any]:
    """Same-run battery: silent close is the hole; armed close refuses it
    and a fully dispositioned close succeeds.
    """
    ledger.mkdir(parents=True, exist_ok=True)
    second = {
        "id": "cnf-0013-second-confirmer",
        "role": ROLE_SECOND_CONFIRMER,
    }

    planted = _base_record("DSC-CNF-0013-silent-plant")
    naive = naive_close(planted)
    naive_close_silent = (
        naive.get("status") == "closed"
        and not _disposition_present(naive.get("disposition"))
    )
    persist_silent_close_refused, persist_code = _caught(
        SILENT_CLOSE_REFUSAL,
        lambda: persist(ledger / "silent-plant.json", naive),
    )

    null_refused, null_code = _caught(
        NULL_DISPOSITION_REFUSAL,
        lambda: close(
            _base_record("DSC-CNF-0013-null"),
            actor_id=second["id"],
            actor_role=second["role"],
            disposition=None,
        ),
    )
    # close() with an explicit None still hits the null gate.
    if not null_refused:
        try:
            close(
                _base_record("DSC-CNF-0013-null"),
                actor_id=second["id"],
                actor_role=second["role"],
            )
            null_refused, null_code = False, ""
        except CloseRefused as exc:
            null_refused, null_code = True, exc.code

    empty_refused, empty_code = _caught(
        EMPTY_DISPOSITION_REFUSAL,
        lambda: close(
            _base_record("DSC-CNF-0013-empty"),
            actor_id=second["id"],
            actor_role=second["role"],
            disposition="",
        ),
    )

    settling_refused, settling_code = _caught(
        SETTLING_EXPERIMENT_REFUSAL,
        lambda: close(
            _base_record("DSC-CNF-0013-residual-bare"),
            actor_id=second["id"],
            actor_role=second["role"],
            disposition="accepted-residual",
        ),
    )

    implementer_refused, implementer_code = _caught(
        IMPLEMENTER_CLOSE_REFUSAL,
        lambda: close(
            _base_record("DSC-CNF-0013-impl-actor"),
            actor_id="cnf-0013-implementer",
            actor_role=ROLE_IMPLEMENTER,
            disposition="specification-ambiguity",
        ),
    )

    confirmer_refused, confirmer_code = _caught(
        CONFIRMATION_AUTHOR_CLOSE_REFUSAL,
        lambda: close(
            _base_record("DSC-CNF-0013-cnf-actor"),
            actor_id="cnf-0013-confirmer",
            actor_role=ROLE_CONFIRMATION_AUTHOR,
            disposition="specification-ambiguity",
        ),
    )

    contested = contest(
        _base_record("DSC-CNF-0013-contest"),
        actor_id="cnf-0013-implementer",
        actor_role=ROLE_IMPLEMENTER,
        text="The implementation is correct; the confirmation over-claimed.",
    )
    contest_did_not_close = str(contested.get("status") or "") != "closed"
    persist(ledger / "contest.json", contested)

    closed_ids: list[str] = []

    full = close(
        _base_record("DSC-CNF-0013-fully-dispositioned"),
        actor_id=second["id"],
        actor_role=second["role"],
        disposition="specification-ambiguity",
    )
    persist(ledger / "fully-dispositioned.json", full)
    fully_ok = (
        full.get("status") == "closed"
        and full.get("disposition") == "specification-ambiguity"
        and (full.get("closer") or {}).get("id") == second["id"]
    )
    if fully_ok:
        closed_ids.append(str(full["id"]))

    impl = close(
        _base_record("DSC-CNF-0013-impl-defect"),
        actor_id=second["id"],
        actor_role=second["role"],
        disposition="implementation-defect",
    )
    persist(ledger / "impl-defect.json", impl)
    impl_defect_opened = (
        isinstance(impl.get("defect"), dict)
        and str((impl.get("defect") or {}).get("kind") or "") == "implementation-defect"
        and str((impl.get("defect") or {}).get("severity") or "") in {"P0", "P1", "P2", "P3"}
        and impl.get("status") == "closed"
    )
    if impl.get("status") == "closed":
        closed_ids.append(str(impl["id"]))

    cnf = close(
        _base_record("DSC-CNF-0013-cnf-defect"),
        actor_id=second["id"],
        actor_role=second["role"],
        disposition="confirmation-defect",
    )
    persist(ledger / "cnf-defect.json", cnf)
    cnf_defect_opened = (
        isinstance(cnf.get("defect"), dict)
        and str((cnf.get("defect") or {}).get("kind") or "") == "confirmation-defect"
        and str((cnf.get("defect") or {}).get("severity") or "") in {"P0", "P1", "P2", "P3"}
        and cnf.get("status") == "closed"
    )
    if cnf.get("status") == "closed":
        closed_ids.append(str(cnf["id"]))

    residual = close(
        _base_record("DSC-CNF-0013-accepted-residual"),
        actor_id=second["id"],
        actor_role=second["role"],
        disposition="accepted-residual",
        settling_experiment="CNF-0013-named-settling-experiment: re-run naive_close then persist on a fresh ledger and require REFUSED:silent-close.",
    )
    persist(ledger / "accepted-residual.json", residual)
    residual_ok = (
        residual.get("status") == "closed"
        and residual.get("disposition") == "accepted-residual"
        and bool(str(residual.get("settling_experiment") or "").strip())
    )
    if residual.get("status") == "closed":
        closed_ids.append(str(residual["id"]))

    env = close(
        _base_record("DSC-CNF-0013-env-diff"),
        actor_id=second["id"],
        actor_role=second["role"],
        disposition="environment-difference",
    )
    persist(ledger / "env-diff.json", env)

    after = census_closed_without_disposition([ledger])
    closed_without_after = len(after)

    flags = {
        "naive_close_silent": bool(naive_close_silent),
        "persist_silent_close_refused": bool(persist_silent_close_refused),
        "null_disposition_refused": bool(null_refused)
        and null_code == NULL_DISPOSITION_REFUSAL,
        "empty_disposition_refused": bool(empty_refused),
        "accepted_residual_without_experiment_refused": bool(settling_refused)
        and settling_code == SETTLING_EXPERIMENT_REFUSAL,
        "implementer_close_refused": bool(implementer_refused)
        and implementer_code == IMPLEMENTER_CLOSE_REFUSAL,
        "confirmation_author_close_refused": bool(confirmer_refused)
        and confirmer_code == CONFIRMATION_AUTHOR_CLOSE_REFUSAL,
        "contest_did_not_close": bool(contest_did_not_close),
        "fully_dispositioned_close_succeeded": bool(fully_ok),
        "implementation_defect_opened": bool(impl_defect_opened),
        "confirmation_defect_opened": bool(cnf_defect_opened),
        "accepted_residual_with_experiment_succeeded": bool(residual_ok),
        "closed_without_disposition_after_ledger": closed_without_after,
    }
    passed = all(
        flags[k] is True
        for k in flags
        if k != "closed_without_disposition_after_ledger"
    ) and closed_without_after == 0

    src_fp = probe_fingerprint(SOURCE_PROBE_ID, SOURCE_PROBE_CMD)
    ver_fp = probe_fingerprint(VERIFIER_PROBE_ID, VERIFIER_PROBE_CMD)
    return {
        **flags,
        "pass": passed,
        "null_disposition_code": null_code or NULL_DISPOSITION_REFUSAL,
        "empty_disposition_code": empty_code,
        "persist_code": persist_code,
        "settling_code": settling_code,
        "implementer_code": implementer_code,
        "confirmer_code": confirmer_code,
        "closed_record_ids": closed_ids,
        "source_probe_fingerprint": src_fp,
        "verifier_probe_fingerprint": ver_fp,
        "ledger": str(ledger),
        "dispositions": list(DISPOSITIONS),
        "gate_snippet": GATE_SNIPPET,
    }
