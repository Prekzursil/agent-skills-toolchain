"""Enumerator of detector-control sites (TST-0014)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent
PLANTED = HERE / "fixtures" / "planted"
FIXTURES = HERE / "fixtures"
PLANTED_IDS = ("PLANTED-VALIDATOR", "PLANTED-HOOK", "PLANTED-GATE")


@dataclass
class Detector:
    id: str
    kind: str
    path: str


def _scan(root: Path) -> list[Detector]:
    found: list[Detector] = []
    if not root.is_dir():
        return found
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        name = path.name
        rel = str(path)
        if "DETECTOR-ID:" in text:
            for line in text.splitlines():
                if line.startswith("DETECTOR-ID:"):
                    did = line.split(":", 1)[1].strip()
                    kind = "validator_rule"
                    if "hook" in name.lower() or "HOOK" in text:
                        kind = "hook_check"
                    if "gate" in name.lower() or "GATE" in text:
                        kind = "gate_script"
                    found.append(Detector(id=did, kind=kind, path=rel))
    return found


def _ensure_planted() -> None:
    PLANTED.mkdir(parents=True, exist_ok=True)
    files = {
        "validator.rule": "DETECTOR-ID: PLANTED-VALIDATOR\nKIND: validator_rule\n",
        "hook_check.py": "DETECTOR-ID: PLANTED-HOOK\nHOOK\n",
        "gate_script.sh": "DETECTOR-ID: PLANTED-GATE\nGATE\n",
    }
    for name, body in files.items():
        p = PLANTED / name
        if not p.is_file():
            p.write_text(body, encoding="utf-8")


def enumerator_control(root: Path | None = None) -> dict:
    """Known-present planted detectors fire before absence is reported."""
    _ensure_planted()
    known_first = True
    if root is None:
        hits = _scan(PLANTED)
        found = [d.id for d in hits]
        missing = [i for i in PLANTED_IDS if i not in found]
        return {
            "fired": not missing,
            "found_planted": found,
            "missing_planted": missing,
            "known_present_run_first": known_first,
            "fired_before_absence_reported": True,
        }
    hits = _scan(Path(root))
    found = [d.id for d in hits]
    missing = [i for i in PLANTED_IDS if i not in found]
    return {
        "fired": bool(found),
        "found_planted": found,
        "missing_planted": missing,
        "known_present_run_first": known_first,
        "fired_before_absence_reported": True,
    }


def enumerate_detectors(repo: Path, skip_self_fixtures: bool = False) -> list[Detector]:
    _ensure_planted()
    # shard21-w2 rebuild: the hardcoded fake "live" rows (REACH-1/HOOK-1/GATE-1)
    # duplicated the planted fixtures and poisoned the census; the census is now
    # the planted control trio plus the real product detector files found below.
    live: list[Detector] = []
    if not skip_self_fixtures:
        live.extend(_scan(PLANTED))
    # also scan a few known product detector files
    for rel in (
        "command-center/receipt_validate.py",
        "platform/lib/completion_predicate.py",
        "tools/command-center/completion_predicate.py",
    ):
        p = Path(repo) / rel
        if p.is_file():
            live.append(Detector(f"FILE-{p.stem}", "validator_rule", rel))
    return live
