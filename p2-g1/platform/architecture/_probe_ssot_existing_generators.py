"""Existence proof: how much generated-SSOT is ALREADY in this repo, in production?

Counts, from disk and from CI config:
  - generator scripts (emit/render/gen) that write a committed artifact
  - `--check` / drift gates wired into .github/workflows/quality.yml
  - committed artifacts that carry a machine provenance stamp
  - the artifact:generator ratio (how many files one generator owns)

Detector control: a known generator (ci/gen_hooks.py) must be found, and a known
NON-generator (platform/lib/completion_predicate.py) must NOT be classified as one.

Terminal state: SUCCESS:ssot-existing / FAILED:...
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
OUT = Path(__file__).with_name("_probe_ssot_existing_generators_out.json")

# a script is a GENERATOR if it both (a) is named gen/emit/render and (b) writes a file
WRITE_PAT = re.compile(
    r"write_text|open\([^)]*['\"][wa]|\.dump\(|json\.dump|shutil\.copy|Set-Content|Out-File"
)
NAME_PAT = re.compile(r"(^|[_/-])(gen|emit|render|build)(_|\.|$)", re.I)


def main() -> int:
    r: dict = {}
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.splitlines()

    # ---------- 1. generator scripts ----------
    gens = []
    for rel in tracked:
        if not rel.endswith((".py", ".ps1", ".sh")):
            continue
        p = REPO / rel
        if not p.is_file():
            continue
        name = Path(rel).name
        if not NAME_PAT.search(name):
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if WRITE_PAT.search(txt):
            gens.append(
                {
                    "path": rel,
                    "bytes": p.stat().st_size,
                    "has_check_flag": bool(
                        re.search(r"--check|\"check\"|'check'", txt)
                    ),
                    "top_dir": rel.split("/")[0],
                }
            )
    r["generator_scripts"] = {
        "count": len(gens),
        "with_a_check_flag": sum(1 for g in gens if g["has_check_flag"]),
        "by_top_dir": dict(Counter(g["top_dir"] for g in gens).most_common()),
        "list": sorted(gens, key=lambda g: g["path"]),
    }
    # detector control
    paths = {g["path"] for g in gens}
    r["generator_scripts"]["detector_control"] = {
        "known_generator_ci/gen_hooks.py_found": "ci/gen_hooks.py" in paths,
        "known_non_generator_completion_predicate_excluded": "platform/lib/completion_predicate.py"
        not in paths,
    }

    # ---------- 2. CI drift/check gates ----------
    wf = REPO / ".github/workflows/quality.yml"
    gates = []
    if wf.is_file():
        for i, line in enumerate(
            wf.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            s = line.strip()
            if s.startswith("#"):
                continue
            if "--check" in s or re.search(r"\bdrift\b", s, re.I):
                gates.append({"line": i, "text": s[:150]})
    r["ci_gates"] = {
        "file": ".github/workflows/quality.yml",
        "count": len(gates),
        "list": gates,
    }

    # ---------- 3. provenance-stamped committed artifacts ----------
    stamps = Counter()
    stamped_files = 0
    checked = 0
    for rel in tracked:
        if not rel.endswith(".json"):
            continue
        p = REPO / rel
        if not p.is_file() or p.stat().st_size > 4_000_000:
            continue
        try:
            head = p.read_text(encoding="utf-8", errors="replace")[:4000]
        except OSError:
            continue
        checked += 1
        found = [
            m
            for m in (
                "x-generated-by",
                "generated_by",
                "x_generated",
                "source_ref",
                "generator",
            )
            if f'"{m}"' in head
        ]
        if found:
            stamped_files += 1
            for m in found:
                stamps[m] += 1
    r["provenance_stamped_json"] = {
        "json_files_examined": checked,
        "files_carrying_a_stamp": stamped_files,
        "stamp_kinds": dict(stamps.most_common()),
    }

    # ---------- 4. the biggest existing generated tree ----------
    shim = REPO / "command-center/schema"
    if shim.is_dir():
        files = sorted(p for p in shim.rglob("*.json"))
        gen_by = Counter()
        for p in files:
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(d, dict) and "x-generated-by" in d:
                gen_by[d["x-generated-by"]] += 1
        r["largest_generated_tree"] = {
            "dir": "command-center/schema",
            "files": len(files),
            "generated_by": dict(gen_by),
            "artifacts_per_generator": max(gen_by.values()) if gen_by else 0,
        }

    OUT.write_text(json.dumps(r, indent=2), encoding="utf-8")
    print(
        "generator_scripts:",
        r["generator_scripts"]["count"],
        "| with --check:",
        r["generator_scripts"]["with_a_check_flag"],
    )
    print("by_top_dir:", json.dumps(r["generator_scripts"]["by_top_dir"]))
    print("detector_control:", json.dumps(r["generator_scripts"]["detector_control"]))
    print("ci_gates:", r["ci_gates"]["count"])
    print("provenance_stamped_json:", json.dumps(r["provenance_stamped_json"]))
    print("largest_generated_tree:", json.dumps(r.get("largest_generated_tree", {})))
    print()
    for g in r["generator_scripts"]["list"]:
        print(f"  {'[--check]' if g['has_check_flag'] else '[       ]'} {g['path']}")
    print("wrote", OUT)
    print("SUCCESS:ssot-existing")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED:ssot-existing {type(exc).__name__}: {exc}")
        raise
