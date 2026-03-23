#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def file_summary(path: Path) -> dict:
    lines = 0
    errors = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for number, line in enumerate(handle, start=1):
                lines += 1
                try:
                    json.loads(line)
                except json.JSONDecodeError as exc:
                    errors.append(f"line {number}: {exc.msg}")
                    break
    except UnicodeDecodeError as exc:
        errors.append(f"unicode: {exc}")
    return {
        "path": str(path),
        "name": path.name,
        "size": path.stat().st_size,
        "lines": lines,
        "parse_ok": not errors,
        "errors": errors,
    }


def collect(root: Path) -> list[dict]:
    sessions = root / "sessions"
    if not sessions.exists():
        return []
    return [file_summary(path) for path in sessions.rglob("rollout-*.jsonl")]


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory Codex session files across multiple roots.")
    parser.add_argument("roots", nargs="+", help="Candidate Codex roots.")
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    args = parser.parse_args()

    reports = []
    groups = {}
    for raw_root in args.roots:
        root = Path(raw_root).expanduser()
        files = collect(root)
        reports.append({"root": str(root), "files": files, "count": len(files)})
        for item in files:
            groups.setdefault(item["name"], []).append(item)

    summary = {
        "roots": reports,
        "total_files": sum(report["count"] for report in reports),
        "duplicate_groups": sum(1 for items in groups.values() if len(items) > 1),
        "invalid_files": sum(1 for items in groups.values() for item in items if not item["parse_ok"]),
        "groups": groups,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
        return 0

    print(
        f"roots={len(reports)} total_files={summary['total_files']} "
        f"duplicate_groups={summary['duplicate_groups']} invalid_files={summary['invalid_files']}"
    )
    for report in reports:
        print(f"- {report['root']}: {report['count']} session files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
