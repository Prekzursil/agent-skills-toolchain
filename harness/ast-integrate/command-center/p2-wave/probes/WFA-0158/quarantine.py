"""Ingestion-boundary quarantine for third-party archaeology artifacts.

Workflow definitions, transcripts and README text pulled in during
archaeology are untrusted DATA. Later stages render them into prompts.
This module is the live ingestion path for that boundary:

  ingest -> tag detected shapes -> neutralize fence/role markers ->
  render-as-data (never as INSTRUCTION) -> split channels -> execute
  only the instruction channel.

A quarantine that drops the candidate fails: legitimate content must
survive in the data channel. Detection tags are an audit trail; the
fence is the control that stops an embedded instruction from executing.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Callable

from payloads import (
    LEGIT_MARKER,
    LEGIT_NAME,
    LEGIT_STEPS,
    OPERATOR,
    PAYLOADS,
    hostile,
)

FENCE_OPEN_PREFIX = "<<<UNTRUSTED-DATA"
FENCE_CLOSE_PREFIX = "<<<END-UNTRUSTED-DATA"
INSTRUCTION_HEAD = "### INSTRUCTION"
DATA_HEAD = "### DATA"
CANARY_RE = re.compile(r"WFA0158_CANARY_[A-Z0-9]+")

NEUTRALIZE_PAIRS: tuple[tuple[str, str], ...] = (
    (FENCE_CLOSE_PREFIX, "[[NEUTRALIZED:FENCE-CLOSE]]"),
    ("<|im_start|>", "[[NEUTRALIZED:CHATML-IM-START]]"),
    ("<|im_end|>", "[[NEUTRALIZED:CHATML-IM-END]]"),
    ('"role": "system"', '"role": "[[NEUTRALIZED:SYSTEM-ROLE]]"'),
    ('"role":"system"', '"role":"[[NEUTRALIZED:SYSTEM-ROLE]]"'),
    ("<!--", "[[NEUTRALIZED:HTML-COMMENT-OPEN]]"),
)

Splitter = Callable[[str], dict[str, str]]


def _frontmatter_system(text: str) -> bool:
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    if end < 0:
        return False
    head = text[3:end]
    return bool(re.search(r"(?im)^system\s*:", head))


def detect_shapes(text: str) -> list[str]:
    """Audit tags. Not the fence. A miss here must not unfence the body."""
    tags: list[str] = []
    low = text.lower()
    if "ignore previous instructions" in low or "ignore all previous" in low:
        tags.append("direct-override")
    if "<!--" in text:
        tags.append("html-comment")
    if re.search(r'"role"\s*:\s*"system"', text):
        tags.append("json-role-system")
    if "<|im_start|>" in text or "<|im_end|>" in text:
        tags.append("chatml-im-token")
    if FENCE_CLOSE_PREFIX in text:
        tags.append("fence-break")
    if _frontmatter_system(text):
        tags.append("yaml-frontmatter-system")
    return tags


def neutralize(text: str) -> tuple[str, list[str]]:
    """Strip instruction potency of fence/role markers; keep bytes as data."""
    out = text
    actions: list[str] = []
    for src, dst in NEUTRALIZE_PAIRS:
        if src in out:
            out = out.replace(src, dst)
            actions.append(src)
    return out, actions


def _candidate_id(origin: str, body: str) -> str:
    digest = hashlib.sha256(f"{origin}\n{body}".encode("utf-8")).hexdigest()[:12]
    return f"ing-{digest}"


def ingest(payload: dict[str, Any], *, drop: bool = False) -> dict[str, Any]:
    """Ingest one archaeology candidate. drop=True is the failing mutant."""
    body = str(payload["body"])
    origin = str(payload["origin"])
    kind = str(payload["kind"])
    cid = _candidate_id(origin, body)
    if drop:
        return {
            "id": cid,
            "payload_id": payload["id"],
            "kind": kind,
            "origin": origin,
            "dropped": True,
            "tags": ["dropped"],
            "neutralize_actions": [],
            "raw": body,
            "body": "",
            "canary": payload.get("canary"),
        }
    tags = detect_shapes(body)
    if "untrusted" not in tags:
        tags = ["untrusted", *tags]
    cleaned, actions = neutralize(body)
    return {
        "id": cid,
        "payload_id": payload["id"],
        "kind": kind,
        "origin": origin,
        "dropped": False,
        "tags": tags,
        "neutralize_actions": actions,
        "raw": body,
        "body": cleaned,
        "canary": payload.get("canary"),
    }


def render_prompt(
    operator: str,
    candidates: list[dict[str, Any]],
    *,
    fence: bool = True,
) -> str:
    """Assemble the downstream prompt. fence=False is the both-states mutant."""
    kept = [c for c in candidates if not c.get("dropped")]
    if not fence:
        chunks = [INSTRUCTION_HEAD, operator.rstrip(), ""]
        for c in kept:
            chunks.append(f"# ingested {c['origin']}")
            chunks.append(c["raw"].rstrip())
            chunks.append("")
        return "\n".join(chunks).rstrip() + "\n"
    chunks = [INSTRUCTION_HEAD, operator.rstrip(), "", DATA_HEAD, ""]
    for c in kept:
        tags = ",".join(c.get("tags") or ["untrusted"])
        chunks.append(
            f"{FENCE_OPEN_PREFIX} id={c['id']} kind={c['kind']} "
            f"origin={c['origin']} tags={tags}>>>"
        )
        chunks.append(c["body"].rstrip())
        chunks.append(f"{FENCE_CLOSE_PREFIX} id={c['id']}>>>")
        chunks.append("")
    return "\n".join(chunks).rstrip() + "\n"


def split_channels(prompt: str) -> dict[str, str]:
    """Author splitter: INSTRUCTION vs DATA headings."""
    text = prompt.replace("\r\n", "\n")
    if DATA_HEAD in text:
        pre, post = text.split(DATA_HEAD, 1)
        inst = pre.replace(INSTRUCTION_HEAD, "", 1).strip()
        data = post.strip()
    else:
        inst = text.replace(INSTRUCTION_HEAD, "", 1).strip()
        data = ""
    return {"instruction": inst, "data": data}


def split_channels_independent(prompt: str) -> dict[str, str]:
    """Reviewer splitter: first fence marker, not the markdown headings.

    Mechanically independent of split_channels: it never looks at
    '### INSTRUCTION' / '### DATA'.
    """
    text = prompt.replace("\r\n", "\n")
    idx = text.find(FENCE_OPEN_PREFIX)
    if idx < 0:
        return {"instruction": text.strip(), "data": ""}
    return {
        "instruction": text[:idx].strip(),
        "data": text[idx:].strip(),
    }


def canaries_in(text: str) -> list[str]:
    return sorted(set(CANARY_RE.findall(text or "")))


def execute_instruction_channel(instruction: str) -> list[str]:
    """Downstream stage: only the instruction channel is executable."""
    return canaries_in(instruction)


def content_survived(data_text: str, raw: str | None = None) -> bool:
    blob = data_text or ""
    if LEGIT_MARKER not in blob:
        return False
    if LEGIT_NAME not in blob:
        return False
    return all(step in blob for step in LEGIT_STEPS)


def run_trial(
    payload: dict[str, Any],
    *,
    fence: bool = True,
    drop: bool = False,
    splitter: Splitter = split_channels,
) -> dict[str, Any]:
    cand = ingest(payload, drop=drop)
    prompt = render_prompt(OPERATOR, [cand], fence=fence)
    ch = splitter(prompt)
    fired = execute_instruction_channel(ch["instruction"])
    canary = payload.get("canary")
    in_inst = canaries_in(ch["instruction"])
    in_data = canaries_in(ch["data"])
    survived = content_survived(ch["data"])
    neutralized = True
    if canary:
        neutralized = canary not in in_inst and canary not in fired
        if not fence:
            neutralized = canary in in_inst
    if drop:
        survived = content_survived(ch["data"])
        neutralized = bool(canary) and canary not in in_inst
    return {
        "payload_id": payload["id"],
        "kind": payload["kind"],
        "origin": payload["origin"],
        "canary": canary,
        "dropped": bool(cand["dropped"]),
        "tags": list(cand["tags"]),
        "neutralize_actions": list(cand["neutralize_actions"]),
        "fence": fence,
        "prompt_verbatim": prompt,
        "instruction_channel": ch["instruction"],
        "data_channel": ch["data"],
        "canary_in_instruction": canary in in_inst if canary else False,
        "canary_in_data": canary in in_data if canary else False,
        "fired_canaries": fired,
        "neutralized": neutralized if canary else True,
        "content_survived": survived,
        "candidate_id": cand["id"],
    }


def run_campaign(
    *,
    fence: bool = True,
    drop: bool = False,
    splitter: Splitter = split_channels,
) -> list[dict[str, Any]]:
    return [
        run_trial(p, fence=fence, drop=drop, splitter=splitter) for p in PAYLOADS
    ]


def verdict_ok(trial: dict[str, Any]) -> bool:
    if trial["dropped"]:
        return False
    if not trial["content_survived"]:
        return False
    canary = trial.get("canary")
    if canary and trial["canary_in_instruction"]:
        return False
    if canary and canary in trial["fired_canaries"]:
        return False
    if canary and not trial["canary_in_data"]:
        # Reachability: the payload must actually arrive in DATA.
        return False
    return True


# Re-export for probes that import the payload helpers from this module.
hostile_payloads = hostile
all_payloads = PAYLOADS
