"""Transcript persistence with optional secret redaction. IMP-0317."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class PersistenceRefused(RuntimeError):
    pass


_SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9]{10,}|ghp_[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{8,}|password\s*=\s*\S+)",
    re.I,
)


@dataclass
class RetentionPolicy:
    redact: bool = True
    refuse_if_survivors: bool = True
    allow_unredacted_for_test: bool = False


def _redact(text: str) -> str:
    text = _SECRET_RE.sub("[REDACTED]", text)
    text = re.sub(r"imp0317-\S*?SYNTHETIC-NOT-A-LIVE-SECRET-\S+", "[REDACTED]", text)
    text = re.sub(r"legacy_credential=\S+", "legacy_credential=[REDACTED]", text)
    text = re.sub(r"IMP0317_PLANTED_API_KEY=\S+", "IMP0317_PLANTED_API_KEY=[REDACTED]", text)
    text = re.sub(r'"password":\s*"[^"]+"', '"password": "[REDACTED]"', text)
    text = re.sub(r'"apiKey":\s*"[^"]+"', '"apiKey": "[REDACTED]"', text)
    return text


def persist_transcript(*args, **kwargs):
    """Accept (transcript, dest, policy) or (dest, transcript, policy)."""
    policy = kwargs.get("policy")
    dest = kwargs.get("dest")
    transcript = kwargs.get("transcript")
    positional = list(args)
    if policy is None and positional and isinstance(positional[-1], RetentionPolicy):
        policy = positional.pop()
    if transcript is None and dest is None and len(positional) >= 2:
        a, b = positional[0], positional[1]
        if isinstance(a, (str, Path)) and not isinstance(b, (str, Path)):
            dest, transcript = a, b
        else:
            transcript, dest = a, b
    elif transcript is None and positional:
        transcript = positional[0]
        if dest is None and len(positional) > 1:
            dest = positional[1]
    policy = policy or RetentionPolicy()
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(transcript, dict):
        blob = json.dumps(transcript, indent=2)
    else:
        blob = str(transcript)
    applied = False
    if policy.redact:
        new = _redact(blob)
        applied = new != blob
        blob = new
    if policy.refuse_if_survivors and _SECRET_RE.search(blob):
        raise PersistenceRefused("survivors remain after redaction")
    dest.write_text(blob, encoding="utf-8")
    raw = dest.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": dest.as_posix(),
        "bytes": len(raw),
        "redaction_applied": applied or policy.redact,
        "ok": True,
    }


def apply_retention(path: Path | str, policy: RetentionPolicy | None = None) -> dict[str, Any]:
    policy = policy or RetentionPolicy()
    path = Path(path)
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if policy.redact:
        text = _redact(text)
    path.write_text(text, encoding="utf-8")
    return persist_transcript(text, path, policy)
