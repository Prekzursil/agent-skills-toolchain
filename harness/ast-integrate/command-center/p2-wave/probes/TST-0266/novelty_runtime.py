#!/usr/bin/env python3
"""Runtime novelty scorer + stopping-rule demotion (TST-0266 / B07 stand-in).

Bucket B07's production novelty scorer is not on this worktree. This module is
the calibratable runtime the unit measures: it maps an idea pair to
duplicate / variant / distinct and refuses to let novelty gate a stopping
rule when Cohen's kappa is below the pre-registered floor.

The floor is a constant, recorded before any gold-set scoring.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

# Pre-registered 2026-08-24, before gold-set scores were computed.
# Below this, novelty is advisory decoration and must not gate a stop.
KAPPA_FLOOR = 0.40
KAPPA_FLOOR_RECORDED_AT = "2026-08-24T00:00:00Z"
KAPPA_FLOOR_NOTE = (
    "Floor recorded before scoring. Chance-level kappa is a decoration; "
    "novelty may gate a stopping rule only when held-out kappa >= 0.40."
)

STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "in",
        "on",
        "for",
        "with",
        "to",
        "of",
        "and",
        "or",
        "from",
        "by",
        "as",
        "at",
        "into",
        "via",
        "over",
        "per",
        "each",
        "every",
        "all",
        "that",
        "this",
        "them",
        "their",
        "when",
        "before",
        "after",
        "using",
        "use",
        "used",
        "instead",
        "than",
        "not",
        "have",
        "has",
        "be",
        "is",
        "are",
        "was",
        "been",
    }
)

SYNONYM = {
    "store": "cache",
    "storing": "cache",
    "stored": "cache",
    "command-line": "cli",
    "commandline": "cli",
    "--verbose": "verbose",
    "debug": "verbose",
    "json-web-token": "jwt",
    "json-web-tokens": "jwt",
    "content-delivery-network": "cdn",
    "healthcheck": "health-check",
    "health": "health-check",
    "httponly": "http-only",
    "parameterised": "parameterized",
    "parameterize": "parameterized",
    "parameters": "parameterized",
    "parameter": "parameterized",
    "gzip-compress": "gzip",
    "throttle": "rate-limit",
    "throttling": "rate-limit",
    "tries": "attempt",
    "authentication": "login",
    "records": "log",
    "deliver": "serve",
    "publish": "document",
    "specification": "document",
    "pipeline": "ci",
    "decreases": "drop",
    "decrease": "drop",
    "apply": "run",
    "route": "endpoint",
    "expose": "ship",
    "expired": "expiry",
    "tokens": "token",
    "prior": "before",
    "archiving": "archival",
    "archive": "archival",
    "eagerly": "prefetch",
    "following": "next",
    "periodic": "schedule",
    "rotation": "rotate",
    "strip": "redact",
    "output": "log",
    "application": "app",
    "address": "ip",
    "source": "ip",
    "concatenating": "parameterized",
    "strings": "query",
    "bind": "parameterized",
    "check": "validate",
    "versions": "version",
    "shas": "sha",
    "action": "github",
    "actions": "github",
    "ci": "github",
    "marked": "httponly",
    "put": "cache",
    "write": "emit",
    "make": "fail",
    "inside": "in",
    "schema": "database",
    "requests": "request",
    "calls": "request",
    "retrying": "retry",
    "logging": "log",
    "option": "flag",
    "files": "asset",
    "static": "asset",
    "add": "index",
    "load": "prefetch",
}

DURATION_UNITS = frozenset(
    {"second", "seconds", "minute", "minutes", "hour", "hours", "day", "days", "ms", "week", "weeks"}
)
SIZE_UNITS = frozenset({"b", "kb", "mb", "gb", "tb", "byte", "bytes"})
RATE_UNITS = frozenset({"percent", "pct", "%"})
POLAR_PAIRS = (
    ("opt-in", "opt-out"),
    ("allow", "deny"),
    ("enable", "disable"),
    ("include", "exclude"),
    ("required", "optional"),
)


def _stem(word: str) -> str:
    w = word.lower()
    if w in SYNONYM:
        w = SYNONYM[w]
    for suf in ("ation", "tions", "ing", "ers", "ies", "ied", "ed", "ly", "es", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            if suf == "ies":
                w = w[: -len(suf)] + "y"
            else:
                w = w[: -len(suf)]
            break
    return SYNONYM.get(w, w)


def normalize_text(text: str) -> str:
    t = text.lower().replace("http-only", "httponly")
    t = t.replace("opt in", "opt-in").replace("opt out", "opt-out")
    t = t.replace("command line", "command-line")
    t = t.replace("json web tokens", "jwt").replace("json web token", "jwt")
    t = t.replace("content delivery network", "cdn")
    t = t.replace("rate limit", "rate-limit")
    t = t.replace("ip address", "ip")
    t = t.replace("health check", "health-check")
    t = t.replace("github actions", "github").replace("github action", "github")
    t = t.replace("commit shas", "sha").replace("commit sha", "sha")
    t = re.sub(r"[^a-z0-9.\-%]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def content_tokens(text: str) -> list[str]:
    return [w for w in normalize_text(text).split() if w not in STOP]


def is_scoped_variant(idea_a: str, idea_b: str) -> bool:
    """Same sentence with extra scope inserted; paraphrases start differently."""
    wa, wb = content_tokens(idea_a), content_tokens(idea_b)
    if not wa or not wb or wa == wb:
        return False
    prefix = 0
    for x, y in zip(wa, wb):
        if x != y:
            break
        prefix += 1
    if prefix < 2:
        return False
    short, long = (wa, wb) if len(wa) <= len(wb) else (wb, wa)
    if len(short) == len(long):
        return False
    it = iter(long)
    return all(tok in it for tok in short)


def token_set(text: str) -> set[str]:
    t = normalize_text(text)
    raw = [x for x in t.split() if x]
    out: set[str] = set()
    for w in raw:
        if w in STOP:
            continue
        stem = _stem(w)
        if stem and stem not in STOP:
            out.add(stem)
        if "-" in w:
            for part in w.split("-"):
                if part and part not in STOP:
                    ps = _stem(part)
                    if ps and ps not in STOP:
                        out.add(ps)
    return out


def stemmed_surface(text: str) -> str:
    parts = []
    for w in normalize_text(text).split():
        if w in STOP:
            continue
        stem = _stem(w)
        if stem and stem not in STOP:
            parts.append(stem)
    return " ".join(parts)


def char_ngrams(text: str, n: int = 3) -> set[str]:
    s = re.sub(r"[^a-z0-9]+", "", stemmed_surface(text))
    if len(s) < n:
        return {s} if s else set()
    return {s[i : i + n] for i in range(len(s) - n + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def lexical_similarity(idea_a: str, idea_b: str) -> float:
    wj = jaccard(token_set(idea_a), token_set(idea_b))
    cj = jaccard(char_ngrams(idea_a), char_ngrams(idea_b))
    return 0.55 * wj + 0.45 * cj


_NUM_UNIT_RE = re.compile(
    r"(?P<num>\d+(?:\.\d+)?)(?:\s*)(?P<unit>[a-z%]+)?"
)
_IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
_ALGO_RE = re.compile(r"\b(aes|sha|tls|rsa)[\s-]*(\d+(?:\.\d+)?)\b", re.I)


def _canon_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    u = unit.lower().rstrip("s")
    mapping = {
        "second": "duration",
        "minute": "duration",
        "hour": "duration",
        "day": "duration",
        "week": "duration",
        "m": "duration",
        "h": "duration",
        "byte": "size",
        "kb": "size",
        "mb": "size",
        "gb": "size",
        "tb": "size",
        "b": "size",
        "percent": "rate",
        "pct": "rate",
        "%": "rate",
    }
    if unit.lower() in DURATION_UNITS or u in {"second", "minute", "hour", "day", "week"}:
        return "duration:" + unit.lower().rstrip("s")
    if unit.lower() in SIZE_UNITS or u in {"byte", "kb", "mb", "gb", "tb"}:
        return "size:" + unit.lower()
    if unit.lower() in RATE_UNITS or unit == "%":
        return "rate"
    return mapping.get(u)


def extract_qualifiers(text: str) -> dict[str, Any]:
    ips = tuple(sorted(_IP_RE.findall(text)))
    t = normalize_text(text)
    t_wo_ip = _IP_RE.sub(" ", text)
    t_wo_ip = normalize_text(t_wo_ip)
    numbers: list[tuple[str, str]] = []
    consumed = [False] * len(t_wo_ip)
    for m in _ALGO_RE.finditer(t_wo_ip):
        for i in range(m.start(), m.end()):
            if 0 <= i < len(consumed):
                consumed[i] = True
    for m in _NUM_UNIT_RE.finditer(t_wo_ip):
        if any(consumed[i] for i in range(m.start(), m.end()) if i < len(consumed)):
            continue
        num = m.group("num")
        unit_raw = m.group("unit")
        kind = _canon_unit(unit_raw)
        if kind:
            numbers.append((kind, num))
        else:
            numbers.append(("bare", num))
    algos = tuple(sorted((a.lower(), n) for a, n in _ALGO_RE.findall(t)))
    polar: set[str] = set()
    for pos, neg in POLAR_PAIRS:
        if pos in t:
            polar.add(pos)
        if neg in t:
            polar.add(neg)
    return {"numbers": tuple(sorted(numbers)), "ips": ips, "algos": algos, "polar": tuple(sorted(polar))}


def qualifier_conflict(idea_a: str, idea_b: str) -> bool:
    qa, qb = extract_qualifiers(idea_a), extract_qualifiers(idea_b)
    if qa["ips"] and qb["ips"] and qa["ips"] != qb["ips"]:
        return True
    if qa["algos"] and qb["algos"] and qa["algos"] != qb["algos"]:
        return True
    # Polar opposition on the same axis.
    for pos, neg in POLAR_PAIRS:
        a_pos, a_neg = pos in qa["polar"], neg in qa["polar"]
        b_pos, b_neg = pos in qb["polar"], neg in qb["polar"]
        if (a_pos or a_neg) and (b_pos or b_neg):
            if (a_pos, a_neg) != (b_pos, b_neg):
                return True
    # Same kind of measured quantity, different value or unit.
    kinds_a = {}
    for kind, num in qa["numbers"]:
        head = kind.split(":")[0]
        if head in {"duration", "size", "rate"} or kind.startswith("aes") or kind == "bare":
            kinds_a.setdefault(head if head != "bare" else "bare", set()).add((kind, num))
    kinds_b = {}
    for kind, num in qb["numbers"]:
        head = kind.split(":")[0]
        kinds_b.setdefault(head if head != "bare" else "bare", set()).add((kind, num))
    for head in set(kinds_a) & set(kinds_b):
        if head == "bare":
            # Only conflict when both sides have a bare number and they differ,
            # and at least one number is unique. Avoid OpenAPI vs OpenAPI 3.
            sa, sb = {n for _, n in kinds_a[head]}, {n for _, n in kinds_b[head]}
            if sa and sb and sa != sb and (sa <= sb or sb <= sa):
                # subset: extra number on one side only — not a conflict
                continue
            if sa and sb and sa != sb:
                return True
        else:
            if kinds_a[head] != kinds_b[head]:
                return True
    return False


def pair_features(idea_a: str, idea_b: str) -> dict[str, Any]:
    conflict = qualifier_conflict(idea_a, idea_b)
    ta, tb = token_set(idea_a), token_set(idea_b)
    inter = len(ta & tb)
    shorter = min(len(ta), len(tb)) or 1
    longer = max(len(ta), len(tb)) or 1
    containment = inter / shorter
    extra = longer - inter
    length_ratio = shorter / longer
    sim = lexical_similarity(idea_a, idea_b)
    capped = min(sim, 0.20) if conflict else sim
    return {
        "lexical_similarity": sim,
        "capped_similarity": capped,
        "qualifier_conflict": conflict,
        "word_jaccard": jaccard(ta, tb),
        "char3_jaccard": jaccard(char_ngrams(idea_a), char_ngrams(idea_b)),
        "containment": containment,
        "extra_tokens": extra,
        "length_ratio": length_ratio,
    }


def classify_pair(idea_a: str, idea_b: str, t_dup: float, t_var: float) -> str:
    feat = pair_features(idea_a, idea_b)
    if feat["qualifier_conflict"]:
        return "distinct"
    if is_scoped_variant(idea_a, idea_b):
        return "variant"
    sim = feat["capped_similarity"]
    if sim >= t_dup:
        return "duplicate"
    if sim >= t_var:
        return "variant"
    return "distinct"


def score_pairs(
    pairs: Sequence[Mapping[str, Any]], t_dup: float, t_var: float
) -> list[dict[str, Any]]:
    rows = []
    for item in pairs:
        pred = classify_pair(item["idea_a"], item["idea_b"], t_dup, t_var)
        feat = pair_features(item["idea_a"], item["idea_b"])
        rows.append(
            {
                "id": item["id"],
                "label": item["label"],
                "predicted": pred,
                "split": item.get("split"),
                "adversarial": bool(item.get("adversarial")),
                **feat,
            }
        )
    return rows


def stopping_rule_from_kappa(kappa: float, floor: float = KAPPA_FLOOR) -> dict[str, Any]:
    """Novelty may gate a stopping rule only when calibrated kappa meets the floor."""
    allowed = float(kappa) >= float(floor)
    return {
        "kappa": float(kappa),
        "kappa_floor": float(floor),
        "may_gate_stopping_rule": allowed,
        "novelty_role": "gate" if allowed else "advisory",
        "refused_reason": None if allowed else "kappa-below-floor",
    }


def apply_novelty_to_stop_expression(
    stop_expression: Mapping[str, Any], kappa: float, floor: float = KAPPA_FLOOR
) -> dict[str, Any]:
    """Strip novelty from a stop expression when the scorer is below floor."""
    gate = stopping_rule_from_kappa(kappa, floor)
    expr = dict(stop_expression)
    uses = bool(expr.get("uses_novelty_score"))
    if uses and not gate["may_gate_stopping_rule"]:
        return {
            "accepted": False,
            "rewritten": {
                **expr,
                "uses_novelty_score": False,
                "novelty_role": "advisory",
            },
            "gate": gate,
        }
    return {"accepted": True, "rewritten": {**expr, "novelty_role": gate["novelty_role"]}, "gate": gate}


def seeded_broken_predictions(labels: Sequence[str], seed: int = 26601) -> list[str]:
    """Deterministic permutation of labels: expected kappa near chance."""
    items = list(labels)
    # Independent LCG shuffle (Fisher-Yates).
    state = seed & 0xFFFFFFFF
    n = len(items)
    for i in range(n - 1, 0, -1):
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        j = state % (i + 1)
        items[i], items[j] = items[j], items[i]
    return items
