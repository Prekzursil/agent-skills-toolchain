#!/usr/bin/env python3
"""Independent conformance suite for the compatibility-matrix contract.

Does not import the ARC-0095 generator. Accepts both the live document shape
(axes / render / evidence / is_pass / operating_system / claude-code) and
legacy aliases (axes / render / operating_system / claude-code).
"""
from __future__ import annotations

from copy import deepcopy
from itertools import product
from typing import Any

CANON_AXES = (
    "operating_system",
    "client",
    "client_version",
    "shell",
    "package_version",
)

AXIS_ALIAS = {
    "operating_system": "operating_system",
    "operating_system": "operating_system",
    "os": "operating_system",
    "client": "client",
    "client_version": "client_version",
    "client_version": "client_version",
    "shell": "shell",
    "package_version": "package_version",
    "package_version": "package_version",
}

CLIENT_ALIAS = {
    "claude-code": "claude-code",
    "claude-code": "claude-code",
    "codex-cli": "codex-cli",
    "codex-cli": "codex-cli",
    "antigravity": "antigravity",
    "antigravity": "antigravity",
    "agy": "antigravity",
    "mcp-generic": "mcp-generic",
    "mcp-generic": "mcp-generic",
}

PASS_LIKE = frozenset(
    {"SUPPORTED", "PASS", "OK", "GREEN", "RUN", "TRUE", "YES", "CHECKED"}
)
UNPINNED = frozenset({"UNPINNED", "UNDECLARED", "*", ""})
IN_CLIENT = frozenset({"in-client", "in-client", "in_client"})
INSTALLER = frozenset(
    {"installer-exit", "installer-exit", "installer_exit", "installer"}
)

RULES = (
    ("R-blank", "Every declared cartesian cell is present; blank cells are forbidden."),
    (
        "R-supported-evidence",
        "SUPPORTED requires an in-client receipt naming run_id and VERSION.",
    ),
    ("R-untested-not-pass", "NOT-CHECKED / UNTESTED must never read as a pass."),
    ("R-untested-token", "An untested cell must carry the literal UNTESTED token."),
    (
        "R-inferred-distinct",
        "INFERRED is never SUPPORTED and must not read as a pass.",
    ),
    ("R-installer-not-evidence", "An installer exit code is not in-client evidence."),
    ("R-unpinned", "UNPINNED client or package version cannot be SUPPORTED."),
    ("R-partial-green", "Zero untested cells on a one-platform estate is a defect."),
    ("R-run-id-or-untested", "Every cell has a run_id or the literal UNTESTED token."),
)


def _canon_axis_key(key: str) -> str:
    return AXIS_ALIAS.get(str(key), str(key))


def _canon_client(value: str) -> str:
    raw = str(value)
    return CLIENT_ALIAS.get(raw, raw)


def _norm_axes_map(raw: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(raw, dict):
        return out
    for key, val in raw.items():
        canon = _canon_axis_key(key)
        text = "" if val is None else str(val)
        if canon == "client":
            text = _canon_client(text)
        out[canon] = text
    return out


def _axis_lists(raw: Any) -> dict[str, list[str]]:
    src = raw if isinstance(raw, dict) else {}
    if isinstance(src.get("declared"), dict):
        src = src["declared"]
    out: dict[str, list[str]] = {k: [] for k in CANON_AXES}
    for key, val in src.items():
        canon = _canon_axis_key(key)
        if canon not in out or not isinstance(val, list):
            continue
        items = []
        for item in val:
            text = str(item)
            if canon == "client":
                text = _canon_client(text)
            items.append(text)
        out[canon] = items
    return out


def _pick_dict(cell: dict, *keys: str) -> dict:
    for key in keys:
        val = cell.get(key)
        if isinstance(val, dict):
            return val
    return {}


def _render(cell: dict) -> dict:
    return _pick_dict(cell, "render", "render")


def _axes_of(cell: dict) -> dict:
    return _pick_dict(cell, "axes", "axes")


def _status(cell: dict) -> str:
    return str(cell.get("status") or cell.get("status") or "")


def _is_pass(cell: dict) -> bool:
    if cell.get("is_pass") is True or cell.get("is_pass") is True:
        return True
    return _render(cell).get("is_pass") is True


def _untested_token(cell: dict) -> str | None:
    rnd = _render(cell) if "render" in cell or "render" in cell else cell.get("render") or {}
    if not isinstance(rnd, dict):
        rnd = {}
    blob = [
        _status(cell) if "status" in cell else str(cell.get("status") or ""),
        str(rnd.get("token") or ""),
        str(rnd.get("display") or ""),
        str(rnd.get("machine_status") or ""),
    ]
    if cell.get("status"):
        blob.append(str(cell.get("status")))
    aliases = rnd.get("aliases") or cell.get("aliases") or []
    if isinstance(aliases, list):
        blob.extend(str(a) for a in aliases)
    for item in blob:
        if item == "UNTESTED":
            return "UNTESTED"
    return None


def cell_id(axes: dict[str, str]) -> str:
    return "|".join(str(axes.get(k) or "") for k in CANON_AXES)


def _evidence_list(cell: dict) -> list[dict]:
    for key in ("evidence", "evidence"):
        ev = cell.get(key)
        if isinstance(ev, list):
            return [e for e in ev if isinstance(e, dict)]
    rec = cell.get("receipt")
    if isinstance(rec, dict):
        return [rec]
    return []


def _run_id_from(cell: dict, evidence: list[dict]) -> str | None:
    for ev in evidence:
        rid = ev.get("run_id") or ev.get("run-id")
        if rid:
            return str(rid)
    rid = cell.get("run_id")
    return str(rid) if rid else None


def valid_in_client(ev: dict, axes: dict[str, str]) -> tuple[bool, str]:
    kind = str(ev.get("observation_kind") or ev.get("observation_kind") or "")
    if kind in INSTALLER:
        return False, "installer"
    if kind not in IN_CLIENT:
        return False, f"kind:{kind or 'missing'}"
    rid = ev.get("run_id") or ev.get("run-id")
    if not rid:
        return False, "missing-run_id"
    ver = str(
        ev.get("observed_client_version")
        or ev.get("observed_client_version")
        or ev.get("client_version")
        or ev.get("client_version")
        or ""
    )
    intended = axes.get("client_version") or ""
    if intended in UNPINNED or ver in UNPINNED:
        return False, "unpinned"
    if ver and intended and ver != intended:
        return False, "version-mismatch"
    if not ver:
        return False, "missing-version"
    result = str(ev.get("result") or ev.get("result") or "").lower()
    if result not in {"pass", "fail"}:
        return False, "result-not-pass-or-fail"
    return True, result


def extract_matrix(doc: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(doc, dict):
        return {"axes": {}, "cells": [], "program_ran_on": []}
    if isinstance(doc.get("cells"), list) and doc.get("axes") is not None:
        return doc
    gr = doc.get("generator_run")
    if isinstance(gr, dict) and isinstance(gr.get("cells"), list):
        axes = None
        if isinstance(doc.get("axes"), dict):
            axes = doc["axes"].get("declared") or doc["axes"]
        return {
            "axes": axes or gr.get("axes") or {},
            "cells": gr["cells"],
            "untested_cell_count": gr.get("untested_cell_count"),
            "status_counts": gr.get("status_counts") or gr.get("status_counts"),
            "program_ran_on": gr.get("program_ran_on") or gr.get("program_ran_on") or [],
            "blank_cells": gr.get("blank_cells"),
        }
    return doc


def naive_status_present(matrix: dict[str, Any]) -> bool:
    """Weak checker: green iff every *present* cell has a non-empty status.

    Missing declared cells and evidence-free SUPPORTED labels stay invisible,
    so this checker stays green on several planted defects.
    """
    cells = extract_matrix(matrix).get("cells") or []
    if not cells:
        return False
    for cell in cells:
        if not isinstance(cell, dict) or not _status(cell):
            return False
    return True


def evaluate(doc: dict[str, Any]) -> dict[str, Any]:
    matrix = extract_matrix(doc)
    axes = _axis_lists(matrix.get("axes"))
    lists = [axes[k] for k in CANON_AXES]
    declared_ids: set[str] = set()
    if all(lists):
        for combo in product(*lists):
            declared_ids.add(cell_id(dict(zip(CANON_AXES, combo))))

    by_id: dict[str, dict[str, Any]] = {}
    for raw in matrix.get("cells") or []:
        if not isinstance(raw, dict):
            continue
        ax = _norm_axes_map(_axes_of(raw))
        cid = cell_id(ax) if ax else str(raw.get("id") or raw.get("id") or "")
        by_id[cid] = {
            "id": cid,
            "axes": ax,
            "status": _status(raw),
            "render": dict(_render(raw)),
            "is_pass": _is_pass(raw),
            "evidence": _evidence_list(raw),
            "reason": str(raw.get("reason") or raw.get("reason") or ""),
        }

    violations: list[dict[str, str]] = []

    def viol(rule: str, detail: str, cid: str = "") -> None:
        violations.append({"rule_id": rule, "detail": detail, "cell_id": cid})

    if declared_ids:
        missing = sorted(declared_ids - set(by_id))
        empty = [cid for cid, cell in by_id.items() if not str(cell["status"]).strip()]
        if missing or empty:
            viol(
                "R-blank",
                f"missing={len(missing)} empty_status={len(empty)}",
                (missing or empty)[0],
            )

    untested_n = 0
    supported_n = 0
    inferred_n = 0
    asserted: list[str] = []
    installer_as_run: list[str] = []
    coverage_rows: list[dict[str, Any]] = []
    platforms_with_evidence: set[str] = set()

    for cid, cell in by_id.items():
        st = cell["status"]
        rnd = cell["render"]
        ax = cell["axes"]
        token = str(rnd.get("token") or st)
        display = str(rnd.get("display") or "")
        untested = _untested_token({"status": st, "render": rnd})
        in_client_ok = False
        in_client_result = ""
        saw_installer = False
        run_id = None
        for ev in cell["evidence"]:
            ok, why = valid_in_client(ev, ax)
            if why == "installer":
                saw_installer = True
            if ok:
                in_client_ok = True
                in_client_result = why
                run_id = str(ev.get("run_id") or ev.get("run-id") or "") or run_id
                platforms_with_evidence.add(ax.get("operating_system") or "")
        if not run_id:
            run_id = _run_id_from(cell, cell["evidence"])

        if st == "NOT-CHECKED":
            untested_n += 1
        if st == "SUPPORTED":
            supported_n += 1
        if st == "INFERRED":
            inferred_n += 1

        pass_painted = st in PASS_LIKE or token in PASS_LIKE or cell["is_pass"]
        if pass_painted and not (in_client_ok and in_client_result == "pass"):
            asserted.append(cid)

        if st == "SUPPORTED":
            if not (in_client_ok and in_client_result == "pass"):
                viol(
                    "R-supported-evidence",
                    "SUPPORTED without in-client pass receipt",
                    cid,
                )
            ver = ax.get("client_version") or ""
            pkg = ax.get("package_version") or ""
            if ver in UNPINNED or pkg in UNPINNED:
                viol(
                    "R-unpinned",
                    f"UNPINNED version on SUPPORTED ver={ver!r} pkg={pkg!r}",
                    cid,
                )
            if saw_installer:
                viol(
                    "R-installer-not-evidence",
                    "installer-exit used as SUPPORTED evidence",
                    cid,
                )
                installer_as_run.append(cid)

        if st == "NOT-CHECKED":
            if cell["is_pass"] or rnd.get("is_pass") is True:
                viol("R-untested-not-pass", "NOT-CHECKED is_pass true", cid)
            if token in PASS_LIKE or display in PASS_LIKE:
                viol(
                    "R-untested-not-pass",
                    f"untested token/display is pass-like {token}/{display}",
                    cid,
                )
            if untested != "UNTESTED":
                viol(
                    "R-untested-token",
                    "NOT-CHECKED missing literal UNTESTED token",
                    cid,
                )

        if st == "INFERRED":
            if token == "SUPPORTED" or display == "SUPPORTED" or cell["is_pass"]:
                viol(
                    "R-inferred-distinct",
                    "INFERRED reads as SUPPORTED/pass",
                    cid,
                )

        covered = bool(run_id) or untested == "UNTESTED" or st == "NOT-APPLICABLE"
        if not covered:
            viol("R-run-id-or-untested", "cell has neither run_id nor UNTESTED", cid)

        coverage_rows.append(
            {
                "id": cid,
                "status": st,
                "untested_token": untested,
                "run_id": run_id,
                "asserted_without_evidence": cid in asserted,
                "in_client_ok": in_client_ok,
            }
        )

    program_ran_on = [
        str(x)
        for x in (matrix.get("program_ran_on") or matrix.get("program_ran_on") or [])
        if str(x).strip()
    ]
    evidenced = {p for p in platforms_with_evidence if p}
    if (
        declared_ids
        and untested_n == 0
        and (len(set(program_ran_on)) <= 1 or len(evidenced) <= 1)
    ):
        viol(
            "R-partial-green",
            f"untested=0 program_ran_on={program_ran_on} evidenced={sorted(evidenced)}",
        )

    rule_ids = [v["rule_id"] for v in violations]
    return {
        "ok": not violations,
        "violations": violations,
        "rule_ids": rule_ids,
        "counts": {
            "declared": len(declared_ids),
            "present": len(by_id),
            "blank": max(len(declared_ids) - len(by_id), 0),
            "untested": untested_n,
            "supported": supported_n,
            "inferred": inferred_n,
            "asserted_without_evidence": len(asserted),
            "installer_treated_as_run": len(installer_as_run),
        },
        "asserted_without_evidence_ids": asserted,
        "cells": coverage_rows,
        "program_ran_on": program_ran_on,
        "platforms_with_evidence": sorted(evidenced),
    }


def _mini_axes() -> dict[str, list[str]]:
    return {
        "operating_system": ["linux", "windows"],
        "client": ["claude-code"],
        "client_version": ["2.0.0"],
        "shell": ["bash"],
        "package_version": ["0.1.0"],
    }


def _receipt(os_name: str, run_id: str, result: str = "pass") -> dict[str, Any]:
    return {
        "operating_system": os_name,
        "client": "claude-code",
        "client_version": "2.0.0",
        "shell": "bash",
        "package_version": "0.1.0",
        "run_id": run_id,
        "observed_at": "2026-08-24T00:00:00Z",
        "result": result,
        "observation_kind": "in-client",
        "observed_client_version": "2.0.0",
    }


def _cell(
    os_name: str,
    status: str,
    *,
    evidence: list | None = None,
    is_pass: bool | None = None,
    display: str | None = None,
    token: str | None = None,
    css: str | None = None,
    reason: str = "fixture",
) -> dict[str, Any]:
    pass_flag = status == "SUPPORTED" if is_pass is None else is_pass
    tok = token if token is not None else status
    disp = display if display is not None else (
        "UNTESTED" if status == "NOT-CHECKED" else status
    )
    glyphs = {"SUPPORTED": "\u25cf", "NOT-CHECKED": "\u25cb", "INFERRED": "\u25c7"}
    css_map = {
        "SUPPORTED": "matrix-cell-supported",
        "NOT-CHECKED": "matrix-cell-not-checked",
        "INFERRED": "matrix-cell-inferred",
    }
    return {
        "id": f"{os_name}|claude-code|2.0.0|bash|0.1.0",
        "axes": {
            "operating_system": os_name,
            "client": "claude-code",
            "client_version": "2.0.0",
            "shell": "bash",
            "package_version": "0.1.0",
        },
        "status": status,
        "is_pass": pass_flag,
        "reason": reason,
        "evidence": list(evidence or []),
        "render": {
            "token": tok,
            "display": disp,
            "glyph": glyphs.get(status, "?"),
            "css_class": css or css_map.get(status, "matrix-cell-other"),
            "is_pass": pass_flag,
            "machine_status": status,
            "aliases": ["UNTESTED", "NEVER-RUN"] if status == "NOT-CHECKED" else [],
        },
    }


def _wrap(cells: list[dict], *, program_ran_on: list[str] | None = None) -> dict[str, Any]:
    return {
        "axes": _mini_axes(),
        "cells": cells,
        "program_ran_on": list(program_ran_on or ["linux"]),
        "untested_cell_count": sum(1 for c in cells if c.get("status") == "NOT-CHECKED"),
    }


def fixtures() -> list[dict[str, Any]]:
    conforming = _wrap(
        [
            _cell("linux", "SUPPORTED", evidence=[_receipt("linux", "ok-linux")]),
            _cell(
                "windows",
                "NOT-CHECKED",
                reason="no recorded in-client run names this cell",
            ),
        ]
    )
    blank = _wrap([_cell("linux", "SUPPORTED", evidence=[_receipt("linux", "ok-linux")])])
    no_evidence = _wrap(
        [
            _cell("linux", "SUPPORTED", evidence=[]),
            _cell("windows", "NOT-CHECKED"),
        ]
    )
    untested_pass = _wrap(
        [
            _cell("linux", "SUPPORTED", evidence=[_receipt("linux", "ok-linux")]),
            _cell("windows", "NOT-CHECKED", is_pass=True, token="PASS", display="PASS"),
        ]
    )
    untested_no_token = deepcopy(conforming)
    for cell in untested_no_token["cells"]:
        if cell["status"] == "NOT-CHECKED":
            cell["render"]["display"] = "NOT-CHECKED"
            cell["render"]["aliases"] = []
            cell["render"]["token"] = "NOT-CHECKED"
    inferred_as_supported = _wrap(
        [
            _cell("linux", "SUPPORTED", evidence=[_receipt("linux", "ok-linux")]),
            _cell(
                "windows",
                "INFERRED",
                is_pass=True,
                token="SUPPORTED",
                display="SUPPORTED",
                css="matrix-cell-supported",
            ),
        ]
    )
    installer = _wrap(
        [
            _cell(
                "linux",
                "SUPPORTED",
                evidence=[
                    {
                        **_receipt("linux", "installer-1"),
                        "observation_kind": "installer-exit",
                    }
                ],
            ),
            _cell("windows", "NOT-CHECKED"),
        ]
    )
    unpinned = _wrap(
        [
            _cell("linux", "SUPPORTED", evidence=[_receipt("linux", "ok-linux")]),
            _cell("windows", "NOT-CHECKED"),
        ]
    )
    unpinned["axes"]["client_version"] = ["UNPINNED"]
    for cell in unpinned["cells"]:
        cell["axes"]["client_version"] = "UNPINNED"
    unpinned["cells"][0]["evidence"][0]["client_version"] = "UNPINNED"
    unpinned["cells"][0]["evidence"][0]["observed_client_version"] = "UNPINNED"
    partial_green = _wrap(
        [
            _cell("linux", "SUPPORTED", evidence=[_receipt("linux", "ok-linux")]),
            _cell("windows", "SUPPORTED", evidence=[_receipt("windows", "ok-win")]),
        ],
        program_ran_on=["linux"],
    )
    no_token_or_run = _wrap(
        [
            _cell("linux", "SUPPORTED", evidence=[_receipt("linux", "ok-linux")]),
            _cell(
                "windows",
                "FAILED",
                is_pass=False,
                token="FAILED",
                display="FAILED",
                evidence=[],
            ),
        ]
    )
    return [
        {
            "id": "conforming-mixed",
            "matrix": conforming,
            "expect_ok": True,
            "expect_rule": None,
        },
        {
            "id": "blank-cell",
            "matrix": blank,
            "expect_ok": False,
            "expect_rule": "R-blank",
        },
        {
            "id": "supported-without-evidence",
            "matrix": no_evidence,
            "expect_ok": False,
            "expect_rule": "R-supported-evidence",
        },
        {
            "id": "untested-as-pass",
            "matrix": untested_pass,
            "expect_ok": False,
            "expect_rule": "R-untested-not-pass",
        },
        {
            "id": "untested-missing-token",
            "matrix": untested_no_token,
            "expect_ok": False,
            "expect_rule": "R-untested-token",
        },
        {
            "id": "inferred-as-supported",
            "matrix": inferred_as_supported,
            "expect_ok": False,
            "expect_rule": "R-inferred-distinct",
        },
        {
            "id": "installer-exit-as-run",
            "matrix": installer,
            "expect_ok": False,
            "expect_rule": "R-installer-not-evidence",
        },
        {
            "id": "unpinned-supported",
            "matrix": unpinned,
            "expect_ok": False,
            "expect_rule": "R-unpinned",
        },
        {
            "id": "all-green-partial-estate",
            "matrix": partial_green,
            "expect_ok": False,
            "expect_rule": "R-partial-green",
        },
        {
            "id": "failed-without-run-or-untested",
            "matrix": no_token_or_run,
            "expect_ok": False,
            "expect_rule": "R-run-id-or-untested",
        },
    ]


def run_fixture_battery() -> dict[str, Any]:
    rows = []
    mismatches = []
    for fix in fixtures():
        got = evaluate(fix["matrix"])
        expect_ok = bool(fix["expect_ok"])
        ok = got["ok"]
        rule = fix["expect_rule"]
        has_rule = rule is None or rule in got["rule_ids"]
        agree = (ok == expect_ok) and (expect_ok or has_rule)
        naive = naive_status_present(fix["matrix"])
        rows.append(
            {
                "row_id": fix["id"],
                "candidate_verdict": "PASS" if ok else "FAIL",
                "oracle_verdict": "PASS" if expect_ok else "FAIL",
                "candidate_failing_condition_id": got["rule_ids"][0]
                if got["rule_ids"]
                else None,
                "oracle_failing_condition_id": rule,
                "agree_verdict": (ok == expect_ok),
                "agree_failing_condition": has_rule,
                "agree": agree,
                "naive_status_present": naive,
                "naive_would_pass_defect": (not expect_ok) and naive,
                "rule_ids": got["rule_ids"],
                "counts": got["counts"],
            }
        )
        if not agree:
            mismatches.append(
                {
                    "id": fix["id"],
                    "ok": ok,
                    "expect_ok": expect_ok,
                    "rules": got["rule_ids"],
                    "violations": got["violations"],
                }
            )
    return {"rows": rows, "mismatches": mismatches, "ok": not mismatches}


if __name__ == "__main__":
    import json

    bat = run_fixture_battery()
    print(json.dumps({"ok": bat["ok"], "mismatches": bat["mismatches"]}, indent=2))
    raise SystemExit(0 if bat["ok"] else 1)
