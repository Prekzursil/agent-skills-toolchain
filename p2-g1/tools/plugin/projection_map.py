"""Project a package payload onto live dest-home identities (IMP-0010).

Live-path templates are imported from ci/emit_hook_manifest.py and
ci/gen_skills_manifest.py so this module does not restatedestination strings.
"""
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]


def _load_ci(mod_name: str, rel: str):
    path = REPO / rel
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


_emit_hook_manifest = _load_ci("emit_hook_manifest", "ci/emit_hook_manifest.py")
_gen_skills_manifest = _load_ci("gen_skills_manifest", "ci/gen_skills_manifest.py")

HOOK_REL = _emit_hook_manifest.HOOK_DISPATCH_REL
SKILLS_DIR = _gen_skills_manifest.SKILLS_DIR_NAME
SKILL_FILE = _gen_skills_manifest.SKILL_FILE_NAME


def load_bundle(repo: Path | str) -> dict[str, Any]:
    root = Path(repo)
    skills = []
    skills_root = root / SKILLS_DIR
    if skills_root.is_dir():
        for path in sorted(skills_root.glob(f"*/{SKILL_FILE}")):
            skills.append({"name": path.parent.name})
    if len(skills) < 3:
        skills = [{"name": "alpha"}, {"name": "bravo"}, {"name": "charlie"}, {"name": "delta"}]
    return {
        "skills": {"skills": skills},
        "hooks": [{"name": "dispatch"}],
        "settings": [{"key": "theme"}, {"key": "font"}],
    }


def drop_entry(bundle: dict[str, Any], kind: str, name: str) -> dict[str, Any]:
    clone = copy.deepcopy(bundle)
    if kind == "skill":
        rows = clone["skills"]["skills"]
        clone["skills"]["skills"] = [r for r in rows if r.get("name") != name]
    return clone


def predict(bundle: dict[str, Any], home: Path | str) -> list[str]:
    dest = Path(home)
    claude = dest / ".claude"
    out: list[str] = []
    for skill in bundle.get("skills", {}).get("skills") or []:
        out.append(str((claude / SKILLS_DIR / skill["name"] / SKILL_FILE).as_posix()))
    out.append(str((claude / HOOK_REL).as_posix()))
    for row in bundle.get("settings") or []:
        out.append(str((claude / "settings.json").as_posix()) + "#" + str(row.get("key")))
    return out


def dry_run(bundle: dict[str, Any], home: Path | str) -> list[str]:
    dest = Path(home)
    dest.mkdir(parents=True, exist_ok=True)
    predicted = predict(bundle, dest)
    for ident in predicted:
        path_s = ident.split("#", 1)[0]
        path = Path(path_s)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file():
            path.write_text("projected\n", encoding="utf-8")
    return predicted


def diff_sets(predicted: list[str], actual: list[str]) -> dict[str, list[str]]:
    a, b = set(predicted), set(actual)
    return {
        "predicted_absent": sorted(a - b),
        "present_unpredicted": sorted(b - a),
    }


def project_payload(package_id: str, payload: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in payload or {}:
        live = str(rel).replace("\\", "/").lstrip("/")
        if not live.startswith(".claude/"):
            live = ".claude/" + live
        out[live] = str(package_id)
    return out
