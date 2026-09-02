"""Matrix validator: no PASS on a cell, every cell has a probe, no-assertion probes fail."""
from __future__ import annotations

import json
from pathlib import Path

from axes import all_cells

FORBIDDEN_CELL_STATUS = frozenset({"PASS", "OK", "SUPPORTED", "GREEN"})
ALLOWED_CELL_STATUS = frozenset(
    {"RUN", "NOT-CHECKED", "FAIL", "NOT-APPLICABLE", "NEVER-RUN"}
)
ASSERTION_MARKERS = (
    "ASSERTION:",
    "assert ",
    "assert(",
    "raise SystemExit",
    "sys.exit(1)",
    "FAILED:",
)


def probe_has_assertion(text: str) -> bool:
    return any(m in text for m in ASSERTION_MARKERS)


def validate_probe_source(path: Path) -> list[str]:
    errs: list[str] = []
    if not path.is_file():
        return [f"probe-absent:{path.as_posix()}"]
    raw = path.read_bytes()
    text = raw.decode("utf-8", "replace")
    if not probe_has_assertion(text):
        errs.append(f"no-assertion:{path.as_posix()}")
    return errs


def get_cells(doc: dict) -> list | None:
    """Cells live at top-level (legacy) or report.cells (receipt_core)."""
    cells = doc.get("cells")
    if isinstance(cells, list):
        return cells
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    cells = report.get("cells")
    return cells if isinstance(cells, list) else None


def validate_matrix(doc: dict, repo: Path) -> list[str]:
    errs: list[str] = []
    if not isinstance(doc, dict):
        return ["not-an-object"]
    cells = get_cells(doc)
    if not isinstance(cells, list):
        return ["cells-missing"]
    expected = {cid: (os_name, shell) for cid, os_name, shell in all_cells()}
    seen: set[str] = set()
    for cell in cells:
        if not isinstance(cell, dict):
            errs.append("cell-not-object")
            continue
        cid = str(cell.get("id") or "")
        st = str(cell.get("status") or "")
        probe = str(cell.get("probe_path") or "").replace("\\", "/")
        if cid in seen:
            errs.append(f"duplicate-cell:{cid}")
        seen.add(cid)
        if st in FORBIDDEN_CELL_STATUS or st == "PASS":
            errs.append(f"forbidden-status:{cid}:{st}")
        if st not in ALLOWED_CELL_STATUS:
            errs.append(f"unknown-status:{cid}:{st}")
        if not probe:
            errs.append(f"probe-path-missing:{cid}")
        else:
            errs.extend(validate_probe_source(repo / probe))
        if cid in expected:
            os_name, shell = expected[cid]
            if cell.get("os") != os_name or cell.get("shell") != shell:
                errs.append(f"axis-mismatch:{cid}")
        if st == "RUN" and not cell.get("probe_executed_on_host"):
            errs.append(f"run-without-execution:{cid}")
    missing = sorted(set(expected) - seen)
    extra = sorted(seen - set(expected))
    if missing:
        errs.append(f"missing-cells:{','.join(missing)}")
    if extra:
        errs.append(f"extra-cells:{','.join(extra)}")
    if len(cells) != 18:
        errs.append(f"cell-count:{len(cells)}")
    counts = {"RUN": 0, "NOT-CHECKED": 0, "FAIL": 0, "NOT-APPLICABLE": 0, "NEVER-RUN": 0}
    for cell in cells:
        if isinstance(cell, dict):
            st = str(cell.get("status") or "")
            if st in counts:
                counts[st] += 1
    summed = sum(counts.values())
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    arith = report.get("arithmetic") if isinstance(report, dict) else None
    if isinstance(arith, dict):
        if int(arith.get("cells") or 0) != 18:
            errs.append("arithmetic-cells-not-18")
        got_sum = int(arith.get("sum") or -1)
        if got_sum != summed:
            errs.append(f"arithmetic-sum-mismatch:{got_sum}!={summed}")
    if summed != 18:
        errs.append(f"status-sum:{summed}")
    return errs


def validate_receipt_file(path: Path, repo: Path) -> list[str]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"unparseable:{type(exc).__name__}"]
    return validate_matrix(doc, repo)
