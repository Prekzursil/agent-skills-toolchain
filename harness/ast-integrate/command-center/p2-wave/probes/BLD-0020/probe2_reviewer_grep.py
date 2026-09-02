#!/usr/bin/env python3
"""Probe 2: independent grep of two prefixes vs census declaring-registry counts."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

ROOTS = [HERE / "fixtures" / "estate", HERE / "fixtures" / "controls"]
HEADING = re.compile(r"^#{1,6}\s+.*\b([A-Z]{1,8}-\d{1,4})\b")
TABLE = re.compile(r"^\|\s*([A-Z]{1,8}-\d{1,4})\s*\|")
JSON_ID = re.compile(
    r'"(?:id|unit_id|option_id|card_id|deliverable_id)"\s*:\s*"([A-Z]{1,8}-\d{1,4})"'
)
YAML_ID = re.compile(
    r"^\s*(?:id|unit_id|option_id|card_id|deliverable_id)\s*:\s*['\"]?([A-Z]{1,8}-\d{1,4})",
    re.IGNORECASE,
)


def independent_registries(prefix: str) -> set[str]:
    """Line-grep declaration sites without calling census.scan_file."""
    found: set[str] = set()
    needle = re.compile(rf"\b{re.escape(prefix)}-\d{{1,4}}\b")
    for root in ROOTS:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in C.TEXT_SUFFIX:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            rel = path.relative_to(root).as_posix()
            suffix = path.suffix.lower()
            for line in text.splitlines():
                if not needle.search(line):
                    continue
                hit = False
                if suffix == ".json":
                    hit = any(m.group(1).startswith(prefix + "-") for m in JSON_ID.finditer(line))
                elif suffix in {".yml", ".yaml"}:
                    m = YAML_ID.match(line)
                    hit = bool(m and m.group(1).startswith(prefix + "-"))
                else:
                    hm = HEADING.match(line)
                    tm = TABLE.match(line)
                    hit = bool(
                        (hm and hm.group(1).startswith(prefix + "-"))
                        or (tm and tm.group(1).startswith(prefix + "-"))
                    )
                if hit:
                    found.add(C.logical_registry(rel))
                    break
    return found


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0020-probe2 {msg}")
    return 1


def main() -> int:
    snap = C.walk(ROOTS)
    decls = C.declarations_by_prefix(snap)
    # Reviewer samples the two colliding prefixes on the control corpus (full set).
    prefixes = [row["prefix"] for row in C.colliding(decls)]
    if sorted(prefixes) != ["M", "QQ"]:
        return fail(f"unexpected-colliding:{prefixes}")
    report = []
    for prefix in prefixes:
        census_regs = set(decls[prefix])
        grep_regs = independent_registries(prefix)
        ok = census_regs == grep_regs
        report.append(
            {
                "prefix": prefix,
                "census_registries": sorted(census_regs),
                "grep_registries": sorted(grep_regs),
                "count_match": ok,
            }
        )
        if not ok:
            return fail(f"{prefix} census={sorted(census_regs)} grep={sorted(grep_regs)}")
    payload = {"probe": "probe2-reviewer-grep", "prefixes": report, "pass": True}
    print(json.dumps(payload, sort_keys=True))
    print(
        "reviewer M="
        f"{len(report[0]['census_registries'])} QQ={len(report[1]['census_registries'])} match=True"
    )
    print("SUCCESS:BLD-0020-probe2 independent-grep declaring-registry-counts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
