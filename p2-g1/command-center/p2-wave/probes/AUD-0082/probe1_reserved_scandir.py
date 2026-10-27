#!/usr/bin/env python3
"""AUD-0082 probe 1 (source): path-string classifier + os.scandir walk with the
extended-length prefix. Classifies reserved device names, >260-char paths and
same-directory case collisions. Must survive a NUL entry without crashing."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = HERE / "probe1_reserved_scandir_out.json"

RESERVED = {"NUL", "CON", "AUX", "PRN"} | {
    "COM%d" % i for i in range(1, 10)} | {"LPT%d" % i for i in range(1, 10)}
SCOPES = ["command-center", "platform", "tools", "hooks", "ci", "scripts",
          "docs", "guides", "rules", "lib", "council", "plugin", "marketplace",
          "workflow_foundry", "release", "schema", "skills", "agents", "commands"]
SKIP = {"node_modules", ".git", "__pycache__"}
MAX_DIRS = 40000


def reserved_hit(name: str) -> str | None:
    base = name.split(".")[0].split(":")[0].upper()
    return base if base in RESERVED else None


def classify_list(paths: list) -> dict:
    """Pure path-string classifier (works on listings the OS refuses to stat)."""
    hazards = []
    for p in paths:
        name = p.replace("\\", "/").rsplit("/", 1)[-1]
        r = reserved_hit(name)
        if r:
            hazards.append({"kind": "reserved-name", "path": p[:300], "name": r})
        if len(p) > 260:
            hazards.append({"kind": "long-path", "path": p[:300], "length": len(p)})
    by_dir: dict = {}
    for p in paths:
        norm = p.replace("\\", "/")
        d, name = norm.rsplit("/", 1) if "/" in norm else ("", norm)
        by_dir.setdefault(d, {}).setdefault(name.lower(), []).append(name)
    for d, names in by_dir.items():
        for low, variants in names.items():
            if len(variants) > 1:
                hazards.append({"kind": "case-collision", "path": d + "/" + variants[0],
                                "variants": variants[:4]})
    return {"hazards": hazards, "counts": {
        k: sum(1 for h in hazards if h["kind"] == k)
        for k in ("reserved-name", "long-path", "case-collision")}}


def walk_scandir() -> tuple:
    all_paths = []
    errors = []
    n_dirs = 0
    prefix = chr(92) * 2 + "?" + chr(92)
    for scope in SCOPES:
        base = REPO / scope
        if not base.is_dir():
            continue
        stack = [str(base)]
        while stack and n_dirs < MAX_DIRS:
            cur = stack.pop()
            n_dirs += 1
            try:
                with __import__("os").scandir(prefix + cur) as it:
                    for entry in it:
                        p = cur + "\\" + entry.name
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                if entry.name not in SKIP:
                                    stack.append(p)
                            else:
                                all_paths.append(str(Path(p).relative_to(REPO)))
                        except OSError as exc:
                            errors.append({"path": p[:200], "err": exc.errno})
            except OSError as exc:
                errors.append({"path": cur[:200], "err": exc.errno})
    return all_paths, errors, n_dirs


def fixture_control() -> dict:
    long_name = "d" * 280 + ".txt"
    fixture_paths = [
        "fixture/NUL",
        "fixture/CON.txt",
        "fixture/" + long_name,
        "fixture/A.txt",
        "fixture/a.txt",
        "fixture/normal.md",
    ]
    res = classify_list(fixture_paths)
    ok = (res["counts"]["reserved-name"] >= 2
          and res["counts"]["long-path"] >= 1
          and res["counts"]["case-collision"] >= 1)
    return {"pass": ok, "counts": res["counts"]}


def main() -> int:
    paths, errors, n_dirs = walk_scandir()
    res = classify_list(paths)
    fixture = fixture_control()
    live_nul = REPO.parents[0] / "source" / "ast-integrate" / "NUL"
    live_nul_seen = live_nul.is_file()
    result = {
        "probe": "probe1-reserved-scandir",
        "dirs_walked": n_dirs,
        "files_indexed": len(paths),
        "walk_errors": len(errors),
        "error_sample": errors[:5],
        "hazard_counts": res["counts"],
        "hazard_sample": res["hazards"][:40],
        "fixture_control": fixture,
        "live_nul_in_source_repo": bool(live_nul_seen),
        "pass": bool(fixture["pass"] and n_dirs > 100),
    }
    OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print("dirs=%d files=%d hazards=%s errors=%d fixture=%s live_nul=%s"
          % (n_dirs, len(paths), res["counts"], len(errors), fixture["pass"], live_nul_seen))
    print("SUCCESS:AUD-0082-probe1 reserved/long/case census" if result["pass"]
          else "FAILED:AUD-0082-probe1 fixture control")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
