r"""CC-0013 named probes — the four catalog tests_required, executed for real.

1. Hand-edit a counter -> gate fires and names the drifted line.
2. Regenerate -> gate silent.
3. Determinism: two runs over unchanged inputs are byte-identical.
4. Empty events -> board status NOT-STARTED, never green.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE_DIR = Path(__file__).resolve().parent
DERIVE = REPO / "command-center" / "status_derive.py"
GATE = REPO / "command-center" / "status_gate.py"
STATUS = REPO / "command-center" / "STATUS.md"
EVENTS = REPO / "command-center" / "events" / "EVENTS.jsonl"
RECEIPTS = REPO / "command-center" / "receipts"


def _run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd or REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _write(name: str, text: str) -> Path:
    path = PROBE_DIR / name
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    return path


def probe_hand_edit_names_line() -> tuple[bool, str]:
    """Hand-edit a counter; gate must fail and name the drifted line."""
    # Fresh derive first so the only drift is the deliberate hand-edit.
    rc0, out0 = _run([sys.executable, str(DERIVE)])
    if rc0 != 0:
        text = f"FAIL: pre-edit derive rc={rc0}\n{out0}"
        _write("probe-hand-edit.raw.txt", text)
        return False, text

    lines = STATUS.read_text(encoding="utf-8").splitlines()
    target_idx = None
    original = None
    mutated = None
    for i, line in enumerate(lines):
        # Prefer a metrics-table counter row (event_records / receipt_files).
        if "| event_records |" in line or "| receipt_files |" in line:
            m = re.search(r"\|\s*([^|]+)\s*\|\s*(\d+)\s*\|", line)
            if not m:
                continue
            target_idx = i
            original = line
            number = m.group(2)
            bumped = str(int(number) + 1)
            mutated = line.replace(f"| {number} |", f"| {bumped} |", 1)
            if mutated == line:
                mutated = line.replace(number, bumped, 1)
            lines[i] = mutated
            break
    if target_idx is None or original is None or mutated is None:
        return False, "FAIL: could not locate a counter line to hand-edit\n"

    backup = STATUS.read_text(encoding="utf-8")
    try:
        STATUS.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        rc, out = _run([sys.executable, str(GATE)])
    finally:
        STATUS.write_text(backup, encoding="utf-8", newline="\n")

    lineno = target_idx + 1
    named = f"line {lineno}" in out
    # Require the counter line to be named; extra drift from races is allowed but the
    # catalog asks that the drifted counter line is named.
    fired = rc != 0 and "FAILED:status-gate" in out and named
    text = (
        "PROBE=CC-0013-hand-edit\n"
        f"PRE_DERIVE_RC={rc0}\n"
        f"TARGET_LINE={lineno}\n"
        f"ORIGINAL={original!r}\n"
        f"MUTATED={mutated!r}\n"
        f"GATE_RC={rc}\n"
        f"GATE_NAMED_LINE={named}\n"
        f"GATE_OUTPUT_BEGIN\n{out}GATE_OUTPUT_END\n"
        f"VERDICT={'PASS' if fired else 'FAIL'}\n"
    )
    _write("probe-hand-edit.raw.txt", text)
    return fired, text


def probe_regenerate_silent() -> tuple[bool, str]:
    rc1, out1 = _run([sys.executable, str(DERIVE)])
    rc2, out2 = _run([sys.executable, str(GATE), "--quiet-ok"])
    silent = rc2 == 0 and out2.strip() == ""
    ok = rc1 == 0 and silent
    text = (
        "PROBE=CC-0013-regenerate-silent\n"
        f"DERIVE_RC={rc1}\n"
        f"DERIVE_OUT={out1.strip()!r}\n"
        f"GATE_RC={rc2}\n"
        f"GATE_OUT={out2!r}\n"
        f"GATE_SILENT={silent}\n"
        f"VERDICT={'PASS' if ok else 'FAIL'}\n"
    )
    _write("probe-regenerate-silent.raw.txt", text)
    return ok, text


def probe_determinism() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="cc0013-det-") as tmp:
        tdir = Path(tmp)
        a = tdir / "a.md"
        b = tdir / "b.md"
        rc1, out1 = _run(
            [
                sys.executable,
                str(DERIVE),
                "--status",
                str(a),
            ]
        )
        rc2, out2 = _run(
            [
                sys.executable,
                str(DERIVE),
                "--status",
                str(b),
            ]
        )
        bytes_a = a.read_bytes() if a.is_file() else b""
        bytes_b = b.read_bytes() if b.is_file() else b""
        identical = bytes_a == bytes_b and len(bytes_a) > 0
        ok = rc1 == 0 and rc2 == 0 and identical
        text = (
            "PROBE=CC-0013-determinism\n"
            f"RUN1_RC={rc1}\n"
            f"RUN2_RC={rc2}\n"
            f"BYTES_A={len(bytes_a)}\n"
            f"BYTES_B={len(bytes_b)}\n"
            f"SHA256_A={hashlib.sha256(bytes_a).hexdigest()}\n"
            f"SHA256_B={hashlib.sha256(bytes_b).hexdigest()}\n"
            f"BYTE_IDENTICAL={identical}\n"
            f"VERDICT={'PASS' if ok else 'FAIL'}\n"
            f"OUT1={out1.strip()!r}\n"
            f"OUT2={out2.strip()!r}\n"
        )
        _write("probe-determinism.raw.txt", text)
        return ok, text


def probe_empty_events_not_started() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="cc0013-empty-") as tmp:
        tdir = Path(tmp)
        events = tdir / "EVENTS.jsonl"
        events.write_text("", encoding="utf-8")
        status = tdir / "STATUS.md"
        # Reuse live receipts so the empty-events control is not vacuously empty of everything.
        rc, out = _run(
            [
                sys.executable,
                str(DERIVE),
                "--events",
                str(events),
                "--receipts",
                str(RECEIPTS),
                "--status",
                str(status),
            ]
        )
        body = status.read_text(encoding="utf-8") if status.is_file() else ""
        has_not_started = "**Board status: NOT-STARTED.**" in body
        green_hits = []
        upper = body.upper()
        for token in (
            "BOARD STATUS: GREEN",
            "BOARD STATUS: COMPLETE",
            "BOARD STATUS: SUCCESS",
            "ALL-GREEN",
            "PROGRAM-GREEN",
            "PROGRAM-COMPLETE",
        ):
            if token in upper:
                green_hits.append(token)
        # Metric row must also say NOT-STARTED.
        metric_ok = "| board_status | NOT-STARTED |" in body
        event_zero = "| event_records | 0 |" in body
        ok = (
            rc == 0
            and has_not_started
            and metric_ok
            and event_zero
            and not green_hits
        )
        text = (
            "PROBE=CC-0013-empty-events\n"
            f"DERIVE_RC={rc}\n"
            f"HAS_NOT_STARTED_HEADLINE={has_not_started}\n"
            f"METRIC_BOARD_STATUS_NOT_STARTED={metric_ok}\n"
            f"EVENT_RECORDS_ZERO={event_zero}\n"
            f"GREEN_HITS={green_hits}\n"
            f"STATUS_BYTES={len(body.encode())}\n"
            f"STATUS_SHA256={hashlib.sha256(body.encode()).hexdigest()}\n"
            f"VERDICT={'PASS' if ok else 'FAIL'}\n"
            f"DERIVE_OUT={out.strip()!r}\n"
            "STATUS_BEGIN\n"
            f"{body}"
            "STATUS_END\n"
        )
        _write("probe-empty-events.raw.txt", text)
        return ok, text


def main() -> int:
    results: list[tuple[str, bool, str]] = []
    for name, fn in (
        ("hand-edit-names-line", probe_hand_edit_names_line),
        ("regenerate-silent", probe_regenerate_silent),
        ("determinism-byte-identical", probe_determinism),
        ("empty-events-not-started", probe_empty_events_not_started),
    ):
        ok, text = fn()
        results.append((name, ok, text))
        print(f"CONTROL {name}: {'PASS' if ok else 'FAIL'}")

    summary_lines = ["CC-0013 CONTROL SUMMARY"]
    all_ok = True
    for name, ok, _ in results:
        summary_lines.append(f"{name}={'PASS' if ok else 'FAIL'}")
        all_ok = all_ok and ok
    summary_lines.append(f"ALL_PASS={all_ok}")
    summary_lines.append(
        "SUCCESS:CC-0013-controls" if all_ok else "FAILED:CC-0013-controls"
    )
    summary = "\n".join(summary_lines) + "\n"
    _write("controls-summary.raw.txt", summary)
    print(summary, end="")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
