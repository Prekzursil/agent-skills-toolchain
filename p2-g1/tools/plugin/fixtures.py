"""Archive fixtures for IMP-0005 dual-census and inventory-diff probes."""
from __future__ import annotations

import os
import tarfile
import zipfile
from pathlib import Path

PLANT_PATH = "keep/plant.txt"

# TST-0025 harness imports `fixtures` via tools/plugin on sys.path.
SEED = 25
N_QUERIES = 24
N_HOOK = 16
ALLOWED_ROOT = Path(__file__).resolve().parents[2] / "command-center" / "p2-wave" / "probes" / "TST-0025" / "work" / "allowed"
DENIED_ROOT = Path(__file__).resolve().parents[2] / "command-center" / "p2-wave" / "probes" / "TST-0025" / "work" / "denied"


def _tst0025():
    import importlib.util

    path = (
        Path(__file__).resolve().parents[2]
        / "command-center"
        / "p2-wave"
        / "probes"
        / "TST-0025"
        / "fixtures.py"
    )
    spec = importlib.util.spec_from_file_location("tst0025_fixtures", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_queries(seed: int = SEED, n: int = N_QUERIES):
    return _tst0025().make_queries(seed, n)


def make_hook_subjects(seed: int = SEED, n: int = N_HOOK):
    return _tst0025().make_hook_subjects(seed, n)


def input_fingerprint(queries, hooks):
    return _tst0025().input_fingerprint(queries, hooks)

PREVIOUS_FILES: dict[str, bytes] = {
    "keep/plant.txt": b"planted-control\n",
    "keep/grow.txt": b"small\n",
    "drop/gone.txt": b"will-remove\n",
    "keep/stable.txt": b"same\n",
}

CURRENT_OK_FILES: dict[str, bytes] = {
    "keep/plant.txt": b"planted-control\n",
    "keep/grow.txt": b"small\n",
    "keep/stable.txt": b"same\n",
    "keep/extra-ok.txt": b"ok\n",
}

INVENTORY_PREV: dict[str, bytes] = {
    "keep/grow.txt": b"aa\n",
    "drop/gone.txt": b"gone\n",
    "keep/stable.txt": b"same\n",
}

INVENTORY_CURR: dict[str, bytes] = {
    "keep/grow.txt": b"aa" + (b"x" * 64) + b"\n",
    "new/added.txt": b"new\n",
    "keep/stable.txt": b"same\n",
}


def _write_zip(path: Path, files: dict[str, bytes]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel, body in files.items():
            zf.writestr(rel, body)
    return path


def write_tar(path: Path, files: dict[str, bytes]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w") as tf:
        for rel, body in files.items():
            info = tarfile.TarInfo(name=rel)
            info.size = len(body)
            import io

            tf.addfile(info, io.BytesIO(body))
    return path


def previous_zip(path: Path) -> Path:
    return _write_zip(path, PREVIOUS_FILES)


def current_ok_zip(path: Path) -> Path:
    return _write_zip(path, CURRENT_OK_FILES)


def over_budget_zip(path: Path) -> Path:
    files = dict(CURRENT_OK_FILES)
    # Incompressible so ZIP_STORED/DEFLATED stays over the previous-archive budget.
    files["huge.bin"] = os.urandom(512 * 1024)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as zf:
        for rel, body in files.items():
            zf.writestr(rel, body)
    return path


def inventory_previous_zip(path: Path) -> Path:
    return _write_zip(path, INVENTORY_PREV)


def inventory_current_zip(path: Path) -> Path:
    return _write_zip(path, INVENTORY_CURR)
