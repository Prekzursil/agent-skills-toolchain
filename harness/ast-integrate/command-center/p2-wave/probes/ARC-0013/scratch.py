"""Scratch-clone helpers: copy ARC-0010 generator, mutate, import, generate."""
from __future__ import annotations

import hashlib
import importlib.util
import shutil
import tempfile
from pathlib import Path
from types import ModuleType

PLANTED_OLD = '        "generator_id": GENERATOR_ID,\n'
PLANTED_NEW = '        "generator_id": GENERATOR_ID + "-planted",\n'
WHITESPACE_MARK = "\n\n# ARC-0013 whitespace-only plant (not a string template)\n\n"


def copy_generator_tree(src_dir: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="arc0013-scratch-"))
    for name in ("generator.py", "registry.json", "registry.schema.json"):
        shutil.copy2(src_dir / name, tmp / name)
    return tmp


def source_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def plant_semantic(generator_py: Path) -> None:
    text = generator_py.read_text(encoding="utf-8")
    if PLANTED_OLD not in text:
        raise RuntimeError("plant target missing in generator.py")
    if text.count(PLANTED_OLD) != 1:
        raise RuntimeError("plant target not unique")
    generator_py.write_text(text.replace(PLANTED_OLD, PLANTED_NEW, 1), encoding="utf-8")


def plant_whitespace(generator_py: Path) -> None:
    text = generator_py.read_text(encoding="utf-8")
    needle = "from typing import Any\n"
    if needle not in text:
        raise RuntimeError("whitespace plant target missing")
    generator_py.write_text(text.replace(needle, needle + WHITESPACE_MARK, 1), encoding="utf-8")


def load_generator(path: Path, mod_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def generate_from(mod: ModuleType) -> dict[str, bytes]:
    registry = mod.load_json(mod.DEFAULT_REGISTRY)
    return mod.generate(registry)
