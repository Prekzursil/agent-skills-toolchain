r"""CC-0013 — hand-edit gate for command-center/STATUS.md.

Re-derives STATUS.md from EVENTS.jsonl + receipts + the shared predicate and
diffs against the on-disk file. Drift fails the gate and names each drifted
line. A clean regenerate is silent (exit 0, no drift lines).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "command-center") not in sys.path:
    sys.path.insert(0, str(REPO / "command-center"))

import status_derive as derive  # noqa: E402


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n")


def diff_lines(expected: str, actual: str) -> list[str]:
    exp = _normalize(expected).splitlines()
    act = _normalize(actual).splitlines()
    findings: list[str] = []
    limit = max(len(exp), len(act))
    for i in range(limit):
        lineno = i + 1
        left = exp[i] if i < len(exp) else "<missing>"
        right = act[i] if i < len(act) else "<missing>"
        if left != right:
            findings.append(
                f"STATUS.md line {lineno}: expected={left!r} actual={right!r}"
            )
    return findings


def check(
    *,
    repo: Path | None = None,
    status_path: Path | None = None,
    events_path: Path | None = None,
    receipts_dir: Path | None = None,
) -> tuple[int, list[str]]:
    root = repo or derive.REPO
    target = status_path or (root / derive.STATUS_REL)
    expected = derive.render_status(
        repo=root, events_path=events_path, receipts_dir=receipts_dir
    )
    if not target.is_file():
        return 1, [f"STATUS.md missing at {target.as_posix()}"]
    actual = target.read_text(encoding="utf-8")
    findings = diff_lines(expected, actual)
    return (1 if findings else 0), findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=str(derive.REPO))
    parser.add_argument("--events", default=None)
    parser.add_argument("--receipts", default=None)
    parser.add_argument("--status", default=None)
    parser.add_argument(
        "--quiet-ok",
        action="store_true",
        help="on success print nothing (default prints a one-line SUCCESS)",
    )
    args = parser.parse_args(argv)
    root = Path(args.repo)
    events = Path(args.events) if args.events else None
    receipts = Path(args.receipts) if args.receipts else None
    status = Path(args.status) if args.status else None
    rc, findings = check(
        repo=root, status_path=status, events_path=events, receipts_dir=receipts
    )
    if rc != 0:
        print("FAILED:status-gate STATUS.md drifted from derived measurement")
        for item in findings:
            print(f"  drifted: {item}")
        print(f"FAILED:status-gate drift_lines={len(findings)}")
        return 1
    if not args.quiet_ok:
        print("SUCCESS:status-gate no drift")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
