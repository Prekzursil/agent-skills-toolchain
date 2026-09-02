"""Independent mechanical judges. Isolated read set: rubric + one dossier."""
from __future__ import annotations

from typing import Any

from fixtures import DIMENSIONS

DIM_IDS = [d["id"] for d in DIMENSIONS]


def _evidence(dossier: dict[str, Any]) -> list[dict]:
    rows: list[dict] = []
    ev = dossier.get("evidence")
    if isinstance(ev, list):
        rows.extend(x for x in ev if isinstance(x, dict))
    design = dossier.get("design")
    if isinstance(design, dict) and isinstance(design.get("evidence"), list):
        rows.extend(x for x in design["evidence"] if isinstance(x, dict))
    return rows


def _verdicts(dossier: dict[str, Any]) -> list[str]:
    return [str(r.get("verdict") or "") for r in _evidence(dossier)]


def _file_n(dossier: dict[str, Any]) -> int:
    design = dossier.get("design") if isinstance(dossier.get("design"), dict) else {}
    if isinstance(design, dict):
        for key in ("file_set_count", "file_set_count"):
            n = design.get(key)
            if isinstance(n, int):
                return n
        fs = design.get("file_set")
        if isinstance(fs, list):
            return len(fs)
    fs = dossier.get("file_set")
    if isinstance(fs, list):
        return len(fs)
    return 0


def _stopped(dossier: dict[str, Any]) -> bool:
    design = dossier.get("design") if isinstance(dossier.get("design"), dict) else {}
    expr = {}
    if isinstance(design, dict):
        expr = design.get("expressibility") or design.get("expressibility") or {}
    if not expr:
        expr = dossier.get("expressibility") or dossier.get("expressibility") or {}
    if isinstance(expr, dict):
        return bool(
            expr.get("stopped_at_first_inexpressible")
            or expr.get("stopped_at_first_inexpressible")
        )
    return False


def _dual(dossier: dict[str, Any]) -> bool:
    design = dossier.get("design") if isinstance(dossier.get("design"), dict) else {}
    prec = design.get("precedence") if isinstance(design, dict) else {}
    if isinstance(prec, dict):
        return bool(prec.get("dual_plane_risk") or prec.get("dual_plane_risk"))
    return False


def _has(dossier: dict[str, Any], key: str) -> bool:
    return key in dossier and dossier[key] not in (None, [], {})


def _clamp(n: int) -> int:
    return max(0, min(5, int(n)))


def _cite(dossier: dict[str, Any], preferred: list[str]) -> str:
    for key in preferred:
        head = key.split(".", 1)[0]
        if head in dossier:
            return key
    if "design" in dossier:
        return "design"
    return next(iter(dossier.keys()))


def _row(score: int | None, citation: str, missing: str | None = None) -> dict[str, Any]:
    if missing:
        return {
            "score": None,
            "abstention": True,
            "missing_evidence": missing,
            "citation": citation,
        }
    return {
        "score": _clamp(int(score or 0)),
        "abstention": False,
        "missing_evidence": None,
        "citation": citation,
    }


def score_ja(dossier: dict[str, Any]) -> dict[str, Any]:
    """Methodologist: evidence density; abstain when a required section is absent."""
    ev = _evidence(dossier)
    v = _verdicts(dossier)
    dims: dict[str, Any] = {}
    if not _has(dossier, "design") and "file_set" not in dossier:
        dims["correctness"] = _row(None, "design", "design section absent from dossier")
    else:
        score = 3
        if _stopped(dossier):
            score += 1
        if any(x == "REFUTED" for x in v):
            score += 1
        dims["correctness"] = _row(score, _cite(dossier, ["design"]))

    dims["singularity"] = _row(
        2 if _dual(dossier) else 4,
        _cite(dossier, ["design.precedence", "design"]),
    )

    if not ev:
        dims["evidence_quality"] = _row(
            None, "evidence", "evidence section empty or absent from dossier"
        )
    else:
        dims["evidence_quality"] = _row(min(5, len(ev)), _cite(dossier, ["evidence", "design"]))

    if not _has(dossier, "failure_modes"):
        dims["operational_safety"] = _row(
            None, "failure_modes", "failure_modes section absent from dossier"
        )
    else:
        dims["operational_safety"] = _row(4, "failure_modes")

    n = _file_n(dossier)
    dims["resource_efficiency"] = _row(
        4 if n <= 6 else (3 if n <= 10 else 1),
        _cite(dossier, ["design.file_set", "design"]),
    )
    return dims


def score_jb(dossier: dict[str, Any]) -> dict[str, Any]:
    """Critic: all-confirmed is suspicious; REFUTED is honesty."""
    v = _verdicts(dossier)
    nref = sum(1 for x in v if x == "REFUTED")
    nconf = sum(1 for x in v if x == "CONFIRMED")
    if not v:
        corr = 1
        eq_row = _row(None, "evidence", "evidence section empty or absent from dossier")
    else:
        corr = 4 if nref else (2 if nconf == len(v) else 3)
        eq_row = _row(5 if nref >= 2 else (4 if nref else 2), _cite(dossier, ["evidence", "design"]))
    has_tests = _has(dossier, "tests") or (
        isinstance(dossier.get("design"), dict) and _has(dossier["design"], "tests")
    )
    return {
        "correctness": _row(corr if v else 1, _cite(dossier, ["design"])),
        "singularity": _row(5 if _dual(dossier) else 2, _cite(dossier, ["design.precedence", "design"])),
        "evidence_quality": eq_row,
        "operational_safety": _row(
            5 if has_tests else 1,
            _cite(dossier, ["tests", "failure_modes", "design"]),
        ),
        "resource_efficiency": _row(
            4 if _file_n(dossier) <= 6 else 2,
            _cite(dossier, ["design.file_set", "design"]),
        ),
    }


def score_jc(dossier: dict[str, Any]) -> dict[str, Any]:
    """Operator: tests, rollback, machinery cost."""
    n = _file_n(dossier)
    has_mig = _has(dossier, "migration")
    has_tests = _has(dossier, "tests")
    has_fm = _has(dossier, "failure_modes")
    corr = 3
    if _stopped(dossier):
        corr += 1
    if has_tests:
        corr += 1
    if has_fm or has_mig:
        op = _row(
            2 + (2 if has_fm else 0) + (1 if has_mig else 0),
            _cite(dossier, ["migration", "failure_modes", "design"]),
        )
    else:
        op = _row(None, "migration", "migration and failure_modes absent from dossier")
    return {
        "correctness": _row(corr, _cite(dossier, ["design", "samples"])),
        "singularity": _row(1 if _dual(dossier) else 3, _cite(dossier, ["design.precedence", "design"])),
        "evidence_quality": _row(
            3 if _evidence(dossier) else 1,
            _cite(dossier, ["evidence", "samples", "design"]),
        ),
        "operational_safety": op,
        "resource_efficiency": _row(
            5 if n <= 5 else (3 if n <= 8 else 1),
            _cite(dossier, ["design.file_set", "design"]),
        ),
    }


SCORERS = {
    "J-A": score_ja,
    "J-B": score_jb,
    "J-C": score_jc,
}


def score_entry(judge_id: str, dossier: dict[str, Any]) -> dict[str, Any]:
    fn = SCORERS[judge_id]
    dims = fn(dossier)
    missing = [k for k in DIM_IDS if k not in dims]
    if missing:
        raise RuntimeError(f"{judge_id} missing dimensions {missing}")
    return dims


def apply_nameless_abstention_rule(dims: dict[str, Any]) -> dict[str, Any]:
    """Abstention without named missing evidence is recorded as zero."""
    out = {}
    for key, row in dims.items():
        r = dict(row)
        if r.get("abstention") and not (r.get("missing_evidence") or "").strip():
            r["score"] = 0
            r["abstention"] = False
            r["recorded_as_zero"] = True
            r["reason"] = "abstention without named missing evidence"
        elif r.get("abstention") and r.get("missing_evidence"):
            r["score"] = None
            r["recorded_as_zero"] = False
        else:
            r["recorded_as_zero"] = False
        out[key] = r
    return out


def forced_dissent(judge_id: str, dims: dict[str, Any]) -> dict[str, Any]:
    """Blind re-eval: each judge names a different weakness (not a copy of peers)."""
    out = {k: dict(v) for k, v in dims.items()}
    if judge_id == "J-A":
        target = "operational_safety"
        note = "forced-dissent: residual operational risk not independently tested"
    elif judge_id == "J-B":
        target = "singularity"
        note = "forced-dissent: possible second control plane under growth"
    else:
        target = "resource_efficiency"
        note = "forced-dissent: machinery cost under-weighted on first pass"
    row = dict(out[target])
    if row.get("score") is not None:
        row["first_pass_score"] = row.get("score")
        row["score"] = _clamp(int(row["score"]) - 1)
    row["forced_dissent"] = True
    row["dissent_note"] = note
    out[target] = row
    return out


def dimension_signature(dims: dict[str, Any]) -> tuple:
    sig = []
    for did in DIM_IDS:
        row = dims[did]
        if row.get("abstention"):
            sig.append(("A", row.get("missing_evidence")))
        else:
            sig.append(("S", row.get("score")))
    return tuple(sig)


def digest_only_dimensions(dossier: dict[str, Any]) -> dict[str, Any]:
    """Negative control: every dimension cites only digest."""
    if "digest" not in dossier:
        raise KeyError("digest")
    return {did: _row(3, "digest") for did in DIM_IDS}


score_entry = score_entry
apply_nameless_abstention_rule = apply_nameless_abstention_rule
forced_dissent = forced_dissent
dimension_signature = dimension_signature
