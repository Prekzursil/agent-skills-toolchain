"""Named health probes and fixture trees for IMP-0043."""
from __future__ import annotations

from pathlib import Path

from health_check import HealthContext, ProbeResult

REQUIRED_PROBE_IDS = (
    "hooks_loaded",
    "skills_present",
    "interpreter_ok",
)


class _FileProbe:
    def __init__(self, probe_id: str, rel: str) -> None:
        self.probe_id = probe_id
        self.rel = rel
        self.both_states = True

    def run(self, ctx: HealthContext) -> ProbeResult:
        path = Path(ctx.root) / self.rel
        if path.is_file():
            return ProbeResult(self.probe_id, "SUCCESS")
        return ProbeResult(self.probe_id, "FAILED", reason=f"missing {self.rel}")


def default_probes() -> list[_FileProbe]:
    return [
        _FileProbe("hooks_loaded", "hooks.ok"),
        _FileProbe("skills_present", "skills.ok"),
        _FileProbe("interpreter_ok", "interpreter.ok"),
    ]


def plant_healthy_tree(root: Path) -> None:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for name in ("hooks.ok", "skills.ok", "interpreter.ok"):
        (root / name).write_text("ok\n", encoding="utf-8")
