#!/usr/bin/env python3
"""Inventory shard-03 imports, g1-surface stubs, and harvest copies of missing probes."""
from __future__ import annotations

import ast
import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
SHARD = WAVE / "ovh-monitor" / "g1-shards" / "shard-03.txt"
IDS = [ln.strip() for ln in SHARD.read_text(encoding="utf-8").splitlines() if ln.strip()]
STDLIB = {
    "abc", "argparse", "array", "ast", "asyncio", "base64", "binascii", "builtins",
    "codecs", "collections", "contextlib", "copy", "csv", "ctypes", "dataclasses",
    "datetime", "decimal", "difflib", "email", "enum", "errno", "fnmatch", "functools",
    "glob", "gzip", "hashlib", "hmac", "html", "http", "importlib", "inspect", "io",
    "itertools", "json", "keyword", "locale", "logging", "math", "mimetypes", "mmap",
    "multiprocessing", "numbers", "operator", "os", "pathlib", "pickle", "pkgutil",
    "platform", "pprint", "queue", "random", "re", "reprlib", "secrets", "shlex",
    "shutil", "signal", "socket", "sqlite3", "ssl", "stat", "string", "struct",
    "subprocess", "sys", "tarfile", "tempfile", "textwrap", "threading", "time",
    "tokenize", "traceback", "types", "typing", "unicodedata", "unittest", "urllib",
    "uuid", "warnings", "weakref", "xml", "zipfile", "zlib", "__future__",
}

HARVEST_PROBE_ROOTS = []
mon = WAVE / "ovh-monitor"
for kind in ("error-pull", "delivery-pull", "missing-pull"):
    root = mon / kind
    if not root.is_dir():
        continue
    for box in root.iterdir():
        if not box.is_dir():
            continue
        for sub in (
            box / "extracted" / "probes",
            box / "extracted-delta" / "probes",
            box / "delta" / "command-center" / "p2-wave" / "probes",
            box / "tree" / "command-center" / "p2-wave" / "probes",
        ):
            if sub.is_dir():
                HARVEST_PROBE_ROOTS.append(sub)
        # error-pull/extracted/<box>/probes
        for nested in ("extracted", "extracted-delta"):
            nest = box / nested
            if nest.is_dir():
                # extracted/gra7-a/probes
                pass
        if (box / "probes").is_dir():
            HARVEST_PROBE_ROOTS.append(box / "probes")

# error-pull/extracted/<box>/probes
ep = mon / "error-pull"
if ep.is_dir():
    for nested in ("extracted", "extracted-delta"):
        n = ep / nested
        if not n.is_dir():
            continue
        for box in n.iterdir():
            p = box / "probes"
            if p.is_dir():
                HARVEST_PROBE_ROOTS.append(p)
            p2 = box / "command-center" / "p2-wave" / "probes"
            if p2.is_dir():
                HARVEST_PROBE_ROOTS.append(p2)


def is_stub(path: Path) -> bool:
    if not path.is_file():
        return False
    head = path.read_text(encoding="utf-8", errors="replace")[:800]
    return "g1-surface: generated" in head or "class _NS:" in head


def resolve_mod(mod: str, inserts: list[Path]) -> Path | None:
    parts = mod.split(".")
    search = list(inserts) + [REPO, REPO / "tools", REPO / "command-center"]
    for root in search:
        cand = root.joinpath(*parts)
        if cand.with_suffix(".py").is_file():
            return cand.with_suffix(".py")
        if (cand / "__init__.py").is_file():
            return cand / "__init__.py"
    return None


def imports_of(path: Path) -> tuple[list[str], list[Path]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    inserts: list[Path] = []
    # crude sys.path.insert detection
    if "REPO / \"tools\"" in text or "REPO / 'tools'" in text:
        inserts.append(REPO / "tools")
    if "HERE" in text:
        inserts.append(path.parent)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [], inserts
    mods: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                top = a.name.split(".")[0]
                if top not in STDLIB:
                    mods.append(a.name)
        elif isinstance(node, ast.ImportFrom):
            if not node.module:
                continue
            top = node.module.split(".")[0]
            if top not in STDLIB:
                mods.append(node.module)
    return sorted(set(mods)), inserts


def harvest_probe(uid: str, name: str) -> Path | None:
    for root in HARVEST_PROBE_ROOTS:
        cand = root / uid / name
        if cand.is_file() and cand.stat().st_size > 40:
            # skip stubs
            return cand
    return None


def main() -> None:
    copied = []
    missing_after = []
    stub_hits: dict[str, list[str]] = {}
    rows = []
    print(f"harvest probe roots={len(HARVEST_PROBE_ROOTS)}")
    for uid in IDS:
        pdir = WAVE / "probes" / uid
        ret_path = pdir / "SUBAGENT-RETURN.json"
        needed = []
        if ret_path.is_file():
            ret = json.loads(ret_path.read_text(encoding="utf-8"))
            for item in (ret.get("named_probes") or []) + (ret.get("probes") or []):
                if not isinstance(item, dict):
                    continue
                cmd = str(item.get("command") or "")
                for tok in cmd.split():
                    t = tok.replace("\\", "/")
                    if t.endswith(".py") and f"probes/{uid}/" in t:
                        needed.append(Path(t).name)
        live = sorted(p.name for p in pdir.glob("probe*.py")) if pdir.is_dir() else []
        restored = []
        for name in needed:
            dest = pdir / name
            if dest.is_file() and dest.stat().st_size > 40:
                continue
            src = harvest_probe(uid, name)
            if src is None:
                missing_after.append(f"{uid}/{name}")
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            copied.append({"id": uid, "name": name, "from": str(src)})
            restored.append(name)
            # also copy sibling helpers from same harvest dir if missing
            for sib in src.parent.iterdir():
                if sib.suffix == ".py" and not (pdir / sib.name).is_file():
                    shutil.copy2(sib, pdir / sib.name)
                    copied.append({"id": uid, "name": sib.name, "from": str(sib)})
        mods = []
        stubs = []
        if pdir.is_dir():
            for py in sorted(pdir.glob("*.py")):
                imps, inserts = imports_of(py)
                for m in imps:
                    mods.append(m)
                    path = resolve_mod(m, inserts)
                    if path and is_stub(path):
                        stubs.append({"mod": m, "path": path.relative_to(REPO).as_posix(), "via": py.name})
                        stub_hits.setdefault(path.relative_to(REPO).as_posix(), []).append(uid)
        rows.append(
            {
                "id": uid,
                "needed": needed,
                "live_probes": live,
                "restored": restored,
                "mods": sorted(set(mods)),
                "stubs": stubs,
            }
        )
        print(
            f"{uid:10} needed={needed} live={live} restored={restored} "
            f"stubs={len(stubs)} mods={len(set(mods))}"
        )
    out = {
        "copied": copied,
        "still_missing": missing_after,
        "stub_files": {k: sorted(set(v)) for k, v in stub_hits.items()},
        "n_stub_files": len(stub_hits),
        "rows": rows,
    }
    dest = WAVE / "ovh-monitor" / "g1-shards" / "_shard03_inventory.json"
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"copied={len(copied)} still_missing={missing_after} stub_files={len(stub_hits)}")
    print("STUBS:")
    for p, uids in sorted(stub_hits.items()):
        print(f"  {p} <- {sorted(set(uids))}")


if __name__ == "__main__":
    main()
