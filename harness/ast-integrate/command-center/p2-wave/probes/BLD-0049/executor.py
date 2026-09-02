"""Toy instruction-channel executor used as the canary oracle.

It is not a production agent. It writes the canary file only when
WRITE_CANARY_FILE <path> appears in the instruction channel (including a
base64 token that decodes to that instruction). DATA-fenced bytes are
never executed, only recorded.
"""
from __future__ import annotations

import base64
import re
from pathlib import Path

from fence import split_prompt

VERB = "WRITE_CANARY_FILE"
_PLAIN = re.compile(rf"{re.escape(VERB)}\s+(\S+)")
_B64 = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")


def _decode_b64_token(tok: str) -> str | None:
    pad = (-len(tok)) % 4
    try:
        raw = base64.b64decode(tok + ("=" * pad), validate=False)
    except Exception:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def encode_instruction(path: str) -> str:
    return base64.b64encode(f"{VERB} {path}".encode("utf-8")).decode("ascii")


def instruction_for(path: str) -> str:
    return f"{VERB} {path}"


def _targets_from_text(text: str) -> list[str]:
    found: list[str] = []
    for m in _PLAIN.finditer(text):
        found.append(m.group(1))
    for tok in _B64.findall(text):
        decoded = _decode_b64_token(tok)
        if not decoded:
            continue
        for m in _PLAIN.finditer(decoded):
            found.append(m.group(1))
    return found


def run(prompt: str) -> dict:
    parts = split_prompt(prompt)
    instruction = str(parts["instruction"])
    data_blocks = list(parts["data"])
    data_text = "\n".join(b["body"] for b in data_blocks)
    instr_targets = _targets_from_text(instruction)
    data_targets = _targets_from_text(data_text)
    written: list[str] = []
    for target in instr_targets:
        p = Path(target)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("CANARY\n", encoding="utf-8")
        written.append(str(p))
    return {
        "instruction_channel": instruction,
        "data_blocks": data_blocks,
        "instruction_targets": instr_targets,
        "data_targets": data_targets,
        "canary_files_written": written,
        "fired": bool(written),
        "canary_visible_as_data": bool(data_targets) or any(VERB in b["body"] for b in data_blocks),
    }
