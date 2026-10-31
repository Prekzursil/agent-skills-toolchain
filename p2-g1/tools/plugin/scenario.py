"""Host-or-fixture pair for live-versus-repo drift classification."""
from __future__ import annotations

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PROBE_SCENARIO = (
    REPO / "command-center" / "p2-wave" / "probes" / "IMP-0034" / "scenario.py"
)
NAMED_LIVE_LARGER = (
    "common/owner-ops-authorization.md",
    "common/performance.md",
    "common/security.md",
)


def _load():
    spec = importlib.util.spec_from_file_location(
        "imp0034_estate_scenario", PROBE_SCENARIO
    )
    if spec is None or spec.loader is None:
        raise ImportError(str(PROBE_SCENARIO))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def resolve_pair() -> dict:
    return _load().resolve_pair()


def host_candidates():
    return _load().host_candidates()


def host_pair():
    return _load().host_pair()


def build_estate_fixtures() -> dict:
    return _load().build_estate_fixtures()


from dataclasses import dataclass, field


@dataclass
class Projection:
    owned: list[str] = field(default_factory=list)

    def owned_relpaths(self) -> list[str]:
        return list(self.owned)


@dataclass
class SeedHome:
    home: Path
    projection: Projection
    user_files: list[str]

    def resolve(self) -> Path:
        return Path(self.home).resolve()

    def exists(self) -> bool:
        return Path(self.home).exists()

    def rglob(self, pattern: str):
        return Path(self.home).rglob(pattern)

    def is_file(self) -> bool:
        return Path(self.home).is_file()

    def is_dir(self) -> bool:
        return Path(self.home).is_dir()

    def __fspath__(self) -> str:
        return str(self.home)

    def __truediv__(self, other):
        return Path(self.home) / other

    def __str__(self) -> str:
        return str(self.home)


def seed_home(home: Path) -> SeedHome:
    """Seed a plugin home with owned, user, and foreign files for uninstall probes."""
    home = Path(home)
    home.mkdir(parents=True, exist_ok=True)
    owned = [
        "plugins/demo/plugin.json",
        "plugins/demo/run.py",
        ".ast/plugin-state.json",
    ]
    user_files = ["user-data/notes.txt"]
    foreign = ["other/keep.bin", "shared/config.ini"]
    for rel in owned + user_files + foreign:
        path = home / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"seed:{rel}\n", encoding="utf-8")
    return SeedHome(home=home, projection=Projection(owned=owned), user_files=user_files)


def write_payload(scratch: Path, version: str) -> Path:
    """Throwaway plugin source tree used by dry-run fidelity probes."""
    import json

    root = Path(scratch) / f"payload-{version}"
    pkg = root / "demo"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "plugin.json").write_text(
        json.dumps({"name": "demo", "version": version}, indent=2) + "\n",
        encoding="utf-8",
    )
    (pkg / "run.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    return root
