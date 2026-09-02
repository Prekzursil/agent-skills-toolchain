#!/usr/bin/env python3
"""Probe 2: known-present control + three-column reconciliation.

A session whose on-disk start_time is 60s before probe runtime must appear.
An absent id must not. An independent glob walker (not enumerate_claude)
must recover the same session ids. Every disk/process disagreement is named.
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import discover as D  # noqa: E402
import scenario as S  # noqa: E402

ABSENT_ID = "00000000-0000-4000-8000-000000000000"


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0407-probe2 {msg}")
    return 1


def independent_claude_ids(claude_home: Path) -> set[str]:
    """Different walker: Path.glob on projects/*/*.jsonl, skip subagents."""
    ids: set[str] = set()
    projects = Path(claude_home) / "projects"
    if not projects.is_dir():
        return ids
    for jsonl in sorted(projects.glob("*/*.jsonl")):
        if "subagents" in jsonl.parts or jsonl.name.startswith("agent-"):
            continue
        found = None
        for line in jsonl.read_text(encoding="utf-8").splitlines()[:8]:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            found = rec.get("sessionId") or rec.get("session_id")
            if found:
                break
        ids.add(str(found or jsonl.stem))
    return ids


def independent_codex_ids(codex_home: Path) -> set[str]:
    ids: set[str] = set()
    threads = Path(codex_home) / "threads"
    if threads.is_dir():
        for path in threads.glob("*.json"):
            rec = json.loads(path.read_text(encoding="utf-8"))
            ids.add(str(rec.get("id") or path.stem))
    return ids


def main() -> int:
    now = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory(prefix="imp0407-p2-") as tmp:
        meta = S.build_estate(Path(tmp) / "estate", now=now)
        probe = D.ProbeContext.capture(started_at=now)
        result = D.discover(
            claude_home=Path(meta["claude_home"]),
            codex_home=Path(meta["codex_home"]),
            process_snapshot=meta["snapshot"],
            probe=probe,
            exclude_self=True,
        )
        ids = D.session_ids(result)
        claude_live = meta["known_present"]["claude"]["session_id"]
        codex_live = meta["known_present"]["codex"]["session_id"]
        if claude_live not in ids:
            return _fail(f"known-present claude {claude_live} missing from registry")
        if codex_live not in ids:
            return _fail(f"known-present codex {codex_live} missing from registry")
        if ABSENT_ID in ids:
            return _fail("absent session id was reported present")
        claude_row = next(s for s in result["sessions"] if s["session_id"] == claude_live)
        started = D.parse_time(claude_row["start_time"])
        delta = (now - started).total_seconds() if started else 0
        if delta < 50:
            return _fail(f"known-present start delta {delta}s is not ~60s")
        nested = "nested-subagent-not-a-session"
        if nested in ids:
            return _fail("subagent jsonl was counted as a session")

        walk_claude = independent_claude_ids(Path(meta["claude_home"]))
        walk_codex = independent_codex_ids(Path(meta["codex_home"]))
        disc_claude = D.session_ids(result, vendor="claude")
        disc_codex = D.session_ids(result, vendor="codex")
        if walk_claude != disc_claude:
            return _fail(f"independent claude walk {walk_claude} != discover {disc_claude}")
        if walk_codex != disc_codex:
            return _fail(f"independent codex walk {walk_codex} != discover {disc_codex}")

        recon = result["reconciliation"]
        kinds = {d["kind"] for d in recon["disagreements"]}
        if "ON_DISK_WITHOUT_PROCESS" not in kinds:
            return _fail(f"stale disk session not named: {recon['disagreements']}")
        if "PROCESS_WITHOUT_ON_DISK" not in kinds:
            return _fail(f"orphan process not named: {recon['disagreements']}")
        named_stale = any(
            meta["stale_claude"] in d.get("named", "") or meta["stale_claude"] in d.get("id", "")
            for d in recon["disagreements"]
        )
        named_orphan = any(
            str(meta["orphan_pid"]) in d.get("named", "") or str(meta["orphan_pid"]) in d.get("id", "")
            for d in recon["disagreements"]
        )
        if not named_stale:
            return _fail("stale claude session disagreement not named")
        if not named_orphan:
            return _fail("orphan process disagreement not named")
        if recon["on_disk_count"] != meta["expected_on_disk"]["total"]:
            return _fail(f"on_disk_count={recon['on_disk_count']}")
        if recon["registry_count"] != recon["on_disk_count"]:
            return _fail("registry_count != on_disk_count")
        if recon["process_table_count"] != meta["expected_process_after_exclusion"]:
            return _fail(f"process_table_count={recon['process_table_count']}")
        if int(meta["self_pid"]) in {p["pid"] for p in result["processes"]}:
            return _fail("self pid leaked into process table")

        print(
            json.dumps(
                {
                    "known_present_claude": claude_live,
                    "known_present_codex": codex_live,
                    "started_seconds_before_probe": round(delta, 3),
                    "absent_id_found": False,
                    "independent_claude_ids": sorted(walk_claude),
                    "independent_codex_ids": sorted(walk_codex),
                    "on_disk_count": recon["on_disk_count"],
                    "process_table_count": recon["process_table_count"],
                    "registry_count": recon["registry_count"],
                    "disagreement_kinds": sorted(kinds),
                    "disagreements_named": [d["named"] for d in recon["disagreements"]],
                    "subagent_excluded": True,
                },
                sort_keys=True,
            )
        )
    print("SUCCESS:IMP-0407-probe2 known-present and three-column reconciliation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
