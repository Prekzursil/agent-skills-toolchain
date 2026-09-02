"""Executed faults against live Codex adapter (spawn injection, not source reads)."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center"))

from adapters.codex import CodexAdapter, SpawnRecord  # noqa: E402

PYTHON = sys.executable


def _timeout_spawn(argv, timeout) -> SpawnRecord:
    try:
        subprocess.run(
            [PYTHON, "-c", "import time; time.sleep(8)"],
            timeout=min(float(timeout), 0.2),
            capture_output=True,
            check=False,
        )
        return SpawnRecord(argv=list(argv), exit_code=0, stdout="", stderr="", timed_out=False)
    except subprocess.TimeoutExpired:
        return SpawnRecord(argv=list(argv), exit_code=124, stdout="", stderr="", timed_out=True)


def _exit0_missing_spawn(argv, timeout) -> SpawnRecord:
    del timeout
    return SpawnRecord(argv=list(argv), exit_code=0, stdout="[codex] progress", stderr="")


def _dispatch(spawn) -> dict:
    adapter = CodexAdapter(spawn=spawn)
    with tempfile.TemporaryDirectory(prefix="bld0027-codex-") as tmp:
        prompt = Path(tmp) / "prompt.txt"
        prompt.write_text("BLD-0027 live adapter fault\n", encoding="utf-8")
        unit = {"id": "BLD-0027-live", "timeout_seconds": 0.2, "prompt": "BLD-0027 live adapter fault"}
        return adapter.dispatch(unit, prompt=prompt.read_text(encoding="utf-8"))


def run_live_adapter_faults() -> dict:
    timeout_doc = _dispatch(_timeout_spawn)
    missing_doc = _dispatch(_exit0_missing_spawn)
    t_state = str(timeout_doc.get("state") or "")
    m_state = str(missing_doc.get("state") or "")
    return {
        "timeout": {
            "state": t_state,
            "classification": timeout_doc.get("classification"),
            "timed_out": (timeout_doc.get("invocation") or {}).get("timed_out"),
            "is_success": t_state == "SUCCESS",
            "is_failed": t_state == "FAILED",
            "catalog_wants_failed": t_state == "FAILED",
        },
        "exit0_missing": {
            "state": m_state,
            "classification": missing_doc.get("classification"),
            "is_success": m_state == "SUCCESS",
            "is_failed": m_state == "FAILED",
            "is_severed": m_state == "SEVERED",
        },
        "timeout_not_success": t_state != "SUCCESS",
        "missing_not_success": m_state != "SUCCESS",
    }


def main() -> int:
    doc = run_live_adapter_faults()
    print(
        "timeout_state={0} missing_state={1} timeout_not_success={2} missing_not_success={3}".format(
            doc["timeout"]["state"],
            doc["exit0_missing"]["state"],
            doc["timeout_not_success"],
            doc["missing_not_success"],
        )
    )
    if not doc["timeout_not_success"] or not doc["missing_not_success"]:
        print("FAILED:BLD-0027 live adapter classified as SUCCESS")
        return 1
    print("SUCCESS:BLD-0027-live-adapter timeout/missing are not SUCCESS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
