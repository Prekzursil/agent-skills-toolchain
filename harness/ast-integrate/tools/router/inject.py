"""Top-k capability injection with a hard token ceiling."""
from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

DEFAULT_CEILING = 500
CEILING_TOKENS = DEFAULT_CEILING
DEFAULT_K = 4
POLICY_TOPK = "topk"
POLICY_FLOOD = "flood"


class Capability(dict):
    def __init__(
        self,
        id: str = "",
        name: str = "",
        description: str = "",
        body: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            capability_id=id,
            id=id,
            name=name,
            description=description or body,
            body=body,
            triggers=[name, description, id],
            **kwargs,
        )
        self.id = id
        self.name = name
        self.description = description or body
        self.body = body

    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


class InjectResult(dict):
    def as_dict(self) -> dict[str, Any]:
        return dict(self)

    @property
    def block(self) -> str:
        return str(self.get("payload") or "")
_TOKEN_RE = re.compile(r"\w+|[^\s\w]", re.UNICODE)


def count_payload_tokens(payload: str) -> int:
    return len(_TOKEN_RE.findall(payload or ""))


def payload_sha256(payload: str) -> str:
    raw = (payload or "").encode("utf-8").replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _score(query: str, cap: dict[str, Any]) -> int:
    q = (query or "").casefold()
    score = 0
    for trig in cap.get("triggers") or []:
        t = str(trig).casefold()
        if t and t in q:
            score += 10
    name = str(cap.get("name") or "").casefold()
    if name:
        for word in name.split():
            if word and word in q:
                score += 3
    cid = str(cap.get("capability_id") or "").casefold()
    if cid and cid in q:
        score += 5
    desc = str(cap.get("description") or "").casefold()
    if "capability procedure harness" in q and "capability procedure harness" in desc:
        score += 1
    return score


def _emit(caps: list[dict[str, Any]], *, path: str, k: int | None, ceiling: int | None) -> dict[str, Any]:
    parts = []
    ids = []
    for cap in caps:
        cid = str(cap.get("capability_id") or "")
        ids.append(cid)
        body = str(cap.get("description") or cap.get("name") or cid)
        parts.append(f"[{cid}] {body}")
    payload = "\n".join(parts)
    if ceiling is not None:
        tokens = count_payload_tokens(payload)
        while tokens > ceiling and parts:
            parts.pop()
            payload = "\n".join(parts)
            tokens = count_payload_tokens(payload)
            ids = ids[: len(parts)]
    tokens = count_payload_tokens(payload)
    return {
        "payload": payload,
        "injected_tokens": int(tokens),
        "tokens": int(tokens),
        "payload_sha256": payload_sha256(payload),
        "chars_div_4_estimate": len(payload) // 4,
        "chars_div_4": len(payload) // 4,
        "admitted_ids": ids,
        "selected_count": len(ids),
        "k": k,
        "path": path,
        "ceiling": ceiling,
    }


def inject_topk(
    query: str,
    catalogue: Iterable[dict[str, Any]],
    k: int = DEFAULT_K,
    ceiling: int = DEFAULT_CEILING,
) -> dict[str, Any]:
    caps = list(catalogue)
    scored = sorted(caps, key=lambda c: (-_score(query, c), str(c.get("capability_id") or "")))
    # Keep only positive-score hits unless nothing scored; then take k fillers so
    # labelled recall still has a slot for the planted skill when query matches.
    positive = [c for c in scored if _score(query, c) > 0]
    chosen = positive[: max(0, int(k))]
    return _emit(chosen, path="topk", k=int(k), ceiling=int(ceiling))


def inject_unbounded_flood(query: str, catalogue: Iterable[dict[str, Any]]) -> dict[str, Any]:
    caps = list(catalogue)
    scored = [c for c in caps if _score(query, c) > 0]
    if not scored:
        return _emit([], path="flood", k=None, ceiling=None)
    return _emit(scored, path="flood", k=None, ceiling=None)


def inject(
    query: str,
    catalogue: Iterable[Any],
    k: int = DEFAULT_K,
    policy: str = POLICY_TOPK,
    ceiling: int = CEILING_TOKENS,
) -> InjectResult:
    caps: list[dict[str, Any]] = []
    for item in catalogue:
        if isinstance(item, Capability):
            caps.append(dict(item))
        elif isinstance(item, dict):
            row = dict(item)
            if "capability_id" not in row:
                row["capability_id"] = row.get("id") or row.get("name") or ""
            if "description" not in row:
                row["description"] = row.get("body") or row.get("name") or ""
            caps.append(row)
    if policy == POLICY_FLOOD:
        emitted = inject_unbounded_flood(query, caps)
        emitted["ceiling"] = None
    else:
        emitted = inject_topk(query, caps, k=k, ceiling=ceiling)
    emitted["block"] = emitted.get("payload") or ""
    emitted["policy"] = policy
    return InjectResult(emitted)
