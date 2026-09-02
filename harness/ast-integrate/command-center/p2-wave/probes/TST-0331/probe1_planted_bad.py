#!/usr/bin/env python3
"""Probe 1: planted bad anchors DETECTED; valid twins pass; no false positives."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
import validator as V  # noqa: E402

UNIT = "TST-0331"
RECEIPTS = REPO / "command-center" / "receipts"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def _eid(row: dict) -> str | None:
    raw = str(row.get("raw") or "")
    if not raw.startswith("{"):
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict) and parsed.get("id"):
        return str(parsed["id"])
    return None


def always_ok(anchor: V.Anchor, ctx: V.ResolveContext) -> V.Resolution:
    del ctx
    return V.Resolution(anchor, V.RESOLVED, "always-ok-mutant")


def independent_file_line(root: Path, rel: str, line: int, snippet: str | None) -> bool:
    if not V.independent_file_line_ok(root, rel, line):
        return False
    if not snippet:
        return True
    text = (root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
    if line < 1 or line > len(text):
        return False
    return snippet in text[line - 1]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0331-p1-") as td:
        root = F.write_fixture_tree(Path(td))
        ctx = V.ResolveContext(root=root, archive_index=F.archive_index(root))
        doc = F.planted_receipt()
        audit = V.audit_receipt(doc, ctx)
        by_id: dict[str, dict] = {}
        for row in audit.resolved + audit.unresolved + audit.unparseable:
            eid = _eid(row)
            if eid:
                by_id[eid] = row

        required_unresolved = {
            "planted-missing-file": "missing-worktree-file",
            "planted-oob-line": "line-out-of-range",
            "planted-command-never-run": "command-never-run",
        }
        detected: dict[str, str] = {}
        for eid, prefix in required_unresolved.items():
            row = by_id.get(eid)
            if row is None:
                return fail(f"{eid} not extracted")
            if row.get("status") != V.UNRESOLVED:
                return fail(f"{eid} status={row.get('status')} reason={row.get('reason')}")
            reason = str(row.get("reason") or "")
            if prefix not in reason:
                return fail(f"{eid} expected {prefix} in {reason}")
            detected[eid] = reason

        for eid in (
            "valid-file-line",
            "valid-file",
            "valid-command",
            "valid-url",
            "valid-inferred",
        ):
            row = by_id.get(eid)
            if row is None or row.get("status") != V.RESOLVED:
                return fail(f"{eid} did not resolve: {row}")

        url_bad = by_id.get("planted-url-no-archive")
        if not url_bad or url_bad.get("status") != V.UNRESOLVED:
            return fail(f"url without archive not unresolved: {url_bad}")
        unp = by_id.get("unparseable-empty")
        if not unp or unp.get("status") != V.UNPARSEABLE:
            return fail(f"empty item not unparseable: {unp}")

        mutant_missed = []
        for a in V.extract_anchors(doc):
            eid = _eid({"raw": a.raw})
            if eid in required_unresolved and always_ok(a, ctx).status == V.RESOLVED:
                mutant_missed.append(eid)
        if set(mutant_missed) != set(required_unresolved):
            return fail(f"always-ok mutant missed set {mutant_missed}")

        live_paths = sorted(p for p in RECEIPTS.glob("*.json") if p.name != "TST-0331.json")
        live_ctx = V.ResolveContext(root=REPO)
        live = V.audit_receipts(live_paths, live_ctx)
        disagreements = []
        independently_valid = 0
        independently_invalid = 0
        for row in live["resolved"] + live["unresolved"]:
            if row.get("kind") != V.KIND_FILE_LINE or row.get("revision"):
                continue
            path = str(row.get("path") or "")
            line = row.get("line")
            if not path or not isinstance(line, int):
                continue
            snippet = row.get("snippet")
            snippet_s = snippet if isinstance(snippet, str) else None
            ok = independent_file_line(REPO, path, line, snippet_s)
            status = row.get("status")
            if ok:
                independently_valid += 1
                if status != V.RESOLVED:
                    disagreements.append(
                        {"path": path, "line": line, "ok": True, "status": status}
                    )
            else:
                independently_invalid += 1
                if status != V.UNRESOLVED:
                    disagreements.append(
                        {"path": path, "line": line, "ok": False, "status": status}
                    )
        if disagreements:
            return fail(f"false-positive/negative vs independent stat: {disagreements[:5]}")
        if independently_valid < 1:
            return fail("no independently-valid live file:line anchors (detector starved)")

        payload = {
            "pass": True,
            "probe": "probe1-planted-bad",
            "unit_id": UNIT,
            "planted_detected": detected,
            "valid_resolved": [
                "valid-file-line",
                "valid-file",
                "valid-command",
                "valid-url",
                "valid-inferred",
            ],
            "mutant_missed": mutant_missed,
            "url_without_archive_unresolved": True,
            "live_file_line_independently_valid": independently_valid,
            "live_file_line_independently_invalid": independently_invalid,
            "disagreements": disagreements,
            "planted_checked": audit.checked,
            "planted_unresolved_count": len(audit.unresolved),
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            "planted_missing_file=DETECTED planted_oob_line=DETECTED "
            "planted_command_never_run=DETECTED valid_twins=PASS "
            f"live_valid={independently_valid} disagreements=0"
        )
        print(
            f"SUCCESS:{UNIT}-probe1 planted bad anchors DETECTED; "
            "valid twins pass; live file:line agrees with independent stat"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
