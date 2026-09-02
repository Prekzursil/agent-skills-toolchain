"""Two-part test: named settling experiment + owner-visible impact."""
from __future__ import annotations

import re
from typing import Any

VACUOUS_EXPERIMENT = re.compile(
    r"\binvestigate\s+further\b|"
    r"\blook\s+into\s+it\b|"
    r"\bneeds?\s+more\s+(research|investigation)\b|"
    r"^\s*(tbd|todo|follow[- ]up)\s*$",
    re.IGNORECASE,
)

OWNER_PHRASE = re.compile(
    r"\b(owner|user|customer|customers|release|ship(?:ped|ping)?|delay|"
    r"cost|outage|product|schedule|production|data\s+loss)\b|"
    r"cannot tell|can't tell",
    re.IGNORECASE,
)

JARGON_TOKEN = re.compile(
    r"detector[- ]controlled|both[- ]states?|fingerprint|predicate:absent|"
    r"\bG-1\b|\bADV\b|subagent|worktree|PYTHONDONTWRITEBYTECODE|"
    r"lane residual|probe-exit|named-probe|completion-sentinel|"
    r"jsonl|unit_id|predicate:absent",
    re.IGNORECASE,
)

SETTLE_WORD = re.compile(
    r"stdout|stderr|exit\s*code|contains|equals|sha256|SETTLED|must\s+be|would settle",
    re.IGNORECASE,
)

RUNNABLE = re.compile(
    r"\bpython3\b|\bpython\b|\bbash\b|\bpytest\b|\.py\b|\.sh\b",
    re.IGNORECASE,
)


def _labeled(text: str, label: str) -> str:
    m = re.search(rf"(?im)^\s*{re.escape(label)}\s*:\s*(.+)$", text)
    if m:
        return m.group(1).strip().strip("`")
    m = re.search(rf"(?i)\b{re.escape(label)}\s*:\s*([^;\n]+)", text)
    return m.group(1).strip().strip("`") if m else ""


def experiment_parts(experiment: Any) -> dict[str, str]:
    if isinstance(experiment, dict):
        return {
            "command": str(
                experiment.get("command") or experiment.get("cmd") or ""
            ).strip(),
            "input": str(
                experiment.get("input")
                or experiment.get("input_path")
                or experiment.get("fixture")
                or ""
            ).strip(),
            "observation": str(
                experiment.get("observation")
                or experiment.get("observe")
                or experiment.get("would_settle")
                or ""
            ).strip(),
            "raw": str(
                experiment.get("raw")
                or experiment.get("text")
                or " ".join(
                    str(experiment.get(k) or "")
                    for k in ("command", "input", "observation")
                )
            ).strip(),
        }
    text = str(experiment or "").strip()
    return {
        "command": _labeled(text, "command"),
        "input": _labeled(text, "input"),
        "observation": _labeled(text, "observation") or _labeled(text, "observe"),
        "raw": text,
    }


def named_experiment(experiment: Any) -> dict[str, Any]:
    """PASS only when command, input, and settling observation are all named.

    'investigate further' fails regardless of surrounding wording.
    """
    parts = experiment_parts(experiment)
    blob = " ".join(
        [
            parts["command"],
            parts["input"],
            parts["observation"],
            parts["raw"],
        ]
    )
    if VACUOUS_EXPERIMENT.search(parts["raw"]) or VACUOUS_EXPERIMENT.search(
        parts["command"]
    ):
        return {
            "pass": False,
            "reason": "vacuous-investigate-further",
            **parts,
        }
    missing = [
        name
        for name in ("command", "input", "observation")
        if not parts[name]
    ]
    if missing:
        return {
            "pass": False,
            "reason": "missing-" + ",".join(missing),
            **parts,
        }
    if not RUNNABLE.search(parts["command"]):
        return {"pass": False, "reason": "command-not-runnable", **parts}
    if not SETTLE_WORD.search(parts["observation"]):
        return {"pass": False, "reason": "observation-does-not-settle", **parts}
    if len(blob) < 24:
        return {"pass": False, "reason": "too-short", **parts}
    return {"pass": True, "reason": "named-command-input-observation", **parts}


def owner_visible_impact(impact: Any) -> dict[str, Any]:
    """PASS only when a non-agent reader can see a concrete consequence."""
    text = str(impact or "").strip()
    if not text:
        return {"pass": False, "reason": "empty", "text": text}
    has_owner = bool(OWNER_PHRASE.search(text))
    jargon_hits = len(JARGON_TOKEN.findall(text))
    if not has_owner:
        return {
            "pass": False,
            "reason": "jargon-or-no-owner-consequence",
            "text": text,
            "jargon_hits": jargon_hits,
        }
    words = re.findall(r"[A-Za-z0-9:-]+", text)
    if words and jargon_hits >= max(3, len(words) // 2) and jargon_hits >= 3:
        return {
            "pass": False,
            "reason": "jargon-dominant",
            "text": text,
            "jargon_hits": jargon_hits,
        }
    return {
        "pass": True,
        "reason": "owner-facing-consequence",
        "text": text,
        "jargon_hits": jargon_hits,
    }


def classify(experiment: Any, impact: Any) -> dict[str, Any]:
    named = named_experiment(experiment)
    owner = owner_visible_impact(impact)
    fails: list[str] = []
    if not named["pass"]:
        fails.append("named-experiment")
    if not owner["pass"]:
        fails.append("owner-visible-impact")
    return {
        "named_experiment": named,
        "owner_visible_impact": owner,
        "pass_both": not fails,
        "fails": fails,
    }


experiment_parts = experiment_parts
named_experiment = named_experiment
owner_visible_impact = owner_visible_impact
