"""Downstream consumer of acquired workflow artifacts (WFA-0121)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wfa_injection_gate.corpus import CANARY, CLEAN_MECH
from wfa_injection_gate.gate import B64_RE, IGNORE_RE, ROLE_RE, is_bundled_agent_config

MECH_RE = re.compile(r"mechanism_id[\"']?\s*[:=]\s*[\"']([^\"']+)")
STAGE_RE = re.compile(r"\bstage[\"']?\s*[:=]\s*[\"']([^\"']+)")


def extract_tokens(text: str) -> tuple[set[str], set[str]]:
    mechs = set(MECH_RE.findall(text))
    stages = set(STAGE_RE.findall(text))
    return mechs, stages


@dataclass
class ConsumeResult:
    canary_obeyed: bool = False
    config_autoload: bool = False
    mechanisms: list[str] = field(default_factory=list)
    stages: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "canary_obeyed": self.canary_obeyed,
            "config_autoload": self.config_autoload,
            "mechanisms": list(self.mechanisms),
            "stages": list(self.stages),
            "findings": list(self.findings),
        }


def consume_text(text: str, relpath: str = "") -> ConsumeResult:
    mechs, stages = extract_tokens(text)
    if not mechs and CLEAN_MECH in text:
        mechs.add(CLEAN_MECH)
    canary = CANARY in text or ROLE_RE.search(text) is not None or IGNORE_RE.search(text) is not None
    b64 = B64_RE.search(text) is not None
    autoload = is_bundled_agent_config(relpath)
    return ConsumeResult(
        canary_obeyed=bool(canary or b64 or autoload),
        config_autoload=autoload,
        mechanisms=sorted(mechs),
        stages=sorted(stages),
        findings=["canary"] if canary else [],
    )


def consume_tree(root: Path) -> ConsumeResult:
    root = Path(root)
    acc = ConsumeResult()
    if root.is_file():
        files = [root]
        base = root.parent
    else:
        files = [p for p in root.rglob("*") if p.is_file()]
        base = root
    for path in files:
        rel = path.relative_to(base).as_posix() if path != root else path.name
        one = consume_text(path.read_text(encoding="utf-8", errors="replace"), rel)
        acc.canary_obeyed = acc.canary_obeyed or one.canary_obeyed
        acc.config_autoload = acc.config_autoload or one.config_autoload
        acc.mechanisms = sorted(set(acc.mechanisms) | set(one.mechanisms))
        acc.stages = sorted(set(acc.stages) | set(one.stages))
        acc.findings.extend(one.findings)
    return acc
