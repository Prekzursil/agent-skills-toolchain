#!/usr/bin/env python3
"""Cross-process regression for event-ledger append serialization."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
WRITERS = 24


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ledger-concurrent-") as temp:
        root = Path(temp) / "ledger"
        project = Path(temp) / "project"
        project.mkdir()
        env = dict(os.environ, EVENT_LEDGER_ROOT=str(root), PYTHONUTF8="1")
        code = (
            "import sys;"
            f"sys.path.insert(0,{str(HERE)!r});"
            "import ledger;"
            f"ledger.append({str(project)!r},'selection',event_id=sys.argv[1])"
        )
        children = [
            subprocess.Popen(
                [sys.executable, "-c", code, f"event-{index}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            for index in range(WRITERS)
        ]
        failures: list[str] = []
        for index, child in enumerate(children):
            try:
                stdout, stderr = child.communicate(timeout=20)
            except subprocess.TimeoutExpired:
                child.kill()
                stdout, stderr = child.communicate()
                failures.append(f"writer {index} timed out")
                continue
            if child.returncode != 0:
                failures.append(
                    f"writer {index} rc={child.returncode} stdout={stdout!r} stderr={stderr!r}"
                )
        assert not failures, "\n".join(failures)

        event_files = list(root.glob("*/events.jsonl"))
        assert len(event_files) == 1, f"expected one project shard, got {event_files}"
        events = [
            json.loads(line)
            for line in event_files[0].read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(events) == WRITERS
        assert sorted(event["seq"] for event in events) == list(range(1, WRITERS + 1))
        assert {event["kind"] for event in events} == {"selection"}
        assert len({event["event_id"] for event in events}) == WRITERS
        state = json.loads(
            event_files[0].with_name("state.json").read_text(encoding="utf-8")
        )
        assert state["seq"] == WRITERS

        # Simulate a process dying after the authoritative event append but before its
        # state projection update. The next writer must recover from the JSONL tail.
        state["seq"] = 1
        event_files[0].with_name("state.json").write_text(
            json.dumps(state), encoding="utf-8"
        )
        recovered = subprocess.run(
            [sys.executable, "-c", code, "event-recovery"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=20,
        )
        assert recovered.returncode == 0, recovered.stderr
        last_event = json.loads(
            event_files[0].read_text(encoding="utf-8").splitlines()[-1]
        )
        assert last_event["seq"] == WRITERS + 1
        recovered_state = json.loads(
            event_files[0].with_name("state.json").read_text(encoding="utf-8")
        )
        assert recovered_state["seq"] == WRITERS + 1
        assert not list(root.rglob("*.tmp")), "atomic projection temp file leaked"
    print(
        f"SUCCESS:event-ledger-concurrency {WRITERS}/{WRITERS} unique monotonic "
        "appends + stale-projection recovery"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAILED:event-ledger-concurrency {exc}", file=sys.stderr)
        raise SystemExit(1)
