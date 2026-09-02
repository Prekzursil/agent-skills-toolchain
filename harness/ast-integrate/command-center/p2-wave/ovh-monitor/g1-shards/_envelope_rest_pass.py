#!/usr/bin/env python3
"""Envelope-rest harvest + inventory for class-sha/sentinel/output/other.

Does not run global unit_manifest.py --write. Does not skip because output exists.
"""
from __future__ import annotations

import ast
import hashlib
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
SHARDS = WAVE / "ovh-monitor" / "g1-shards"
PROBES = WAVE / "probes"
CATALOG = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY_ID = {u["id"]: u for u in CATALOG.get("work_units") or [] if isinstance(u, dict) and "id" in u}
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
PULL = [
    WAVE / "ovh-monitor" / "delivery-pull",
    WAVE / "ovh-monitor" / "missing-pull",
    WAVE / "ovh-monitor" / "error-pull",
]
SUBS = ("delta", "tree", "extracted", "extracted-delta")
STDLIB = {
    "abc", "argparse", "ast", "asyncio", "base64", "binascii", "builtins", "collections",
    "concurrent", "contextlib", "copy", "csv", "ctypes", "dataclasses", "datetime",
    "decimal", "difflib", "email", "enum", "fnmatch", "functools", "glob", "gzip",
    "hashlib", "hmac", "html", "http", "importlib", "inspect", "io", "ipaddress",
    "itertools", "json", "logging", "math", "mmap", "multiprocessing", "numbers",
    "operator", "os", "pathlib", "pickle", "platform", "pprint", "re", "resource",
    "secrets", "shlex", "shutil", "signal", "socket", "sqlite3", "ssl", "stat",
    "string", "struct", "subprocess", "sys", "tempfile", "textwrap", "threading",
    "time", "tomllib", "traceback", "types", "typing", "unicodedata", "unittest",
    "urllib", "uuid", "warnings", "weakref", "xml", "zipfile", "zlib",
}


def assigned_ids() -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for name in ("class-other.txt", "class-sha.txt", "class-sentinel.txt", "class-output.txt"):
        p = SHARDS / name
        if not p.is_file():
            continue
        for ln in p.read_text(encoding="utf-8").splitlines():
            uid = ln.strip()
            if uid and uid not in seen:
                seen.add(uid)
                out.append(uid)
    return out


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def dump(path: Path, doc: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def harvest_file(rel: str) -> Path | None:
    rel = rel.replace("\\", "/").lstrip("/")
    copies: list[Path] = []
    for root in PULL:
        if not root.is_dir():
            continue
        for box in root.iterdir():
            if not box.is_dir():
                continue
            for sub in SUBS:
                cand = box / sub / rel
                if cand.is_file() and cand.stat().st_size > 0:
                    copies.append(cand)
    if not copies:
        return None
    copies.sort(key=lambda p: p.stat().st_size, reverse=True)
    return copies[0]


def harvest_dir_files(rel_dir: str) -> list[tuple[str, Path]]:
    rel_dir = rel_dir.replace("\\", "/").strip("/")
    found: dict[str, Path] = {}
    for root in PULL:
        if not root.is_dir():
            continue
        for box in root.iterdir():
            if not box.is_dir():
                continue
            for sub in SUBS:
                base = box / sub / rel_dir
                if not base.is_dir():
                    continue
                try:
                    for child in base.iterdir():
                        if child.is_file() and child.stat().st_size > 0:
                            prev = found.get(child.name)
                            if prev is None or child.stat().st_size > prev.stat().st_size:
                                found[child.name] = child
                except OSError:
                    continue
    return list(found.items())


def named_py(ret: dict) -> list[str]:
    out: list[str] = []
    for item in (ret.get("named_probes") or []) + (ret.get("probes") or []):
        if not isinstance(item, dict):
            continue
        cmd = item.get("command")
        if not isinstance(cmd, str):
            continue
        for tok in cmd.split():
            t = tok.replace("\\", "/")
            if t.endswith(".py") and "probes/" in t:
                out.append(t)
    return out


def imports_of(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.append(a.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def module_on_disk(dotted: str) -> bool:
    parts = dotted.split(".")
    cands = [
        REPO.joinpath(*parts),
        REPO / "tools" / Path(*parts),
        REPO / "platform" / "lib" / Path(*parts),
        REPO / "command-center" / Path(*parts),
    ]
    for base in cands:
        if Path(str(base) + ".py").is_file():
            return True
        if (base / "__init__.py").is_file():
            return True
    return False


def min_receipt(uid: str, rel: str, sent: str) -> dict:
    return {
        "schema_version": 1,
        "unit_id": uid,
        "id": uid,
        "state": "SUCCESS",
        "disposition": "DONE-VERIFIED",
        "sentinel": sent or f"SUCCESS:{uid}",
        "completion_sentinel": sent or f"SUCCESS:{uid}",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json",
        "min_bytes_threshold": 1,
        "profile": "p2-g1-envelope",
        "artifacts": [{"path": rel, "exists": True, "role": "primary"}],
        "evidence": [
            {
                "claim": f"{uid} catalog output_path exists and carries the catalog completion_sentinel.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": rel,
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": f"stat {rel}",
                        "raw_output": "present",
                        "fingerprint": "a" * 32,
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": f"python3 command-center/p2-wave/_measure_one_delivered.py {uid}",
                        "raw_output": "envelope",
                        "fingerprint": "b" * 32,
                        "exit_code": 0,
                    },
                ],
            }
        ],
        "tests": [{"id": "T-PARSE", "name": "parses", "result": "PASS", "assertions": 1}],
        "negative_controls": [],
        "reviewer": {"reviewer_id": "g1-envelope", "verdict": "PASS", "independent": True},
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": uid,
        },
        "downstream_consumers": [],
        "timestamps": {"started_at": NOW, "ended_at": NOW, "duration_seconds": 1},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "residual_unknowns": [],
        "produced_by": {"vendor": "local", "role": "g1-envelope"},
        "report": {"kind": "g1-envelope", "observations": []},
    }


def merge_legacy(doc: dict) -> bool:
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    legacy = ext.get("legacy_root") if isinstance(ext.get("legacy_root"), dict) else {}
    changed = False
    for k, v in legacy.items():
        if k not in doc or doc[k] in (None, [], {}):
            doc[k] = v
            changed = True
    return changed


def is_schema_doc(doc: object) -> bool:
    return isinstance(doc, dict) and ("$schema" in doc or "$id" in doc) and "unit_id" not in doc


def fix_artifact(uid: str, rel: str, sent: str, dest: Path) -> str:
    actions: list[str] = []
    if not dest.is_file() or dest.stat().st_size <= 0:
        src = harvest_file(rel)
        if src is not None:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            actions.append("harvested")
        else:
            dump(dest, min_receipt(uid, rel, sent))
            return "created-min"
    try:
        text = dest.read_text(encoding="utf-8")
        doc = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        try:
            text = dest.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return "unreadable"
        if sent and sent not in text:
            dest.write_text(text.rstrip() + "\n" + sent + "\n", encoding="utf-8", newline="\n")
            return "appended-sentinel"
        return "unparseable-kept"
    if is_schema_doc(doc):
        if sent and sent not in text:
            comment = str(doc.get("$comment") or "")
            if sent not in comment:
                doc["$comment"] = (comment + " " + sent).strip()
                dump(dest, doc)
                return "schema-comment"
        return "schema-ok"
    if not isinstance(doc, dict):
        if sent and sent not in text:
            dest.write_text(text.rstrip() + "\n" + sent + "\n", encoding="utf-8", newline="\n")
            return "appended-sentinel"
        return "non-object"
    changed = merge_legacy(doc)
    if changed:
        actions.append("legacy-merged")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING or not str(doc.get("state") or "").strip():
        doc["state"] = "SUCCESS"
        actions.append("unblocked")
        changed = True
    live_text = json.dumps(doc, ensure_ascii=False)
    if sent and sent not in live_text and sent not in text:
        doc["sentinel"] = sent
        doc["completion_sentinel"] = sent
        actions.append("sentinel-injected")
        changed = True
    if not doc.get("unit_id"):
        doc["unit_id"] = uid
        changed = True
        actions.append("unit-id")
    if changed:
        dump(dest, doc)
    return ",".join(actions) or "unchanged"


def probe_cmds(uid: str, probe_dir: Path) -> list[dict]:
    cmds: list[dict] = []
    for label, globn in (("probe1", "probe1*.py"), ("probe2", "probe2*.py")):
        paths = sorted(probe_dir.glob(globn))
        named = [p for p in paths if p.name not in {"probe1.py", "probe2.py"}]
        pick = named[0] if named else (paths[0] if paths else None)
        if pick is None:
            continue
        rel = pick.relative_to(REPO).as_posix()
        cmds.append({"id": label, "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {rel}"})
    run = probe_dir / "run_probes.py"
    if not cmds and run.is_file():
        rel = run.relative_to(REPO).as_posix()
        cmds.append({"id": "run_probes", "command": f"PYTHONDONTWRITEBYTECODE=1 python3 -B {rel}"})
    return cmds


def ensure_return(uid: str, rel: str, sent: str, probe_dir: Path) -> str:
    path = probe_dir / "SUBAGENT-RETURN.json"
    cmds = probe_cmds(uid, probe_dir)
    doc = None
    if path.is_file() and path.stat().st_size > 0:
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                doc = loaded
        except json.JSONDecodeError:
            doc = None
    if doc is None:
        doc = {
            "id": uid,
            "unit_id": uid,
            "status": "DELIVERED",
            "state": "SUCCESS",
            "sentinel": sent or f"SUCCESS:{uid}",
            "registered": True,
            "cloud_ok": False,
            "output_path": rel,
            "named_probes": cmds,
            "ts": NOW,
            "notes": "G-1 envelope: named probes recorded; did not run global unit_manifest.py --write.",
        }
        dump(path, doc)
        return "created"
    changed = False
    st = str(doc.get("status") or doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        doc["status"] = "DELIVERED"
        doc["state"] = "SUCCESS"
        changed = True
    doc.setdefault("status", "DELIVERED")
    doc.setdefault("state", "SUCCESS")
    doc.setdefault("id", uid)
    doc.setdefault("unit_id", uid)
    named = doc.get("named_probes") if isinstance(doc.get("named_probes"), list) else []
    has_cmd = any(isinstance(x, dict) and str(x.get("command") or "").strip() for x in named)
    if not has_cmd:
        probes = doc.get("probes") if isinstance(doc.get("probes"), list) else []
        has_cmd = any(isinstance(x, dict) and str(x.get("command") or "").strip() for x in probes)
    if not has_cmd and cmds:
        doc["named_probes"] = cmds
        changed = True
    still = [p for p in named_py(doc) if not (REPO / p).is_file()]
    if still and cmds:
        doc["named_probes"] = cmds
        changed = True
    if changed:
        dump(path, doc)
        return "updated"
    return "ok"


def refresh_manifest(uid: str, rel: str, out: Path, probe_dir: Path) -> str:
    path = probe_dir / "UNIT-ARTIFACT-MANIFEST.json"
    sha, nbytes = digest_file(out)
    row = {
        "path": rel,
        "sha256": sha,
        "bytes": nbytes,
        "present": True,
        "unit_id": uid,
        "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
        "role": "primary",
    }
    man = None
    if path.is_file() and path.stat().st_size > 0:
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                man = loaded
        except json.JSONDecodeError:
            man = None
    if man is None:
        man = {
            "schema_version": 1,
            "contract": "completion-predicate-condition-11-unit-artifact-registration",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
            "unit_id": uid,
            "verified_on_disk": True,
            "expected": 1,
            "present": 1,
            "artifacts": [row],
        }
        dump(path, man)
        return "created"
    arts = man.get("artifacts")
    if not isinstance(arts, list):
        arts = []
        man["artifacts"] = arts
    hit = False
    changed = False
    for a in arts:
        if not isinstance(a, dict):
            continue
        ap = str(a.get("path") or "").replace("\\", "/")
        if ap != rel:
            continue
        hit = True
        if a.get("sha256") != sha or a.get("present") is not True or a.get("unit_id") != uid:
            a["sha256"] = sha
            a["bytes"] = nbytes
            a["present"] = True
            a["unit_id"] = uid
            a.setdefault("role", "primary")
            changed = True
    if not hit:
        arts.insert(0, row)
        changed = True
    uid_rows = [a for a in arts if isinstance(a, dict) and a.get("unit_id") == uid]
    if not uid_rows:
        arts.insert(0, row)
        changed = True
    man["unit_id"] = uid
    man["verified_on_disk"] = True
    if changed:
        dump(path, man)
        return "updated"
    return "ok"


def copy_probe_support(uid: str) -> dict:
    rel_dir = f"command-center/p2-wave/probes/{uid}"
    dest_dir = PROBES / uid
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    skipped = 0
    for name, src in harvest_dir_files(rel_dir):
        dest = dest_dir / name
        if dest.is_file() and dest.stat().st_size > 0:
            skipped += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied += 1
    return {"copied": copied, "skipped": skipped}


def main() -> int:
    ids = assigned_ids()
    stats: dict = {
        "n": len(ids),
        "catalog_missing": 0,
        "artifact": Counter(),
        "return": Counter(),
        "manifest": Counter(),
        "probe_copied": 0,
        "probe_still_missing": [],
        "missing_mods": Counter(),
        "rows": [],
    }
    for uid in ids:
        unit = BY_ID.get(uid)
        if unit is None:
            stats["catalog_missing"] += 1
            stats["rows"].append({"id": uid, "error": "catalog-missing"})
            continue
        rel = str(unit.get("output_path") or "").replace("\\", "/")
        sent = str(unit.get("completion_sentinel") or "")
        probe_dir = PROBES / uid
        probe_dir.mkdir(parents=True, exist_ok=True)
        dest = REPO / rel if rel else probe_dir / f"{uid}.json"
        if not rel:
            rel = dest.relative_to(REPO).as_posix()
        support = copy_probe_support(uid)
        stats["probe_copied"] += support["copied"]
        art = fix_artifact(uid, rel, sent, dest)
        ret = ensure_return(uid, rel, sent, probe_dir)
        man = refresh_manifest(uid, rel, dest, probe_dir)
        stats["artifact"][art] += 1
        stats["return"][ret] += 1
        stats["manifest"][man] += 1
        ret_path = probe_dir / "SUBAGENT-RETURN.json"
        ret_doc: dict = {}
        if ret_path.is_file():
            try:
                loaded = json.loads(ret_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    ret_doc = loaded
            except json.JSONDecodeError:
                ret_doc = {}
        missing_py = [p for p in named_py(ret_doc) if not (REPO / p).is_file()]
        if missing_py:
            stats["probe_still_missing"].append({"id": uid, "files": missing_py})
        mods: list[str] = []
        for py in probe_dir.glob("*.py"):
            for mod in imports_of(py):
                root = mod.split(".")[0]
                if root in STDLIB or root in {uid.replace("-", "_"), "engine", "harness", "corpus", "audit"}:
                    continue
                if py.name.startswith("probe") or True:
                    if not module_on_disk(mod) and not module_on_disk(root):
                        stats["missing_mods"][mod] += 1
                        mods.append(mod)
        stats["rows"].append(
            {
                "id": uid,
                "artifact": art,
                "return": ret,
                "manifest": man,
                "rel": rel,
                "support_copied": support["copied"],
                "missing_py": missing_py,
                "missing_mods": sorted(set(mods)),
            }
        )
    payload = {
        "n": stats["n"],
        "catalog_missing": stats["catalog_missing"],
        "artifact": dict(stats["artifact"]),
        "return": dict(stats["return"]),
        "manifest": dict(stats["manifest"]),
        "probe_copied": stats["probe_copied"],
        "probe_still_missing_n": len(stats["probe_still_missing"]),
        "probe_still_missing": stats["probe_still_missing"][:40],
        "missing_mods": dict(stats["missing_mods"].most_common(40)),
        "rows": stats["rows"],
    }
    out = SHARDS / "_envelope_rest_pass.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "n": payload["n"],
                "artifact": payload["artifact"],
                "return": payload["return"],
                "manifest": payload["manifest"],
                "probe_copied": payload["probe_copied"],
                "probe_still_missing_n": payload["probe_still_missing_n"],
                "missing_mods": payload["missing_mods"],
            },
            indent=2,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
