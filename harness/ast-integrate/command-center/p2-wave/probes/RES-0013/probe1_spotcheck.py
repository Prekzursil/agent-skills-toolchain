#!/usr/bin/env python3
"""Named probe 1: spot-check 5 recorded rows against changelog + second artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extractor as E  # noqa: E402

ART = REPO / "command-center/research/RES-0013.json"
SENTINEL = (
    "SUCCESS:RES-0013 in the receipt AND a version-indexed breaking-change "
    "register where >=5 rows are corroborated by a second artifact"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0013-probe1 {msg}")
    return 1


def section_for(changelog: str, version: str) -> str:
    lines = changelog.splitlines()
    start = None
    chunks: list[str] = []
    for line in lines:
        m = E.HEADING_RE.match(line)
        if m:
            if start is not None:
                break
            if m.group(1) == version:
                start = line
                chunks.append(line)
            continue
        if start is not None:
            chunks.append(line)
    return "\n".join(chunks)


def second_text(row: dict) -> tuple[str, str]:
    second = row.get("second_artifact") or {}
    rel = str(second.get("path") or "")
    if not rel:
        return "", ""
    path = REPO / rel
    if not path.is_file():
        return rel, ""
    if rel.endswith(".json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        return rel, str(doc.get("body") or json.dumps(doc))
    return rel, path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("catalog sentinel absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "RES-0013":
        return fail(f"unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    payload = E.registry_payload(doc)
    if int(payload.get("corroborated_count") or 0) < 5:
        return fail(f"corroborated_count {payload.get('corroborated_count')}")

    changelog = (HERE / "snapshots" / "CHANGELOG.md").read_text(encoding="utf-8")
    by_id = {r["id"]: r for r in (payload.get("register") or []) if isinstance(r, dict)}
    ids = list(payload.get("spot_check_ids") or [])
    if len(ids) < 5:
        return fail(f"spot_check_ids n={len(ids)}")

    live = E.live_extract()
    live_by = {r["id"]: r for r in live["rows"]}
    checked = []
    for rid in ids[:5]:
        rec = by_id.get(rid)
        if rec is None:
            return fail(f"artifact missing row {rid}")
        live_row = live_by.get(rid)
        if live_row is None:
            return fail(f"live extractor missing {rid}")
        if live_row["changelog_excerpt"] != rec.get("changelog_excerpt"):
            return fail(f"excerpt drift {rid}")
        if rec.get("corroborated") is not True:
            return fail(f"recorded uncorroborated {rid}")
        section = section_for(changelog, rec["version"])
        if rec["changelog_excerpt"] not in section:
            return fail(f"excerpt not in changelog section {rid} v={rec['version']}")
        rel, body = second_text(rec)
        if not rel or not body:
            return fail(f"second artifact unreadable {rid}")
        if E.norm(rec["changelog_excerpt"])[:48] not in E.norm(body):
            return fail(f"second artifact missing needle {rid} path={rel}")
        checked.append(
            {
                "id": rid,
                "version": rec["version"],
                "surface": rec["surface"],
                "second_path": rel,
                "ok": True,
            }
        )

    out = {
        "checked": checked,
        "n": len(checked),
        "corroborated_count": payload.get("corroborated_count"),
        "live_row_count": live["row_count"],
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:RES-0013-probe1 spot-check 5 rows against changelog and second artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
