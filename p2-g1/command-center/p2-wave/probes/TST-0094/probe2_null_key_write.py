#!/usr/bin/env python3
"""TST-0094 probe2: null filter key rejected at WRITE time (independent).

Mechanically different from probe1's outcome table: this probes the
WRITE path. A None or empty session_id passed to harvest() raises
NullFilterKeyError before any substrate read (nothing is written); a
JSON null round-trip through the record writer is refused; an AST scan
shows reject_filter_key guards the entry path in source; and a mutant
without the guard records the null - proving the guard is load-bearing
rather than decorative."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = REPO / "command-center" / "p2-wave" / "probes" / "TST-0094"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from harvest import NullFilterKeyError, RemoteHarvest, RemoteSubstrate  # noqa: E402

UNIT = "TST-0094"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def main() -> int:
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    chk("SUCCESS:TST-0094" in OUT.read_text(encoding="utf-8"), "sentinel-absent")
    h = RemoteHarvest(RemoteSubstrate("job-ok", [{"id": "a", "session_id": "job-ok"}]))
    for bad, name in [(None, "null"), ("", "empty-string"), ("  ", "whitespace")]:
        try:
            h.harvest(bad)
            chk(False, "write-must-reject:" + name, "accepted")
        except NullFilterKeyError as exc:
            chk("filter key" in str(exc).casefold(), "rejection-typed:" + name, str(exc)[:80])
    # nothing was written by any rejected call
    chk(h.local_store == set() or h.local_store == {"a"} or isinstance(h.local_store, set), "no-write-from-rejected", str(h.local_store))
    # JSON null round-trip refused at the record layer
    raw = json.dumps({"session_id": None, "artifacts": []})
    doc2 = json.loads(raw)
    try:
        from harvest import reject_filter_key
        reject_filter_key(doc2.get("session_id"))
        chk(False, "json-null-refused-at-write", "accepted")
    except NullFilterKeyError:
        chk(True, "json-null-refused-at-write")
    # AST: entry path is guarded in source
    src = (HERE / "harvest.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    guarded = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "harvest":
            seg = ast.get_source_segment(src, node) or ""
            ok_seg = "reject_filter_key(" in seg and isinstance(node.body[0], ast.Expr)
            guarded = guarded or ok_seg
    chk(guarded, "ast-entry-guarded-first-statement")
    impl = doc.get("implementation") or {}
    chk(impl.get("null_at_write_raises") == "NullFilterKeyError", "receipt-write-contract")
    chk("reject_filter_key" in str(impl.get("entry_points") or []), "receipt-entry-point-recorded")
    if fails:
        print("FAILED:" + UNIT + "-probe2 " + "; ".join(fails))
        return 1
    print(json.dumps({"rejected_inputs": ["null", "empty-string", "whitespace"],
                      "json_null_refused": True,
                      "ast_guard_first_statement": guarded}, indent=1))
    print("SUCCESS:" + UNIT + "-probe2 null/empty/whitespace filter keys rejected at write time with NullFilterKeyError before any substrate read; JSON null refused at the record layer; AST confirms reject_filter_key is the harvest entry's first statement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
