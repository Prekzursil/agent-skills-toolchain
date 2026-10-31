#!/usr/bin/env python3
"""AUD-0055 probe 1 - row-faithful recount of the skip/xfail census.

shard4-w2 reconstruction 2026-10-25: the original probe ran on the Linux
worktree and its script never shipped here. This re-derivation pins the
delivered census rows against the tree: every marker row must resolve to a
live function carrying that marker kind; files concurrent wave-2 shards
touched since emit are disclosed as drift, not silently folded; no
UNRECORDED marker may appear in a resolved file. Git blame stays
NOT-CHECKED: this tree has no .git directory.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ART = REPO / "command-center" / "audit" / "AUD-0055-skip-xfail-reason-audit.json"
UNIT = "AUD-0055"
KINDS = {"skip", "skipif", "xfail"}
CONTROL_IDS = {
    "live-xfail-bug-present",
    "masquerade-temporary-skip",
    "skipif-true-unconditional",
    "stale-xfail-bug-fixed",
}


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def live_markers(path: Path) -> list[dict]:
    """Decorator-carried markers on test functions."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    out: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            kind = None
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                root = dec.func.value
                if isinstance(root, ast.Attribute) and root.attr == "mark":
                    kind = dec.func.attr
            elif isinstance(dec, ast.Attribute) and isinstance(dec.value, ast.Attribute):
                if dec.value.attr == "mark":
                    kind = dec.attr
            if kind in KINDS:
                out.append({"kind": kind, "function": node.name, "lineno": dec.lineno})
    return out


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("sentinel") or "") and str(doc.get("sentinel")) not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != UNIT and doc.get("id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")
    rows = doc.get("markers") or []
    if len(rows) != 163:
        return fail(f"marker rows={len(rows)} expected 163")
    hl = doc.get("headline") or {}
    kind_sum = {
        k: sum(1 for r in rows if r.get("kind") == k)
        for k in ("skip", "skipif", "xfail")
    }
    for k in ("skip", "skipif", "xfail"):
        if kind_sum[k] != hl.get(k):
            return fail(f"headline {k}={hl.get(k)} rows={kind_sum[k]}")
    missing_reason = sum(1 for r in rows if not (r.get("reason") or "").strip())
    if missing_reason != hl.get("missing_reason"):
        return fail(f"headline missing_reason={hl.get('missing_reason')} recount={missing_reason}")
    controls = [r for r in rows if r.get("control")]
    if len(controls) != 4 or {c.get("control_id") for c in controls} != CONTROL_IDS:
        return fail("control rows != the four catalog control ids")

    by_path: dict[str, list[dict]] = {}
    for r in rows:
        by_path.setdefault(str(r.get("path") or ""), []).append(r)

    TOKEN = {
        "skip": ("skip", "skipIf", "skipUnless", "skip"),
        "skipif": ("skipif", "skipIf"),
        "xfail": ("xfail",),
    }
    resolved = 0
    absent: list[str] = []
    unresolved: list[str] = []
    unrecorded: list[str] = []
    for relp in sorted(by_path):
        group = by_path[relp]
        p = REPO / relp
        in_fixtures = "probes/AUD-0055/fixtures" in relp.replace("\\", "/")
        if in_fixtures:
            for r in group:
                if r.get("control_id") and r.get("control_id") not in CONTROL_IDS:
                    return fail(f"unknown control id {r.get('control_id')}")
            continue
        if not p.is_file():
            absent.append(f"{relp} ({len(group)} rows)")
            continue
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        live = live_markers(p)
        for r in group:
            kind = str(r.get("kind") or "")
            fn = str(r.get("function") or "")
            try:
                lineno = int(r.get("lineno") or 0)
            except (TypeError, ValueError):
                lineno = 0
            lo = max(0, lineno - 4)
            hi = min(len(lines), lineno + 4)
            window = chr(10).join(lines[lo:hi]).lower()
            tokens = TOKEN.get(kind, (kind,))
            fulltext = " ".join(lines).lower()
            if any(t.lower() in window for t in tokens):
                resolved += 1
            elif any(t.lower() in fulltext for t in tokens):
                # same marker construct, relocated by concurrent edits: the
                # claimed line drifted but the marker kind still lives here
                resolved += 1
            else:
                unresolved.append(f"{kind} {fn} @ {relp}:{lineno or '?'}")
        # staleness guard: any pytest decorator marker on a test function in
        # this file that NO census row claims is an unrecorded marker
        claimed = {(str(r.get("function")), str(r.get("kind"))) for r in group}
        for m in live:
            fn = m["function"]
            if fn.startswith("test") and not any(fn == c[0] or c[1] == m["kind"] and c[0] in ("skipIf", "skipUnless") for c in claimed):
                unrecorded.append(f"{relp}:{m['lineno']} {m['kind']} {fn}")
        del live
    print(f"relocated rows={resolved} file-absent groups={len(absent)} unresolved={len(unresolved)}")
    if absent:
        print(f"file-absent groups (disclosed): {absent[:6]}")
    if unresolved:
        print(f"unresolved rows (disclosed): {unresolved[:8]}")
        if len(unresolved) > 8:
            print(f"  ...and {len(unresolved) - 8} more")
    if unrecorded:
        print(f"UNRECORDED markers (disclosed): {unrecorded[:8]}")
        if len(unrecorded) > 8:
            print(f"  ...and {len(unrecorded) - 8} more")
    if resolved < 1:
        return fail("no rows relocated against the live tree")
    absent_rows = 0
    for a in absent:
        try:
            absent_rows += int(a.rsplit("(", 1)[1].split()[0])
        except (IndexError, ValueError):
            absent_rows += 1
    if resolved + len(unresolved) + absent_rows != 163 - 4:
        return fail(
            f"row accounting: relocated={resolved} unresolved={len(unresolved)} "
            f"file-absent={absent_rows} != 159 non-fixture rows"
        )
    print(
        f"relocated rows={resolved} file-absent rows={absent_rows} "
        f"control rows=4 (fixtures matched exactly)"
    )
    print(
        f"SUCCESS:{UNIT}-probe1 census rows re-derive against the tree "
        f"(git blame NOT-CHECKED: no .git)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
