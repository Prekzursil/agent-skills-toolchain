#!/usr/bin/env python3
"""AUD-0040 NAMED PROBE 1: re-run the dep-graph generator and byte-compare.

Catalog evidence_requirement Probe 1:
  re-run the generator and byte-compare its output to the committed file.

Planted control (fixtures/planted_pair):
  build_graph(planted catalog) must byte-match the planted graph; a one-byte
  effort flip must diverge. Proves the comparator can go RED.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT_JSON = PROBE / "probe1-generator-byte-compare.json"
OUT_RAW = PROBE / "probe1-generator-byte-compare.raw.txt"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
GRAPH = REPO / "command-center/DEPENDENCY-GRAPH.json"
PLANTED_CAT = PROBE / "fixtures/planted_pair/catalog.json"
PLANTED_GRAPH = PROBE / "fixtures/planted_pair/DEPENDENCY-GRAPH.json"

sys.path.insert(0, str(REPO / "tools/command-center"))
import catalog as cat  # noqa: E402


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


lines: list[str] = []


def log(msg: str) -> None:
    lines.append(msg)
    print(msg)


def ensure_planted_graph() -> dict:
    """Derive and write planted graph so the fixture stays generator-honest."""
    planted_catalog = cat.load(PLANTED_CAT)
    g = cat.build_graph(planted_catalog)
    cat.save(g, PLANTED_GRAPH)
    return g


def planted_control() -> dict:
    ensure_planted_graph()
    planted_catalog = cat.load(PLANTED_CAT)
    good_bytes = PLANTED_GRAPH.read_bytes()
    with tempfile.TemporaryDirectory(prefix="aud0040-p1-planted-") as td:
        tmp = Path(td)
        regen_path = tmp / "DEPENDENCY-GRAPH.json"
        cat.save(cat.build_graph(planted_catalog), regen_path)
        regen_bytes = regen_path.read_bytes()
        good_equal = regen_bytes == good_bytes

        mutated = json.loads(json.dumps(planted_catalog))
        item = next(i for i in mutated["items"] if i.get("effort"))
        old = item["effort"]
        item["effort"] = ("Z" if old[:1] != "Z" else "Y") + old[1:]
        mut_path = tmp / "mut-DEPENDENCY-GRAPH.json"
        cat.save(cat.build_graph(mutated), mut_path)
        mut_bytes = mut_path.read_bytes()
        bad_diverges = mut_bytes != good_bytes

    ok = good_equal and bad_diverges
    log(
        f"PLANTED_CONTROL good_equal={good_equal} bad_diverges={bad_diverges} "
        f"good_sha={sha256_bytes(good_bytes)[:16]} "
        f"mut_sha={sha256_bytes(mut_bytes)[:16]} ok={ok}"
    )
    return {
        "ok": ok,
        "good_equal": good_equal,
        "bad_diverges": bad_diverges,
        "good_sha256": sha256_bytes(good_bytes),
        "mutated_sha256": sha256_bytes(mut_bytes),
        "effort_before": old,
        "effort_after": item["effort"],
        "description": (
            "Planted pair must byte-match after regeneration; one-byte effort "
            "mutation must diverge."
        ),
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    log("AUD-0040 PROBE1 generator byte-compare")
    log(f"REPO={REPO}")
    log(f"CATALOG={CATALOG} exists={CATALOG.is_file()} bytes={CATALOG.stat().st_size if CATALOG.is_file() else -1}")
    log(f"GRAPH={GRAPH} exists={GRAPH.is_file()} bytes={GRAPH.stat().st_size if GRAPH.is_file() else -1}")

    if not CATALOG.is_file() or not GRAPH.is_file():
        log("FAILED: missing catalog or graph")
        payload = {
            "ok": False,
            "unit_id": "AUD-0040",
            "probe": 1,
            "error": "missing-inputs",
            "started_at": started,
            "ended_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        OUT_RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 1

    catalog = cat.load(CATALOG)
    committed = GRAPH.read_bytes()
    committed_sha = sha256_bytes(committed)
    committed_obj = json.loads(committed.decode("utf-8"))

    with tempfile.TemporaryDirectory(prefix="aud0040-p1-regen-") as td:
        tmp = Path(td)
        regen_path = tmp / "DEPENDENCY-GRAPH.json"
        generated = cat.build_graph(catalog)
        cat.save(generated, regen_path)
        regen_bytes = regen_path.read_bytes()
        regen_sha = sha256_bytes(regen_bytes)

    byte_equal = regen_bytes == committed
    json_equal = generated == committed_obj
    log(f"COMMITTED_SHA256={committed_sha}")
    log(f"REGENERATED_SHA256={regen_sha}")
    log(f"BYTE_EQUAL={byte_equal}")
    log(f"JSON_EQUAL={json_equal}")
    log(
        f"NODE_COUNT committed={committed_obj.get('node_count')} "
        f"generated={generated.get('node_count')}"
    )
    log(
        f"EDGE_COUNT committed={committed_obj.get('edge_count')} "
        f"generated={generated.get('edge_count')}"
    )
    log(f"ACYCLIC committed={committed_obj.get('acyclic')} generated={generated.get('acyclic')}")
    log(f"DERIVATION={generated.get('derivation')}")

    control = planted_control()
    ok = byte_equal and json_equal and control["ok"]
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    log(f"PROBE1_OK={ok}")

    payload = {
        "ok": ok,
        "unit_id": "AUD-0040",
        "probe": 1,
        "name": "generator-byte-compare",
        "generator": "tools/command-center/catalog.py:build_graph + catalog.save",
        "catalog_path": "command-center/WORK-UNIT-CATALOG.json",
        "graph_path": "command-center/DEPENDENCY-GRAPH.json",
        "committed_bytes": len(committed),
        "regenerated_bytes": len(regen_bytes),
        "committed_sha256": committed_sha,
        "regenerated_sha256": regen_sha,
        "byte_equal": byte_equal,
        "json_equal": json_equal,
        "node_count": generated.get("node_count"),
        "edge_count": generated.get("edge_count"),
        "acyclic": generated.get("acyclic"),
        "control": control,
        "started_at": started,
        "ended_at": ended,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    OUT_RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
