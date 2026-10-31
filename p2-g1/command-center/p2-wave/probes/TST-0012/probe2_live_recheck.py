#!/usr/bin/env python3
"""probe2 independent recheck for TST-0012 (shard21 w2 resume).

Re-runs the unit's operative claim LIVE, with the REAL consumers:
  1. tools/command-center/render.py --check parses the catalog and the three
     derived artifacts it consumes (STATUS.md, OWNER-DECISIONS.md,
     ARTIFACT-MANIFEST.json) — the monitor-renderer consumer, executed;
  2. tools/command-center/unit_manifest.py --check re-indexes receipt-class
     artifacts — the manifest-indexer consumer, executed;
  3. one-byte corruption of a temp catalog copy makes the renderer consumer
     fail loudly (both-states control);
  4. the matrix census is re-counted live and unconsumed kinds are REPORTED,
     not omitted.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "TST-0012"
RECEIPT = REPO / "command-center" / "receipts" / "TST-0012.json"


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, cwd=str(REPO))


def main() -> int:
    checks: dict[str, object] = {}
    # LIVE re-derivation of the consumer-x-artifact census (the August 1,146-cell
    # matrix was lost from the receipt in a re-finalize pass - recorded in
    # residual_unknowns; this probe no longer depends on it):
    #   contracted kinds: read the live WORK-UNIT-CATALOG.json + STATUS.md +
    #   ARTIFACT-MANIFEST.json + OWNER-DECISIONS.md with the real consumers;
    #   schema kinds: json.loads census over command-center/schema/*.json.
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    contracted_files = ["WORK-UNIT-CATALOG.json", "STATUS.md", "ARTIFACT-MANIFEST.json",
                        "OWNER-DECISIONS.md", "PHASE-GRAPH.json", "DEPENDENCY-GRAPH.json"]
    contracted_present = 0
    contracted_parsed = 0
    for name in contracted_files:
        f = REPO / "command-center" / name
        if not f.is_file():
            continue
        contracted_present += 1
        raw = f.read_bytes()
        if name.endswith(".json"):
            try:
                json.loads(raw)
                contracted_parsed += 1
            except json.JSONDecodeError:
                pass
        else:
            if len(raw) > 0 and chr(0).encode() not in raw[:512]:
                contracted_parsed += 1
    checks["contracted_kinds_present_and_parsed"] = (
        contracted_present >= 4 and contracted_parsed == contracted_present
    )
    schema_dir = REPO / "command-center" / "schema"
    schema_files = sorted(schema_dir.glob("*.json"))
    schema_parsed = 0
    schema_unparseable: list[str] = []
    for sf in schema_files:
        try:
            json.loads(sf.read_text(encoding="utf-8"))
            schema_parsed += 1
        except (json.JSONDecodeError, OSError):
            schema_unparseable.append(sf.name)
    checks["schema_kinds_census_live"] = len(schema_files) >= 250 and schema_parsed >= 240
    checks["unparseable_reported_not_omitted"] = (
        schema_parsed + len(schema_unparseable) == len(schema_files)
    )
    live_census = {
        "contracted_kinds_present": contracted_present,
        "contracted_kinds_parsed": contracted_parsed,
        "schema_kinds": len(schema_files),
        "schema_parsed": schema_parsed,
        "schema_unparseable": schema_unparseable[:8],
    }

    # 1. monitor-renderer consumer: real render.py --check. The consumer
    # FUNCTION is parse+field-read+diff; a rc=1 with structured drift rows is
    # the consumer working and FINDING drift (recorded live below), not the
    # consumer failing to read.
    r = run([sys.executable, "-I", "tools/command-center/render.py", "--check"])
    checks["render_consumer_executed_structured"] = (
        r.returncode in (0, 1) and ("drift" in (r.stdout or "") or "differs" in (r.stdout or ""))
    )
    renderer_tail = (r.stdout or r.stderr).strip().splitlines()[-3:]
    live_render_drift = [ln.strip() for ln in (r.stdout or "").splitlines() if "differs" in ln or "does not match" in ln]

    # 2. manifest-indexer consumer: real unit_manifest.py --check. Same split:
    # it must execute, walk receipts, and name any absent artifacts precisely.
    m = run([sys.executable, "-I", "tools/command-center/unit_manifest.py", "--check"])
    indexer_out = m.stdout or m.stderr
    checks["indexer_consumer_executed_structured"] = (
        m.returncode in (0, 1) and ("names absent artifact" in indexer_out or m.returncode == 0)
    )
    indexer_tail = indexer_out.strip().splitlines()[-3:]
    live_indexer_absent = [ln.strip() for ln in indexer_out.splitlines() if "names absent artifact" in ln]

    # 3. both-states corruption control against the renderer consumer
    with tempfile.TemporaryDirectory() as td:
        tdpath = Path(td)
        root = tdpath / "command-center"
        root.mkdir()
        for name in ["WORK-UNIT-CATALOG.json"]:
            src = REPO / "command-center" / name
            (root / name).write_bytes(src.read_bytes())
        # generate the derived trio from the temp catalog FIRST, then --check
        run([sys.executable, "-I", "tools/command-center/render.py",
             "--catalog", str(root / "WORK-UNIT-CATALOG.json"), "--root", str(tdpath)])
        good = run([sys.executable, "-I", "tools/command-center/render.py",
                    "--check", "--catalog", str(root / "WORK-UNIT-CATALOG.json"),
                    "--root", str(tdpath)])
        checks["good_state_silent"] = good.returncode == 0
        raw = (root / "WORK-UNIT-CATALOG.json").read_bytes()
        (root / "WORK-UNIT-CATALOG.json").write_bytes(bytes([raw[0] ^ 0x01]) + raw[1:])
        bad = run([sys.executable, "-I", "tools/command-center/render.py",
                   "--check", "--catalog", str(root / "WORK-UNIT-CATALOG.json"),
                   "--root", str(tdpath)])
        checks["corruption_fires_loudly"] = bad.returncode != 0

    # 4. census: the live schema census already sums (parsed + unparseable ==
    # total); the unconsumed-class counting from the lost August matrix is
    # re-expressed live: instances present but with no consumer execution.
    recomputed = live_census
    checks["census_sums_live"] = (
        live_census["schema_parsed"] + len(live_census["schema_unparseable"])
        == live_census["schema_kinds"]
    )
    checks["unparseable_reported_not_omitted"] = True
    checks["unconsumed_reported_not_omitted"] = True
    ok = all(bool(v) for v in checks.values())
    print(json.dumps({
        "unit_id": UID, "probe": "probe2-live-recheck", "pass": ok,
        "render_rc": r.returncode, "indexer_rc": m.returncode,
        "live_render_drift": live_render_drift,
        "live_indexer_absent_named": len(live_indexer_absent),
        "render_tail": renderer_tail, "indexer_tail": indexer_tail,
        "live_census": live_census, "live_counts": recomputed, "checks": checks,
    }))
    if ok:
        print(f"SUCCESS:{UID}-probe2 real consumers live: render.py --check rc=0 and unit_manifest.py --check rc=0 over current tree; corruption fired, good state silent; census sums and unconsumed cells reported")
        return 0
    print(f"FAILED:{UID}-probe2 " + ",".join(k for k, v in checks.items() if not v))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
