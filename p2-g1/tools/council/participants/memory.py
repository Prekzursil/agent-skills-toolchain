"""Per-participant memory policy for council briefs (IMP-0350)."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


class MemoryPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class MemoryPolicy:
    memory_enabled: bool
    import_conclusion: bool

    def as_dict(self) -> dict[str, bool]:
        return {
            "memory_enabled": self.memory_enabled,
            "import_conclusion": self.import_conclusion,
        }


@dataclass
class PromptItem:
    participant_id: str
    policy: MemoryPolicy
    text: str


@dataclass
class ScanResult:
    fired: bool
    hits: list
    hit_count: int

    def as_dict(self) -> dict[str, Any]:
        return {"fired": self.fired, "hits": list(self.hits), "hit_count": self.hit_count}

    def __getitem__(self, key: str) -> Any:
        return self.as_dict()[key]


def resolve_policy(spec: dict[str, Any], participant: dict[str, Any]) -> MemoryPolicy:
    raw = participant.get("memory", spec.get("memory_default", "off"))
    if isinstance(raw, dict):
        enabled = bool(raw.get("enabled") or raw.get("memory_enabled"))
        imported = bool(raw.get("import_conclusion"))
        return MemoryPolicy(enabled, imported)
    if raw in {"off", False, "disabled", "none"}:
        return MemoryPolicy(False, False)
    if raw in {"on", True, "enabled"}:
        return MemoryPolicy(True, False)
    if raw in {"import", "import_conclusion"}:
        return MemoryPolicy(True, True)
    raise MemoryPolicyError(f"unrecognized memory flag {raw!r}")


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[A-Za-z0-9-]+", text.lower()) if len(t) > 2}


def _similarity(a: str, b: str) -> float:
    if b and b in a:
        return 0.92
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _conclusion_texts(conclusions) -> list[str]:
    out: list[str] = []
    for item in conclusions or []:
        if isinstance(item, dict):
            text = str(item.get("conclusion") or "")
        else:
            text = str(item)
        if text:
            out.append(text)
    return out


def scan_prompt_for_conclusions(prompt: str, conclusions) -> ScanResult:
    texts = _conclusion_texts(conclusions)
    hits = [c for c in texts if c and c in prompt]
    return ScanResult(bool(hits), hits, len(hits))


def render_delivered_prompt(
    *,
    participant: dict[str, Any],
    spec: dict[str, Any],
    prior_councils: list[dict[str, Any]],
    current_task: dict[str, Any],
    policy: MemoryPolicy | None = None,
) -> PromptItem:
    policy = policy or resolve_policy(spec, participant)
    question = spec.get("question") or current_task.get("question") or ""
    notes = current_task.get("notes") or ""
    lines = [
        f"Council: {spec.get('id') or 'current'}",
        f"Question: {question}",
        f"Task notes: {notes}",
        "Do not inherit a prior conclusion unless import_conclusion is set.",
    ]
    if policy.memory_enabled:
        for prior in prior_councils:
            lines.append(f"prior_council_id={prior.get('council_id')}")
            lines.append(f"prior_date={prior.get('date')}")
            if policy.import_conclusion:
                conclusion = str(prior.get("conclusion") or "")
                lines.append(f"PRIOR CONCLUSION: {conclusion}")
                lines.append(conclusion)
                lines.append(conclusion)
    text = "\n".join(lines)
    return PromptItem(str(participant.get("id") or ""), policy, text)


def render_roster_prompts(
    spec: dict[str, Any],
    priors: list[dict[str, Any]],
    task: dict[str, Any],
) -> list[PromptItem]:
    items = []
    for p in spec.get("participants") or []:
        policy = resolve_policy(spec, p)
        item = render_delivered_prompt(
            participant=p,
            spec=spec,
            prior_councils=priors,
            current_task=task,
            policy=policy,
        )
        items.append(item)
    return items


def compare_on_versus_off(
    spec: dict[str, Any],
    template: dict[str, Any],
    priors: list[dict[str, Any]],
    task: dict[str, Any],
) -> dict[str, Any]:
    conclusion = priors[0]["conclusion"] if priors else ""
    off_p = {**template, "id": "seat-measure", "memory": "off"}
    on_p = {**template, "id": "seat-measure", "memory": "on"}
    imp_p = {
        **template,
        "id": "seat-measure",
        "memory": {"enabled": True, "import_conclusion": True},
    }
    off = render_delivered_prompt(
        participant=off_p, spec=spec, prior_councils=priors, current_task=task
    ).text
    on = render_delivered_prompt(
        participant=on_p, spec=spec, prior_councils=priors, current_task=task
    ).text
    imported = render_delivered_prompt(
        participant=imp_p, spec=spec, prior_councils=priors, current_task=task
    ).text
    off_sim = _similarity(off, conclusion)
    on_sim = _similarity(on, conclusion)
    imp_sim = _similarity(imported, conclusion)
    return {
        "memory_off": {
            "similarity": off_sim,
            "prompt": off,
            "prompt_scan": scan_prompt_for_conclusions(off, [conclusion]).as_dict(),
        },
        "memory_on_default": {
            "similarity": on_sim,
            "prompt": on,
            "prompt_scan": scan_prompt_for_conclusions(on, [conclusion]).as_dict(),
        },
        "memory_on_import_conclusion": {
            "similarity": imp_sim,
            "prompt": imported,
            "prompt_scan": scan_prompt_for_conclusions(imported, [conclusion]).as_dict(),
        },
        "delta_import_minus_off": imp_sim - off_sim,
        "independence_preserved_by_default": conclusion not in off and conclusion not in on,
        "import_conclusion_voids_independence": conclusion in imported,
    }


def enforce_memory_scope(
    roster: list[PromptItem], priors: list[dict[str, Any]]
) -> dict[str, Any]:
    conclusions = [p.get("conclusion") or "" for p in priors]
    violations = []
    for item in roster:
        if item.policy.import_conclusion:
            continue
        for c in conclusions:
            if c and c in item.text:
                violations.append(
                    {
                        "participant_id": item.participant_id,
                        "kind": "cross-seat-conclusion-leak",
                    }
                )
    return {"ok": not violations, "violations": violations}


def plant_conclusion_leak(prompt: str, conclusion: str) -> str:
    return prompt + "\nPLANTED:" + conclusion
