"""PATH shim that logs helper execs. Text-grep of a script is not this detector."""
from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from scenario import COUNTED_HELPERS, HERE

KNOWN_SPAWN = "tst0107-probe"
WRAPPER_BODY = """\
import json
import os
import sys

name = os.path.basename(sys.argv[0])
log = os.environ["TST0107_SPAWN_LOG"]
reals = json.loads(open(os.environ["TST0107_REAL_MAP"], encoding="utf-8").read())
real = reals[name]
with open(log, "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"name": name, "argv": sys.argv[1:]}) + "\\n")
os.execv(real, [real, *sys.argv[1:]])
"""


class SpawnShim:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.log_path = root / "spawns.jsonl"
        self.map_path = root / "reals.json"
        self.bin_dir = root / "bin"
        self.reals: dict[str, str] = {}

    def env(self, base: dict[str, str] | None = None) -> dict[str, str]:
        env = dict(base if base is not None else os.environ)
        env["PATH"] = str(self.bin_dir) + os.pathsep + env.get("PATH", "")
        env["TST0107_SPAWN_LOG"] = str(self.log_path)
        env["TST0107_REAL_MAP"] = str(self.map_path)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env

    def entries(self) -> list[dict]:
        if not self.log_path.is_file():
            return []
        rows = []
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows

    def count(self, name: str | None = None) -> int:
        rows = self.entries()
        if name is None:
            return len(rows)
        return sum(1 for row in rows if row.get("name") == name)

    def nested_helper_count(self) -> int:
        counted = set(COUNTED_HELPERS)
        return sum(1 for row in self.entries() if row.get("name") in counted)


def _install_wrapper(shim: SpawnShim, name: str, real: Path) -> None:
    wrapper = shim.bin_dir / name
    wrapper.write_text(f"#!{sys.executable}\n{WRAPPER_BODY}", encoding="utf-8")
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    shim.reals[name] = str(real)


def _known_spawn_binary(root: Path) -> Path:
    src = HERE / "fixtures" / "bin" / KNOWN_SPAWN
    dest = root / "real" / KNOWN_SPAWN
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dest)
    dest.chmod(dest.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return dest


@contextmanager
def path_shim() -> Iterator[SpawnShim]:
    tmp = Path(tempfile.mkdtemp(prefix="tst0107-shim-"))
    shim = SpawnShim(tmp)
    shim.bin_dir.mkdir(parents=True, exist_ok=True)
    shim.log_path.write_text("", encoding="utf-8")
    _install_wrapper(shim, KNOWN_SPAWN, _known_spawn_binary(tmp))
    for name in COUNTED_HELPERS:
        if name == KNOWN_SPAWN:
            continue
        real = shutil.which(name)
        if real:
            _install_wrapper(shim, name, Path(real))
    shim.map_path.write_text(json.dumps(shim.reals, indent=0), encoding="utf-8")
    try:
        yield shim
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
