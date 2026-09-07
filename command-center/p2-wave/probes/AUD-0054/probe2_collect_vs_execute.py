#!/usr/bin/env python3
"""AUD-0054 Probe 2: real collected-vs-executed node-ID diff on this Linux host.

Catalog evidence_requirement Probe 2:
  a diff of collected-versus-executed node IDs from a real run on each available
  platform (this cloud host is Linux) -- catches runtime skips that no decorator
  declares.

"Each available platform" is honestly ONE here: this execution substrate is Linux.
Windows and macOS cells are NOT-RUN-HERE and reported as residual_unknowns rather
than invented. What IS real: every file this probe touches is actually collected and
actually executed with a real ``pytest`` subprocess on this host, and the resulting
SKIPPED/PASSED/FAILED outcome per node id is parsed from that real run's output --
not reasoned about from the source.

Scope: the files probe 1 found to contain a decorator-declared platform skip, PLUS
two runtime-only candidates that carry NO decorator (the hermetic fixture built for
this unit, and one real production test discovered by grep for platform-conditioned
`pytest.skip()`/`raise ...SkipTest` calls in test bodies). The second category is
exactly what the catalog's independence control needs: something Probe 1 structurally
cannot see because it only walks decorator lists.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT_JSON = PROBE / "probe2-collect-vs-execute.json"
OUT_RAW = PROBE / "probe2-collect-vs-execute.raw.txt"

# Files carrying a decorator-declared platform skipif (from probe1's own findings) --
# kept as a literal list here (not re-imported from probe1's JSON) so this probe can
# run standalone and its own file selection is auditable independently of probe1's
# code.
DECORATOR_DECLARED_FILES = [
    "hooks/file-scope/test_file_scope.py",
    "hooks/precompact-snapshot/test_snapshot.py",
    "platform/coordination/test_leases.py",
]

# Runtime-only platform skips: no pytest.mark.skipif/skip/xfail decorator anywhere on
# the gated test, only a body-level `pytest.skip()` / `raise ...SkipTest` guarded by a
# platform predicate. Probe 1 is structurally blind to these by construction.
RUNTIME_ONLY_FILES = [
    "command-center/p2-wave/probes/AUD-0054/fixtures/test_control_runtime_only_skip.py",
    "tools/agentrail/tests/test_deploy.py",
]

ALL_FILES = DECORATOR_DECLARED_FILES + RUNTIME_ONLY_FILES

VERBOSE_LINE_RE = re.compile(
    r"^(?P<nodeid>\S+::\S+)\s+(?P<outcome>PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS)\b(?:\s+\((?P<reason>.*)\))?"
)


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 180) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd,
            cwd=str(cwd or REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s: {' '.join(cmd)}"
    except OSError as e:
        return 127, f"{type(e).__name__}: {e}"


def collect_ids(rel_path: str) -> tuple[list[str], str]:
    rc, out = run([sys.executable, "-m", "pytest", "--collect-only", "-q", rel_path])
    ids = []
    for line in out.splitlines():
        s = line.strip()
        if "::" in s and not s.startswith("=") and "error" not in s.lower():
            ids.append(s)
    return ids, out


LIVE_MARKER_FLAG_FILES = {
    # This file's runtime platform skip lives INSIDE a body gated on the opt-in
    # `@pytest.mark.live` conftest hook (tools/agentrail/tests/conftest.py adds a
    # SEPARATE, unrelated `skip(reason="deselected: ...")` marker at collection time
    # unless --run-live is passed). Without the flag, that marker-skip fires FIRST and
    # the platform check inside the body is never reached -- measured directly:
    # without --run-live the recorded skip reason is "deselected: live-marked tests
    # need a real agent rail", not the platform reason. --run-live is required to
    # observe the actual runtime platform gate this probe is auditing.
    "tools/agentrail/tests/test_deploy.py": ["--run-live"],
}


def execute_verbose(rel_path: str) -> tuple[dict[str, dict], str, int]:
    extra = LIVE_MARKER_FLAG_FILES.get(rel_path, [])
    rc, out = run(
        [sys.executable, "-m", "pytest", "-v", "--tb=short", "-rs", rel_path, *extra]
    )
    outcomes: dict[str, dict] = {}
    for line in out.splitlines():
        m = VERBOSE_LINE_RE.match(line.strip())
        if m:
            outcomes[m.group("nodeid")] = {
                "outcome": m.group("outcome"),
                "reason": m.group("reason"),
            }
    # Also parse the `-rs` short skip summary for reasons, since -v lines sometimes
    # truncate long reasons.
    in_skip_section = False
    for line in out.splitlines():
        if line.startswith("=") and "short test summary" in line.lower():
            in_skip_section = True
            continue
        if in_skip_section and line.startswith("SKIPPED"):
            mm = re.match(r"SKIPPED \[\d+\] (\S+):\d+: (.*)", line)
            if mm:
                nodeid_prefix = mm.group(1)
                for nid in list(outcomes):
                    if nid.startswith(nodeid_prefix):
                        outcomes[nid]["reason"] = mm.group(2)
    return outcomes, out, rc


def declared_by_probe1(rel_path: str, test_name: str, probe1_rows: list[dict]) -> bool:
    return any(r["path"] == rel_path and r["target"] == test_name for r in probe1_rows)


def main() -> int:
    p1_path = PROBE / "probe1-ast-platform-skips.json"
    probe1_rows: list[dict] = []
    if p1_path.is_file():
        probe1_rows = json.loads(p1_path.read_text(encoding="utf-8")).get("rows", [])

    raw: list[str] = ["unit=AUD-0054 probe=2 real collect-vs-execute diff (host=linux)"]
    per_file: list[dict] = []
    all_skipped_rows: list[dict] = []

    for rel_path in ALL_FILES:
        target = REPO / rel_path
        if not target.is_file():
            per_file.append({"path": rel_path, "ok": False, "error": "file-missing"})
            raw.append(f"--- {rel_path}: MISSING ---")
            continue
        collected, collect_raw = collect_ids(rel_path)
        outcomes, exec_raw, rc = execute_verbose(rel_path)

        executed_ids = {nid for nid, o in outcomes.items() if o["outcome"] != "SKIPPED"}
        skipped_ids = {nid for nid, o in outcomes.items() if o["outcome"] == "SKIPPED"}
        collected_not_in_outcomes = [nid for nid in collected if nid not in outcomes]

        skip_rows = []
        for nid in sorted(skipped_ids):
            test_name = nid.split("::")[-1].split("[")[0]
            declared = declared_by_probe1(rel_path, test_name, probe1_rows)
            row = {
                "node_id": nid,
                "path": rel_path,
                "test_name": test_name,
                "reason": outcomes[nid].get("reason"),
                "declared_by_probe1": declared,
            }
            skip_rows.append(row)
            all_skipped_rows.append(row)

        per_file.append(
            {
                "path": rel_path,
                "collected_count": len(collected),
                "executed_count": len(executed_ids),
                "skipped_count": len(skipped_ids),
                "collected_not_matched_to_outcome": collected_not_in_outcomes,
                "rc": rc,
                "skip_rows": skip_rows,
                "ok": rc in (0, 1) and len(collected) > 0,
            }
        )
        raw.append(f"--- {rel_path} ---")
        raw.append(
            f"collected={len(collected)} executed={len(executed_ids)} "
            f"skipped={len(skipped_ids)} rc={rc}"
        )
        for r in skip_rows:
            raw.append(
                f"  SKIPPED {r['node_id']} declared_by_probe1={r['declared_by_probe1']} "
                f"reason={r['reason']!r}"
            )
        raw.append(exec_raw[-2500:])

    runtime_only_hits = [r for r in all_skipped_rows if not r["declared_by_probe1"]]
    declared_hits = [r for r in all_skipped_rows if r["declared_by_probe1"]]

    control_fixture_hit = any(
        r["test_name"] == "test_control_windows_only_runtime_skip_no_decorator"
        and not r["declared_by_probe1"]
        for r in all_skipped_rows
    )
    control_sibling_ran = any(
        r["test_name"] == "test_control_sibling_runs_on_every_platform" for r in all_skipped_rows
    ) is False  # sibling must NOT be in the skipped set (it must execute)

    real_world_runtime_hit = any(
        r["path"] == "tools/agentrail/tests/test_deploy.py"
        and r["test_name"] == "test_the_rendered_shim_really_propagates_a_nonzero_exit"
        and not r["declared_by_probe1"]
        for r in all_skipped_rows
    )

    control_ok = control_fixture_hit and control_sibling_ran and real_world_runtime_hit

    doc = {
        "unit": "AUD-0054",
        "probe": 2,
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "execution_substrate": "linux-cursor-cloud",
        "platforms_available_here": ["linux"],
        "platforms_not_run_here": ["windows", "macos"],
        "files": per_file,
        "total_skipped_here": len(all_skipped_rows),
        "declared_hits_count": len(declared_hits),
        "runtime_only_hits_count": len(runtime_only_hits),
        "runtime_only_hits": runtime_only_hits,
        "control": {
            "ok": control_ok,
            "fixture_runtime_skip_found_by_probe2": control_fixture_hit,
            "fixture_sibling_test_executed_not_skipped": control_sibling_ran,
            "real_world_runtime_skip_found_by_probe2": real_world_runtime_hit,
        },
        "ok": control_ok and len(all_skipped_rows) > 0,
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    raw.insert(0, "SUCCESS:AUD-0054-probe2" if doc["ok"] else "FAILED:AUD-0054-probe2")
    raw.append(
        f"total_skipped_here={len(all_skipped_rows)} declared_hits={len(declared_hits)} "
        f"runtime_only_hits={len(runtime_only_hits)} control_ok={control_ok}"
    )
    OUT_RAW.write_text("\n".join(raw) + "\n", encoding="utf-8")
    print(OUT_RAW.read_text(encoding="utf-8")[-6000:])
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
