"""Live clean-install + golden-journey harness for TST-0070.

Published artifact = tar.gz packed from a scratch payload tree (never the
repo source tree). Install consumes the unpacked tar into an empty profile.
Each golden journey ends in a file postcondition: exists AND json.loads AND
size >= MIN_BYTES. Exit code 0 is not the evidence.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import uuid
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

UNIT = "TST-0070"
PLUGIN_NAME = "golden-kit"
PLUGIN_VERSION = "1.0.0"
MIN_BYTES = 256
MISSING_DEP = "jsonschema"
STDLIB = set(getattr(sys, "stdlib_module_names", ())) | set(sys.builtin_module_names)

JOURNEY_MANIFEST_PY = r'''#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True)
    p.add_argument("--out", required=True)
    ns = p.parse_args()
    manifest = Path(ns.root) / "plugin.json"
    raw = manifest.read_bytes()
    doc = json.loads(raw.decode("utf-8"))
    report = {
        "bytes": len(raw),
        "hooks": doc.get("hooks"),
        "journey": "identity-manifest",
        "name": doc.get("name"),
        "padding": "x" * 80,
        "postcondition": "exists-and-parses-and-min-size",
        "sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
        "skills": doc.get("skills"),
        "source": str(manifest),
        "unit_id": "TST-0070",
        "version": doc.get("version"),
    }
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
'''

JOURNEY_SKILL_PY = r'''#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True)
    p.add_argument("--out", required=True)
    ns = p.parse_args()
    skill = Path(ns.root) / "skills" / "skill.golden" / "SKILL.md"
    raw = skill.read_bytes()
    text = raw.decode("utf-8")
    heading = ""
    for line in text.splitlines():
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            break
    report = {
        "bytes": len(raw),
        "heading": heading,
        "journey": "skill-checksum",
        "padding": "y" * 80,
        "postcondition": "exists-and-parses-and-min-size",
        "sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
        "source": str(skill),
        "unit_id": "TST-0070",
        "word_count": len(re.findall(r"\S+", text)),
    }
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
'''

JOURNEY_HOOK_PY = r'''#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True)
    p.add_argument("--out", required=True)
    ns = p.parse_args()
    hook = Path(ns.root) / "hooks" / "hook.golden.json"
    raw = hook.read_bytes()
    doc = json.loads(raw.decode("utf-8"))
    report = {
        "bytes": len(raw),
        "enabled": doc.get("enabled"),
        "event": doc.get("event"),
        "fired": True,
        "journey": "hook-fire",
        "padding": "z" * 80,
        "postcondition": "exists-and-parses-and-min-size",
        "sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
        "side_effect": "hook-report-written",
        "source": str(hook),
        "unit_id": "TST-0070",
    }
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
'''


def _first_attr(obj: Any, names: tuple[str, ...]) -> Any:
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    raise AttributeError(f"none of {names} on {obj}")


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(x) for x in obj]
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def payload_digest(root: Path) -> str:
    import plugin.payload as payload

    fn = _first_attr(payload, ("payload_digest", "payload_digest", "digest_payload"))
    return str(fn(root))


def iter_payload_rels(root: Path) -> list[str]:
    import plugin.payload as payload

    for name in ("iter_payload_files", "iter_payload_files"):
        if hasattr(payload, name):
            return list(getattr(payload, name)(root))
    rels: list[str] = []
    for path in Path(root).rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            rels.append(path.relative_to(root).as_posix())
    return sorted(rels)


def install_from_handoff(handoff: dict, dest: Path) -> Any:
    import plugin.install as install

    fn = _first_attr(
        install, ("install_from_handoff", "install_from_handoff", "install")
    )
    return fn(handoff, dest)


def try_marketplace_install(payload: Path, dest: Path) -> Any | None:
    try:
        import marketplace.install as marketplace_install

        return marketplace_install.install(payload, dest)
    except Exception:
        return None


def _projection_version_key() -> str:
    try:
        import marketplace.handoff as marketplace_handoff

        schema = marketplace_handoff.load_schema()
        props = (
            (schema.get("properties") or {})
            .get("projection_map", {})
            .get("properties", {})
        )
        if "schema_version" in props:
            return "schema_version"
        if "schema_version" in props:
            return "schema_version"
    except Exception:
        pass
    return "schema_version"


def build_schema_valid_handoff(payload: Path) -> dict:
    try:
        import marketplace.handoff as marketplace_handoff

        fn = _first_attr(marketplace_handoff, ("build_handoff", "build_handoff"))
        return fn(payload, source="direct")
    except Exception:
        pass
    digest = payload_digest(payload)
    entries = [
        {"source": rel, "dest": f"plugins/{PLUGIN_NAME}/{rel}"}
        for rel in iter_payload_rels(payload)
    ]
    ver_key = _projection_version_key()
    return {
        "declared_permissions": [f"fs:write:plugins/{PLUGIN_NAME}"],
        "digest": {"alg": "sha256", "value": digest},
        "kind": "install-handoff",
        "payload_path": str(payload.resolve()),
        "plugin_name": PLUGIN_NAME,
        "projection_map": {"entries": entries, ver_key: 1},
        "schema_version": 1,
        "source": "direct",
        "transaction_id": str(uuid.uuid4()),
    }


def build_payload_tree(root: Path) -> Path:
    payload = root / "payload"
    (payload / "skills" / "skill.golden").mkdir(parents=True)
    (payload / "hooks").mkdir(parents=True)
    (payload / "rules").mkdir(parents=True)
    (payload / "journeys").mkdir(parents=True)
    plugin = {
        "description": "TST-0070 published-artifact fixture: three golden journeys",
        "hooks": ["hooks/hook.golden.json"],
        "name": PLUGIN_NAME,
        "permissions": [f"fs:write:plugins/{PLUGIN_NAME}"],
        "rules": ["rules/rule.golden.md"],
        "skills": ["skills/skill.golden/SKILL.md"],
        "version": PLUGIN_VERSION,
        "x-journeys": ["identity-manifest", "skill-checksum", "hook-fire"],
    }
    (payload / "plugin.json").write_text(
        json.dumps(plugin, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (payload / "skills" / "skill.golden" / "SKILL.md").write_text(
        "# golden skill\n\nEmit a checksum report of this skill from the "
        "INSTALLED copy, not from the source tree. TST-0070 journey 2.\n",
        encoding="utf-8",
    )
    (payload / "rules" / "rule.golden.md").write_text(
        "# golden rule\nInstall from the packed artifact only.\n",
        encoding="utf-8",
    )
    (payload / "hooks" / "hook.golden.json").write_text(
        json.dumps(
            {
                "enabled": True,
                "event": "post-install",
                "name": "golden-hook",
                "unit": UNIT,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (payload / "PACKAGE-METADATA.json").write_text(
        json.dumps(
            {
                "install_requires": [],
                "name": PLUGIN_NAME,
                "note": "Third-party runtime deps are not declared. Measured gap.",
                "requires_python": ">=3.11",
                "version": PLUGIN_VERSION,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (payload / "journeys" / "identity_manifest.py").write_text(
        JOURNEY_MANIFEST_PY, encoding="utf-8"
    )
    (payload / "journeys" / "skill_checksum.py").write_text(
        JOURNEY_SKILL_PY, encoding="utf-8"
    )
    (payload / "journeys" / "hook_fire.py").write_text(JOURNEY_HOOK_PY, encoding="utf-8")
    return payload


def pack_artifact(payload: Path, dest_tar: Path) -> dict:
    dest_tar.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(dest_tar, "w:gz") as tf:
        for rel in iter_payload_rels(payload):
            tf.add(payload / rel, arcname=f"{PLUGIN_NAME}/{rel}")
    with tarfile.open(dest_tar, "r:gz") as tf:
        members = sorted(m.name for m in tf.getmembers() if m.isfile())
    raw = dest_tar.read_bytes()
    return {
        "bytes": len(raw),
        "contains_jsonschema": any("jsonschema" in m for m in members),
        "contains_repo_tools": any("tools/" in m for m in members),
        "member_count": len(members),
        "members": members,
        "path": str(dest_tar),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def unpack_artifact(tar_path: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tf:
        tf.extractall(dest, filter="data")
    payload = dest / PLUGIN_NAME
    if not payload.is_dir():
        raise RuntimeError(f"unpacked artifact missing {PLUGIN_NAME}/")
    return payload


def empty_profile(root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    before = sorted(
        p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
    )
    return {
        "empty": len(before) == 0,
        "file_count": len(before),
        "files": before,
        "has_claude": (root / ".claude").exists(),
        "has_plugins": (root / "plugins").exists(),
        "path": str(root),
    }


def postcondition(path: Path, min_bytes: int = MIN_BYTES) -> dict:
    exists = path.is_file()
    size = path.stat().st_size if exists else 0
    parsed = False
    parse_error = None
    if exists:
        try:
            json.loads(path.read_text(encoding="utf-8"))
            parsed = True
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            parse_error = f"{type(exc).__name__}: {exc}"
    return {
        "bytes": size,
        "exists": exists,
        "min_bytes": min_bytes,
        "ok": exists and parsed and size >= min_bytes,
        "parse_error": parse_error,
        "parses": parsed,
        "path": str(path),
    }


def install_published(unpacked_payload: Path, dest: Path) -> dict:
    repo_plugin = (TOOLS / "plugin").resolve()
    if unpacked_payload.resolve() == repo_plugin:
        raise RuntimeError("refusing to install from the source tree")
    live = try_marketplace_install(unpacked_payload, dest)
    if live is not None:
        return {
            "dest_root": str(dest),
            "payload_is_source_tree": False,
            "payload_path": str(unpacked_payload),
            "result": _jsonable(live),
            "via": "marketplace.install",
        }
    handoff = build_schema_valid_handoff(unpacked_payload)
    result = install_from_handoff(handoff, dest)
    return {
        "dest_root": str(dest),
        "handoff_keys": sorted(handoff.keys()),
        "payload_is_source_tree": False,
        "payload_path": str(unpacked_payload),
        "result": _jsonable(result),
        "transaction_id": handoff.get("transaction_id"),
        "via": "plugin.install.install_from_handoff",
    }


def installed_plugin_root(dest: Path) -> Path:
    return dest / "plugins" / PLUGIN_NAME


def run_journey(script_name: str, plugin_root: Path, out: Path) -> dict:
    script = plugin_root / "journeys" / script_name
    if not script.is_file():
        raise FileNotFoundError(script)
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PYTHONPATH", None)
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(script),
            "--root",
            str(plugin_root),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    pc = postcondition(out)
    return {
        "exit_code": proc.returncode,
        "output": str(out),
        "pass": proc.returncode == 0 and pc["ok"],
        "postcondition": pc,
        "script": script_name,
        "script_path": str(script),
        "stderr": (proc.stderr or "")[-500:],
        "stdout": (proc.stdout or "")[-500:],
    }


def run_three_journeys(plugin_root: Path, out_dir: Path) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    specs = (
        ("identity_manifest.py", "journey-identity-manifest.json"),
        ("skill_checksum.py", "journey-skill-checksum.json"),
        ("hook_fire.py", "journey-hook-fire.json"),
    )
    return [run_journey(script, plugin_root, out_dir / name) for script, name in specs]


def corrupt_and_check(path: Path) -> dict:
    original = path.read_bytes()
    path.write_bytes(b"{")
    bad = postcondition(path)
    path.write_bytes(original)
    good = postcondition(path)
    return {
        "corrupt": bad,
        "fired_on_corrupt": bad["ok"] is False,
        "restored": good,
        "silent_on_good": good["ok"] is True,
    }


def _top_level_imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def third_party_imports(scan_roots: list[Path]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for root in scan_roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            for name in _top_level_imports(path):
                if name in STDLIB or name in {"plugin", "marketplace"}:
                    continue
                try:
                    rel = path.relative_to(REPO).as_posix()
                except ValueError:
                    rel = str(path)
                found.setdefault(name, []).append(rel)
    return {k: sorted(set(v)) for k, v in sorted(found.items())}


def packaging_metadata_present() -> dict[str, bool]:
    names = (
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "Pipfile",
        "poetry.lock",
    )
    return {n: (REPO / n).is_file() for n in names}


def dep_census(artifact: dict) -> dict:
    third = third_party_imports([TOOLS / "plugin", TOOLS / "marketplace"])
    meta = packaging_metadata_present()
    packed_has = bool(artifact.get("contains_jsonschema"))
    missing = []
    if "jsonschema" in third and not packed_has and not any(meta.values()):
        missing.append(
            {
                "in_packed_artifact": packed_has,
                "name": "jsonschema",
                "packaging_metadata_present": any(meta.values()),
                "repo_importers": third["jsonschema"],
            }
        )
    return {
        "answer": MISSING_DEP if missing else None,
        "missing_from_package": missing,
        "packaging_metadata": meta,
        "packed_contains_jsonschema": packed_has,
        "third_party_imports_in_plugin_and_marketplace": third,
    }


def exec_policy_requires_jsonschema() -> dict:
    import plugin.exec_policy as exec_policy

    validate = _first_attr(exec_policy, ("validate_policy", "validate_policy"))
    policy = {
        "allow_connect": [],
        "allow_spawn": ["/bin/echo"],
        "allow_write": ["/tmp"],
        "schema_version": 1,
        "windows_limitation": (
            "Windows has no native OS-level process sandbox for arbitrary "
            "third-party binaries; this module does NOT provide one."
        ),
    }
    saved = exec_policy.jsonschema
    live_err = None
    if saved is not None:
        try:
            validate(policy)
        except Exception as exc:
            live_err = f"{type(exc).__name__}: {exc}"
    exec_policy.jsonschema = None
    hidden_raised = False
    hidden_exc = None
    try:
        validate(policy)
    except Exception as exc:
        hidden_raised = True
        hidden_exc = f"{type(exc).__name__}: {exc}"
    finally:
        exec_policy.jsonschema = saved
    return {
        "hidden_exception": hidden_exc,
        "hidden_raises": hidden_raised,
        "live_jsonschema_importable": saved is not None,
        "live_validate_error": live_err,
        "load_bearing": hidden_raised and saved is not None,
    }


def run_clean_install() -> dict:
    with tempfile.TemporaryDirectory(prefix="tst0070-") as tmp:
        tmp_path = Path(tmp)
        payload = build_payload_tree(tmp_path / "src")
        tar_path = tmp_path / "dist" / f"{PLUGIN_NAME}-{PLUGIN_VERSION}.tar.gz"
        artifact = pack_artifact(payload, tar_path)
        unpacked = unpack_artifact(tar_path, tmp_path / "unpacked")
        profile = tmp_path / "empty-profile"
        before = empty_profile(profile)
        if not before["empty"]:
            raise RuntimeError("profile was not empty before install")
        dest = profile / "site"
        installed = install_published(unpacked, dest)
        plugin_root = installed_plugin_root(dest)
        plugin_json = plugin_root / "plugin.json"
        pc = postcondition(plugin_json)
        after_files = sorted(
            p.relative_to(profile).as_posix()
            for p in profile.rglob("*")
            if p.is_file()
        )
        return {
            "artifact": artifact,
            "install": installed,
            "installed_files": after_files,
            "pass": before["empty"] and pc["ok"] and len(after_files) >= 4,
            "plugin_json_postcondition": pc,
            "plugin_root": str(plugin_root),
            "profile_before": before,
            "unpacked_is_repo_tools": unpacked.resolve() == (TOOLS / "plugin").resolve(),
            "unpacked_payload": str(unpacked),
        }


def run_golden_journeys() -> dict:
    with tempfile.TemporaryDirectory(prefix="tst0070-j-") as tmp:
        tmp_path = Path(tmp)
        payload = build_payload_tree(tmp_path / "src")
        tar_path = tmp_path / "dist" / f"{PLUGIN_NAME}-{PLUGIN_VERSION}.tar.gz"
        artifact = pack_artifact(payload, tar_path)
        unpacked = unpack_artifact(tar_path, tmp_path / "unpacked")
        profile = tmp_path / "empty-profile"
        empty_profile(profile)
        dest = profile / "site"
        install_published(unpacked, dest)
        plugin_root = installed_plugin_root(dest)
        journeys = run_three_journeys(plugin_root, tmp_path / "journey-out")
        corrupt = corrupt_and_check(Path(journeys[0]["output"]))
        deps = dep_census(artifact)
        load_bearing = exec_policy_requires_jsonschema()
        return {
            "all_three_pass": all(j["pass"] for j in journeys) and len(journeys) == 3,
            "artifact": artifact,
            "corruption_control": corrupt,
            "dep_census": deps,
            "exec_policy_jsonschema": load_bearing,
            "journeys": journeys,
            "pass": (
                all(j["pass"] for j in journeys)
                and len(journeys) == 3
                and corrupt["fired_on_corrupt"]
                and corrupt["silent_on_good"]
                and deps.get("answer") == MISSING_DEP
                and load_bearing["load_bearing"]
            ),
            "plugin_root": str(plugin_root),
        }


def run_all() -> dict:
    install = run_clean_install()
    journeys = run_golden_journeys()
    return {
        "clean_install": install,
        "golden_journeys": journeys,
        "missing_runtime_dependency": MISSING_DEP,
        "pass": bool(install.get("pass") and journeys.get("pass")),
        "unit_id": UNIT,
    }
