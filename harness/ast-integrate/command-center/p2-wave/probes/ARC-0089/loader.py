"""Turn-zero load instrument for the ARC-0089 skill contract.

This is a measurement of what the loader PUTS into the turn-zero context,
not a classifier that looks at frontmatter and guesses. Frontmatter is an
input to the loader; the output is the context bag. Probe 2 reads that bag.

Load-mode switch (the measured inversion, IMP-0387 / RES-0010):
  * `paths` key ABSENT (including a file with no frontmatter at all)
    -> ALWAYS-ON: the full body is injected at turn zero.
  * `paths` key PRESENT (even `paths: ["**/*"]`, even an empty list)
    -> LAZY: turn zero keeps only the router index card (name + description).
      The body is injected later, only after a matching path is touched.

Adding `paths` therefore DEMOTES a file. It does not arm it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from frontmatter import paths_key_present, split_frontmatter
from globs import any_match

MEASUREMENT_COMMAND = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0089/probe2_load_semantics.py"
)
INSTRUMENT = "turn0-context-bag (injected body bytes, not a frontmatter classifier)"
ROUTER_FIELDS = ("name", "description")


@dataclass
class Capability:
    cap_id: str
    rel_path: str
    kind: str
    frontmatter: dict[str, Any] | None
    body: str
    source_text: str

    @property
    def paths_present(self) -> bool:
        return paths_key_present(self.frontmatter)

    @property
    def load_mode(self) -> str:
        return "LAZY" if self.paths_present else "ALWAYS-ON"

    @property
    def name(self) -> str:
        if isinstance(self.frontmatter, dict) and self.frontmatter.get("name"):
            return str(self.frontmatter["name"])
        return self.cap_id

    @property
    def description(self) -> str:
        if isinstance(self.frontmatter, dict) and self.frontmatter.get("description"):
            return str(self.frontmatter["description"])
        return ""

    @property
    def path_globs(self) -> list[str]:
        if not self.paths_present:
            return []
        raw = self.frontmatter.get("paths") if self.frontmatter else None
        if raw is None:
            return []
        if isinstance(raw, list):
            return [str(x) for x in raw]
        return [str(raw)]


@dataclass
class LoadTrace:
    """Direct measurement: bodies that actually landed in the context bag."""

    injected_bodies: dict[str, str] = field(default_factory=dict)
    index_cards: dict[str, dict[str, str]] = field(default_factory=dict)
    lazy_ids: list[str] = field(default_factory=list)
    always_on_ids: list[str] = field(default_factory=list)
    capabilities: list[Capability] = field(default_factory=list)
    touched_path: str | None = None
    measurement_command: str = MEASUREMENT_COMMAND
    instrument: str = INSTRUMENT

    def injected_ids(self) -> list[str]:
        return sorted(self.injected_bodies)

    def body_contains(self, cap_id: str, marker: str) -> bool:
        return marker in self.injected_bodies.get(cap_id, "")


def iter_capability_files(root: Path) -> list[Path]:
    files: list[Path] = []
    if not root.is_dir():
        return files
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".md", ".markdown"}:
            continue
        files.append(p)
    return files


def cap_id_for(root: Path, path: Path) -> str:
    rel = path.relative_to(root).as_posix()
    if path.name == "SKILL.md":
        return path.parent.name
    return rel.replace("/", ".")


def parse_capability(root: Path, path: Path) -> Capability:
    text = path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    rel = path.relative_to(root).as_posix()
    kind = "skill" if path.name == "SKILL.md" else "rule"
    return Capability(
        cap_id=cap_id_for(root, path),
        rel_path=rel,
        kind=kind,
        frontmatter=fm,
        body=body,
        source_text=text,
    )


def inventory(root: Path) -> list[Capability]:
    return [parse_capability(root, p) for p in iter_capability_files(root)]


def load_turn_zero(root: Path, touched_path: str | None = None) -> LoadTrace:
    """Run the loader and return the context bag.

    `touched_path` is the workspace-relative path the user just opened. At
    genuine turn zero it is None, so no lazy body can match.
    """
    caps = inventory(root)
    trace = LoadTrace(capabilities=caps, touched_path=touched_path)
    for cap in caps:
        trace.index_cards[cap.cap_id] = {
            "name": cap.name,
            "description": cap.description,
            "rel_path": cap.rel_path,
            "kind": cap.kind,
        }
        inject = False
        if cap.load_mode == "ALWAYS-ON":
            inject = True
            trace.always_on_ids.append(cap.cap_id)
        else:
            trace.lazy_ids.append(cap.cap_id)
            if touched_path and any_match(cap.path_globs, touched_path):
                inject = True
        if inject:
            trace.injected_bodies[cap.cap_id] = cap.body
    return trace


def as_record(trace: LoadTrace) -> dict[str, Any]:
    return {
        "kind": "turn-zero-load-trace",
        "instrument": trace.instrument,
        "measurement_command": trace.measurement_command,
        "touched_path": trace.touched_path,
        "injected_ids": trace.injected_ids(),
        "always_on_ids": sorted(trace.always_on_ids),
        "lazy_ids": sorted(trace.lazy_ids),
        "known_always_on_named": bool(trace.always_on_ids),
        "index_card_ids": sorted(trace.index_cards),
        "router_fields": list(ROUTER_FIELDS),
        "load_mode_control_field": "paths",
    }
