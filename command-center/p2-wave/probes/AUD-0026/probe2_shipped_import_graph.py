#!/usr/bin/env python3
"""AUD-0026 NAMED PROBE 2: import graph of shippable modules vs declared-dev-only deps.

A declared development dependency that a shipped module imports is a packaging
defect the declaration hides. Catalog control: a shipped fixture module importing
a dev-only package must be flagged; a test-only import of the same package must
NOT be flagged.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from split_lib import (
    discover_manifests,
    find_defects,
    find_test_imports_of_dev,
    is_other_probe_scratch,
    is_our_fixture,
    iter_shipped_modules,
    parse_manifest,
    rel,
)

PROBE = Path(__file__).resolve().parent
OUT_JSON = PROBE / "probe2-shipped-import-graph.json"
OUT_RAW = PROBE / "probe2-shipped-import-graph.raw.txt"
P1 = PROBE / "probe1-declared-split.json"

CATALOG_VERBATIM = (
    "Probe 2: the IMPORT graph of shippable modules only - a declared dev "
    "dependency that a shipped module imports is a packaging defect that the "
    "declaration hides."
)


def main() -> int:
    if not P1.is_file():
        print("FAIL: probe1 output missing; run probe1 first", file=sys.stderr)
        return 2

    rows = []
    for path in discover_manifests():
        rpath = rel(path)
        if is_other_probe_scratch(rpath):
            continue
        rec = parse_manifest(path)
        if rec is None or rec.get("error"):
            continue
        rec["planted_fixture"] = is_our_fixture(rpath)
        rows.append(rec)

    live_rows = [r for r in rows if not r["planted_fixture"]]
    planted_rows = [r for r in rows if r["planted_fixture"]]

    live_defects: list[dict] = []
    for r in live_rows:
        live_defects.extend(find_defects(r))

    planted_defects: list[dict] = []
    planted_test_hits: list[dict] = []
    for r in planted_rows:
        planted_defects.extend(find_defects(r))
        planted_test_hits.extend(find_test_imports_of_dev(r))

    # Control: shipped import of pytest / typescript flagged; test-only not flagged.
    py_shipped_caught = any(
        d["declared_dev_only"] == "pytest"
        and d["module"].endswith("aud0026_planted/shipped.py")
        for d in planted_defects
    )
    node_shipped_caught = any(
        d["declared_dev_only"] == "typescript"
        and "/src/shipped.mjs" in d["module"].replace("\\", "/")
        for d in planted_defects
    )
    planted_shipped_caught = py_shipped_caught and node_shipped_caught

    py_test_present = any(
        t["declared_dev_only"] == "pytest" and "/tests/" in t["module"].replace("\\", "/")
        for t in planted_test_hits
    )
    node_test_present = any(
        t["declared_dev_only"] == "typescript"
        and "/test/" in t["module"].replace("\\", "/")
        for t in planted_test_hits
    )
    # Negatives: those test imports must not appear in defects
    test_only_not_flagged = (
        py_test_present
        and node_test_present
        and not any("/tests/" in d["module"].replace("\\", "/") for d in planted_defects)
        and not any(
            "/test/" in d["module"].replace("\\", "/") and d["module"].endswith(".mjs")
            for d in planted_defects
            if "planted-node" in d["module"]
        )
    )

    # dead = declared-dev-only names never imported by any shippable module (correctly dead to runtime)
    dead_dev_only = []
    for r in live_rows:
        shipped_imps: set[str] = set()
        for mod in iter_shipped_modules(r):
            if mod["shipped"]:
                shipped_imps.update(mod["imports"])
        for name in r.get("dev_only") or []:
            # compare normalized forms
            hit = False
            for imp in shipped_imps:
                if imp == name or imp.replace("_", "-") == name or imp.replace("-", "_") == name.replace("-", "_"):
                    hit = True
                    break
            if not hit:
                dead_dev_only.append(
                    {
                        "manifest": r["manifest"],
                        "package": r.get("name"),
                        "ecosystem": r["ecosystem"],
                        "declared_dev_only": name,
                    }
                )

    ok = planted_shipped_caught and test_only_not_flagged

    payload = {
        "unit": "AUD-0026",
        "catalog_verbatim": CATALOG_VERBATIM,
        "live_defect_count": len(live_defects),
        "dead_dev_only_count": len(dead_dev_only),
        "live_defects": live_defects,
        "dead_dev_only": dead_dev_only,
        "planted_defects": planted_defects,
        "planted_test_imports_of_dev": planted_test_hits,
        "planted_shipped_caught": planted_shipped_caught,
        "py_shipped_caught": py_shipped_caught,
        "node_shipped_caught": node_shipped_caught,
        "test_only_not_flagged": test_only_not_flagged,
        "py_test_present": py_test_present,
        "node_test_present": node_test_present,
        "packages_scanned": len(live_rows),
        "ok": ok,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    lines = [
        "AUD-0026 NAMED PROBE 2: shippable-module import graph vs declared-dev-only",
        f"catalog_verbatim={CATALOG_VERBATIM}",
        "unit=AUD-0026",
        f"packages_scanned={len(live_rows)}",
        f"live_defect_count={len(live_defects)}",
        f"dead_dev_only_count={len(dead_dev_only)}",
        f"planted_shipped_caught={planted_shipped_caught}",
        f"py_shipped_caught={py_shipped_caught}",
        f"node_shipped_caught={node_shipped_caught}",
        f"test_only_not_flagged={test_only_not_flagged}",
        f"py_test_present={py_test_present}",
        f"node_test_present={node_test_present}",
        "PLANTED-DEFECTS-BEGIN",
    ]
    for d in planted_defects:
        lines.append(
            f"PLANTED-DEFECT\t{d['ecosystem']}\t{d['module']}\t"
            f"import={d['import_name']}\tdev_only={d['declared_dev_only']}"
        )
    lines.append("PLANTED-DEFECTS-END")
    lines.append("PLANTED-TEST-IMPORTS-BEGIN")
    for t in planted_test_hits:
        lines.append(
            f"PLANTED-TEST\t{t['module']}\timport={t['import_name']}\t"
            f"dev_only={t['declared_dev_only']}"
        )
    lines.append("PLANTED-TEST-IMPORTS-END")
    lines.append("LIVE-DEFECTS-BEGIN")
    for d in live_defects:
        lines.append(
            f"LIVE\t{d['ecosystem']}\t{d['manifest']}\t{d['module']}\t"
            f"import={d['import_name']}\tdev_only={d['declared_dev_only']}"
        )
    lines.append("LIVE-DEFECTS-END")
    lines.append(
        "SUCCESS:AUD-0026-probe2" if ok else "FAIL:AUD-0026-probe2"
    )
    raw = "\n".join(lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    sys.stdout.write(raw)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
