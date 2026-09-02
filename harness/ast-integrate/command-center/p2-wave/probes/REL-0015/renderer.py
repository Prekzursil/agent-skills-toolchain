"""Publish the compatibility matrix. Missing receipts become NOT-CHECKED, never PASS."""
from __future__ import annotations

from typing import Any, Iterable

CSS = {
    "pass": "rel0015-pass",
    "fail": "rel0015-fail",
    "not_checked": "rel0015-not-checked",
}

TOKENS = {
    "PASS": "PASS",
    "FAIL": "FAIL",
    "NOT-CHECKED": "NOT-CHECKED",
}

STATUS_CSS = {
    "PASS": CSS["pass"],
    "FAIL": CSS["fail"],
    "NOT-CHECKED": CSS["not_checked"],
}


def normalize_status(raw: str) -> str:
    s = (raw or "").upper().replace("_", "-")
    if s in {"PASS", "FAIL"}:
        return s
    if s in {"NOT-CHECKED", "NOT-CHECKED", "UNTESTED", "SKIPPED"}:
        return "NOT-CHECKED"
    return "NOT-CHECKED"


def arithmetic(published: list[dict[str, Any]]) -> dict[str, Any]:
    receipts = [c for c in published if c["status"] in {"PASS", "FAIL"}]
    not_checked = [c for c in published if c["status"] == "NOT-CHECKED"]
    n_pub, n_rec, n_nc = len(published), len(receipts), len(not_checked)
    return {
        "published_cells": n_pub,
        "executed_receipts": n_rec,
        "not_checked_entries": n_nc,
        "identity": "published_cells = executed_receipts + not_checked_entries",
        "holds": n_pub == n_rec + n_nc,
        "receipt_cell_ids": [c["cell_id"] for c in receipts],
        "not_checked_cell_ids": [c["cell_id"] for c in not_checked],
    }


def publish(
    contract_cells: Iterable[dict[str, str]],
    receipts_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Render every declared cell. Absence of a receipt => NOT-CHECKED, never blank/PASS.

    Neighbor cells are never consulted. A FAIL receipt is kept in the table.
    """
    published: list[dict[str, Any]] = []
    for spec in contract_cells:
        cid = spec["cell_id"]
        receipt = receipts_by_id.get(cid)
        if receipt is None:
            row = {
                "cell_id": cid,
                "os": spec["os"],
                "client": spec["client"],
                "declared_version": spec["declared_version"],
                "status": "NOT-CHECKED",
                "reason": "no executed-cell receipt on disk; not inferred from a neighbour",
                "inferred_from_neighbour": False,
                "receipt_present": False,
            }
        else:
            status = normalize_status(str(receipt.get("status") or ""))
            if status == "NOT-CHECKED":
                row = {
                    "cell_id": cid,
                    "os": spec["os"],
                    "client": spec["client"],
                    "declared_version": spec["declared_version"],
                    "status": "NOT-CHECKED",
                    "reason": str(receipt.get("reason") or "not executed"),
                    "inferred_from_neighbour": False,
                    "receipt_present": False,
                }
            else:
                row = {
                    "cell_id": cid,
                    "os": spec["os"],
                    "client": spec["client"],
                    "declared_version": spec["declared_version"],
                    "status": status,
                    "observed_client_build_string": receipt.get(
                        "observed_client_build_string"
                    )
                    or receipt.get("observed_client_build_string"),
                    "reason": str(receipt.get("reason") or ""),
                    "inferred_from_neighbour": False,
                    "receipt_present": True,
                }
        published.append(row)

    html = _html(published)
    markdown = _markdown(published)
    arith = arithmetic(published)
    return {
        "published": published,
        "html": html,
        "markdown": markdown,
        "css_classes": dict(CSS),
        "visual_tokens": {
            "pass": TOKENS["PASS"],
            "fail": TOKENS["FAIL"],
            "not_checked": TOKENS["NOT-CHECKED"],
        },
        "arithmetic": arith,
    }


def _html(published: list[dict[str, Any]]) -> str:
    rows = []
    for c in published:
        cls = STATUS_CSS[c["status"]]
        token = TOKENS[c["status"]]
        reason = (c.get("reason") or "").replace("<", "&lt;")[:180]
        rows.append(
            "<tr>"
            f"<td>{c['os']}</td><td>{c['client']}</td>"
            f"<td>{c['declared_version']}</td>"
            f'<td class="{cls}">{token}</td>'
            f"<td>{reason}</td>"
            "</tr>"
        )
    style = (
        f".{CSS['pass']}{{background:#1b7f3a;color:#fff;font-weight:700}}"
        f".{CSS['fail']}{{background:#a11;color:#fff;font-weight:700}}"
        f".{CSS['not_checked']}{{background:repeating-linear-gradient("
        "45deg,#f4e8a8,#f4e8a8 6px,#c4b56a 6px,#c4b56a 12px);"
        "color:#111;font-weight:700}"
    )
    return (
        "<style>" + style + "</style>"
        "<table class=\"rel0015-matrix\">"
        "<thead><tr><th>os</th><th>client</th><th>version</th>"
        "<th>result</th><th>note</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table>"
    )


def _markdown(published: list[dict[str, Any]]) -> str:
    lines = [
        "| os | client | version | result | note |",
        "| --- | --- | --- | --- | --- |",
    ]
    for c in published:
        token = TOKENS[c["status"]]
        note = (c.get("reason") or "").replace("|", "/")[:120]
        lines.append(
            f"| {c['os']} | {c['client']} | {c['declared_version']} | {token} | {note} |"
        )
    return "\n".join(lines) + "\n"


def renderer_controls() -> dict[str, Any]:
    """Catalog tests: delete-receipt, fail-survives, all-pass vs mixed."""
    specs = [
        {
            "cell_id": "linux::generic-mcp::1.0.0",
            "os": "linux",
            "client": "generic-mcp",
            "declared_version": "1.0.0",
        },
        {
            "cell_id": "linux::claude-code::current",
            "os": "linux",
            "client": "claude-code",
            "declared_version": "current",
        },
        {
            "cell_id": "windows::generic-mcp::1.0.0",
            "os": "windows",
            "client": "generic-mcp",
            "declared_version": "1.0.0",
        },
    ]
    pass_r = {
        "cell_id": specs[0]["cell_id"],
        "status": "PASS",
        "observed_client_build_string": "rel-0015-generic-mcp-host/1.0.0-fabricated",
        "reason": "hook side-effect observed",
    }
    fail_r = {
        "cell_id": specs[1]["cell_id"],
        "status": "FAIL",
        "observed_client_build_string": "claude-code/broken-build",
        "reason": "hook side-effect missing",
    }
    mixed = {specs[0]["cell_id"]: pass_r, specs[1]["cell_id"]: fail_r}
    all_pass = {
        s["cell_id"]: {
            "cell_id": s["cell_id"],
            "status": "PASS",
            "observed_client_build_string": "fabricated-all-pass",
            "reason": "fabricated",
        }
        for s in specs
    }
    r_mixed = publish(specs, mixed)
    r_all = publish(specs, all_pass)
    deleted = dict(mixed)
    deleted.pop(specs[0]["cell_id"])
    r_del = publish(specs, deleted)
    del_row = next(c for c in r_del["published"] if c["cell_id"] == specs[0]["cell_id"])
    fail_row = next(c for c in r_mixed["published"] if c["cell_id"] == specs[1]["cell_id"])
    miss_row = next(c for c in r_mixed["published"] if c["cell_id"] == specs[2]["cell_id"])
    del_md_line = [
        ln for ln in r_del["markdown"].splitlines() if specs[0]["client"] in ln and "linux" in ln
    ]
    blank = any(
        ln for ln in r_del["markdown"].splitlines() if ln.startswith("| linux | generic-mcp |") and "||" in ln.replace(" ", "")
    )
    classes = {CSS["pass"], CSS["fail"], CSS["not_checked"]}
    return {
        "delete_receipt_status": del_row["status"],
        "delete_receipt_shows_not_checked": del_row["status"] == "NOT-CHECKED",
        "delete_receipt_not_pass": del_row["status"] != "PASS",
        "delete_receipt_not_blank": bool(del_md_line) and "NOT-CHECKED" in del_md_line[0] and not blank,
        "fail_survives": fail_row["status"] == "FAIL"
        and "FAIL" in r_mixed["html"]
        and "FAIL" in r_mixed["markdown"],
        "missing_is_not_checked": miss_row["status"] == "NOT-CHECKED",
        "all_pass_differs_from_mixed": r_all["html"] != r_mixed["html"]
        and r_all["markdown"] != r_mixed["markdown"],
        "visual_classes_distinct": len(classes) == 3,
        "css_in_html": all(v in r_mixed["html"] for v in CSS.values()),
        "pass": (
            del_row["status"] == "NOT-CHECKED"
            and fail_row["status"] == "FAIL"
            and r_all["html"] != r_mixed["html"]
            and miss_row["status"] == "NOT-CHECKED"
            and len(classes) == 3
        ),
    }


def table_from_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Read published_table from a receipt (top-level or report payload)."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    table = doc.get("published_table") or report.get("published_table") or {}
    return table if isinstance(table, dict) else {}


def arithmetic_from_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Read arithmetic from a receipt (top-level or report payload)."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    arith = doc.get("arithmetic") or report.get("arithmetic") or {}
    return arith if isinstance(arith, dict) else {}


renderer_controls = renderer_controls
