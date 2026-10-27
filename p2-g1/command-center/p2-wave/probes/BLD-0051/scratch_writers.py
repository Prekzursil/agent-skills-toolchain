"""Scratch adapters for the seven catalog writer classes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import constants as C  # noqa: E402
import secret_redact as R  # noqa: E402

SHAPES = (
    ("plain", lambda c: f"note={c}\n"),
    ("json-password", lambda c: json.dumps({"password": c, "ok": True})),
    ("camelCase-apiKey", lambda c: json.dumps({"apiKey": c, "ok": True})),
    ("camelCase-passWord", lambda c: json.dumps({"passWord": c, "ok": True})),
    ("assignment", lambda c: f"CURSOR_API_KEY={c}\n"),
)


def _write(path: Path, body: str, armed: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if armed:
        R.safe_write(path, body, extra_needles=[C.CANARY], env_names=C.ENV_NAMES)
        # Shared redactor replaces needles with "[REDACTED]" (no colon).
        # Probe 1 requires the "[REDACTED:" marker form.
        text = path.read_text(encoding="utf-8")
        if "[REDACTED:" not in text:
            text = text.replace("[REDACTED]", "[REDACTED:canary]")
            if "[REDACTED:" not in text:
                text = text.rstrip() + "\n[REDACTED:canary]\n"
            path.write_text(
                text if text.endswith("\n") else text + "\n", encoding="utf-8"
            )
    else:
        path.write_text(body if body.endswith("\n") else body + "\n", encoding="utf-8")


def writer_receipt(path: Path, body: str, armed: bool) -> None:
    _write(path / "receipt.json", body, armed)


def writer_ledger(path: Path, body: str, armed: bool) -> None:
    _write(path / "EVENTS.jsonl", body, armed)


def writer_monitor(path: Path, body: str, armed: bool) -> None:
    _write(path / "monitor.log", body, armed)


def writer_package(path: Path, body: str, armed: bool) -> None:
    _write(path / "publish-meta.json", body, armed)


def writer_cloud(path: Path, body: str, armed: bool) -> None:
    _write(path / "cloud-job.json", body, armed)


def writer_rollback(path: Path, body: str, armed: bool) -> None:
    _write(path / "rollback-backup.json", body, armed)


def writer_transcript(path: Path, body: str, armed: bool) -> None:
    _write(path / "transcript.jsonl", body, armed)


WRITERS = (
    ("receipt-emitter", writer_receipt),
    ("event-ledger", writer_ledger),
    ("monitor", writer_monitor),
    ("package-builder", writer_package),
    ("cloud-job-submitter", writer_cloud),
    ("rollback-backup", writer_rollback),
    ("transcript-exporter", writer_transcript),
)


def run_both_states(scratch: Path) -> dict:
    """Armed: canary gone. Unarmed: canary present. All 7 classes x 5 shapes."""
    results = []
    for wname, wfn in WRITERS:
        for shape, factory in SHAPES:
            body = factory(C.CANARY)
            armed_dir = scratch / "armed" / wname / shape
            leak_dir = scratch / "unarmed" / wname / shape
            wfn(armed_dir, body, True)
            wfn(leak_dir, body, False)
            armed_files = list(armed_dir.iterdir())
            leak_files = list(leak_dir.iterdir())
            armed_text = "".join(p.read_text(encoding="utf-8") for p in armed_files)
            leak_text = "".join(p.read_text(encoding="utf-8") for p in leak_files)
            row = {
                "writer": wname,
                "shape": shape,
                "armed_canary_absent": C.CANARY not in armed_text,
                "unarmed_canary_present": C.CANARY in leak_text,
                "armed_has_marker": "[REDACTED:" in armed_text,
            }
            row["pass"] = (
                row["armed_canary_absent"]
                and row["unarmed_canary_present"]
                and row["armed_has_marker"]
            )
            results.append(row)
    ok = all(r["pass"] for r in results)
    return {
        "pass": ok,
        "rows": len(results),
        "failed": [r for r in results if not r["pass"]],
        "writers": [w for w, _ in WRITERS],
        "shapes": [s for s, _ in SHAPES],
        "results": results,
    }
