"""Fixture stores + declaration scan for the IMP-0430 bleed/audit probes."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE_LIVE = HERE / "fixtures-live" / "hooks"
SHARED = REPO / "hooks" / "_shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from session_keyed_store import ProjectKeyedMutant, SessionKeyedStore  # noqa: E402

STORES = ("goal_inject", "ledger_replay", "claims", "caches")


def fresh_store_root() -> Path:
    return Path(tempfile.mkdtemp(prefix="imp0430-stores-"))


def build_stores(root: Path, cls=SessionKeyedStore) -> dict:
    return {name: cls(name, root) for name in STORES}


def _import_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem + "_auditmod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def scan_store_dir(directory: Path) -> dict:
    """Scan a hooks directory for store declarations without running hooks."""
    out = {}
    directory = Path(directory)
    if not directory.is_dir():
        return out
    for name in STORES:
        p = directory / (name + ".py")
        if not p.is_file():
            out[name] = {"present": False, "key_shape": None, "repo_source": None,
                         "key_template": None}
            continue
        mod = _import_module(p)
        out[name] = {
            "present": True,
            "key_shape": getattr(mod, "KEY_SHAPE", None),
            "key_template": getattr(mod, "KEY_TEMPLATE", None),
            "repo_source": p.as_posix().replace(chr(92), "/"),
        }
    return out
