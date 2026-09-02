"""A5 expressibility mapper: capability -> typed work-unit + ledger records.

A capability is EXPRESSIBLE when it can be encoded as one or more work-unit
records that complete via the shared TST-0003 reducer (never via subprocess
exit code) and carry an idempotence_key.

The FIRST inexpressible construct is dispatcher-local SUCCESS from process
exit code 0: TST-0003 reducer.py states exit code 0 is not consulted.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterator

BANNED_KEYS = frozenset(
    {
        "complete_on_exit_code",
        "exit_code_means_success",
        "local_success",
        "skip_reducer",
        "private_reducer",
        "exactly_once_without_key",
        "complete_on",
    }
)
EXIT_CODE_TOKENS = (
    "exit_code_0",
    "exit-code-0",
    "process.exitcode",
    "subprocess-exit-0",
)
FORM = "a5-work-unit/v1"
REDUCER = "command-center/p2-wave/probes/TST-0003/reducer.py:evaluate"


def canonical_bytes(doc: Any) -> bytes:
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def digest(doc: Any) -> str:
    return hashlib.sha256(canonical_bytes(doc)).hexdigest()


def _strip_none(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_none(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_none(x) for x in obj]
    return obj


def _exit_code_completion(node: dict[str, Any]) -> bool:
    complete_on = str(node.get("complete_on") or node.get("completion") or "")
    if any(tok in complete_on.lower() for tok in EXIT_CODE_TOKENS):
        return True
    if node.get("complete_on_exit_code") is True:
        return True
    if node.get("exit_code_means_success") is True:
        return True
    if node.get("skip_reducer") is True:
        return True
    return False


def find_inexpressible_author(obj: Any, path: str = "$") -> str | None:
    if isinstance(obj, dict):
        for key, val in obj.items():
            kl = str(key).lower()
            child = f"{path}.{key}"
            if kl in BANNED_KEYS:
                if kl in {
                    "complete_on_exit_code",
                    "exit_code_means_success",
                    "complete_on",
                    "skip_reducer",
                    "local_success",
                    "private_reducer",
                }:
                    return f"{child}:dispatcher-local-success-from-exit-code-0"
                return f"{child}:banned-key"
            if isinstance(val, str) and any(tok in val.lower() for tok in EXIT_CODE_TOKENS):
                return f"{child}:dispatcher-local-success-from-exit-code-0"
            if _exit_code_completion(obj) and (
                "complete" in path.split(".")[-1].lower() or "complete" in kl or kl == "body"
            ):
                if path.endswith("completion") or kl in {"complete_on", "completion"}:
                    return f"{path}:dispatcher-local-success-from-exit-code-0"
            hit = find_inexpressible_author(val, child)
            if hit:
                return hit
        if _exit_code_completion(obj):
            return f"{path}:dispatcher-local-success-from-exit-code-0"
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            hit = find_inexpressible_author(item, f"{path}[{i}]")
            if hit:
                return hit
    elif isinstance(obj, str):
        if any(tok in obj.lower() for tok in EXIT_CODE_TOKENS):
            return f"{path}:dispatcher-local-success-from-exit-code-0"
    return None


def _iter_independent(obj: Any, path: str = "$") -> Iterator[tuple[str, Any]]:
    yield path, obj
    if isinstance(obj, dict):
        for key in sorted(obj.keys(), reverse=True):
            yield from _iter_independent(obj[key], f"{path}.{key}")
    elif isinstance(obj, list):
        for i in range(len(obj) - 1, -1, -1):
            yield from _iter_independent(obj[i], f"{path}[{i}]")


def find_inexpressible_independent(obj: Any) -> str | None:
    for path, node in _iter_independent(obj):
        if isinstance(node, dict):
            keys_l = {str(k).lower() for k in node}
            banned = keys_l & BANNED_KEYS
            if banned:
                return f"{path}.{sorted(banned)[0]}:dispatcher-local-success-from-exit-code-0"
            if _exit_code_completion(node):
                return f"{path}:dispatcher-local-success-from-exit-code-0"
        elif isinstance(node, str):
            if any(tok in node.lower() for tok in EXIT_CODE_TOKENS):
                return f"{path}:dispatcher-local-success-from-exit-code-0"
    return None


def _work_unit_form(capability: dict[str, Any], body: Any) -> dict[str, Any]:
    kind = capability.get("kind")
    cid = capability.get("id")
    children: list[str] = []
    records = ["ENQUEUE", "CLAIM", "START", "REDUCE", "COMPLETE"]
    if kind == "workflow_blueprint":
        stages = body.get("stages") if isinstance(body, dict) else None
        if isinstance(stages, list):
            children = [f"{cid}:{s.get('id', i)}" for i, s in enumerate(stages) if isinstance(s, dict)]
        records = ["ENQUEUE", "FANOUT", "BARRIER_WAIT", "BARRIER_RELEASE", "CLAIM", "REDUCE"]
    elif kind == "council_preset":
        roles = body.get("roles") if isinstance(body, dict) else None
        if isinstance(roles, list):
            children = [f"{cid}:voice:{r}" for r in roles]
        records = ["ENQUEUE", "FANOUT", "CLAIM", "REDUCE", "COMPLETE"]
    inputs = canonical_bytes(body)
    key = digest({"id": cid, "inputs": hashlib.sha256(inputs).hexdigest()})
    return {
        "form": FORM,
        "kind": kind,
        "id": cid,
        "source_id": capability.get("source_id"),
        "unit": {
            "unit_id": cid,
            "unit_type": kind,
            "substrate": "local",
            "idempotence_key": f"{cid}:{key[:16]}",
            "dedupe_key": cid,
            "completion": REDUCER,
            "children": children,
            "ledger_records": records,
        },
        "config": _strip_none(body),
    }


def transcribe_author(capability: dict[str, Any]) -> dict[str, Any]:
    body = capability.get("body", capability)
    hit = find_inexpressible_author(body)
    if hit:
        return {
            "verdict": "INEXPRESSIBLE",
            "first_construct": hit,
            "id": capability.get("id"),
            "kind": capability.get("kind"),
            "source_id": capability.get("source_id"),
            "mapper": "author-dfs-insertion-order",
        }
    form = _work_unit_form(capability, body)
    return {
        "verdict": "EXPRESSIBLE",
        "first_construct": None,
        "id": capability.get("id"),
        "kind": capability.get("kind"),
        "source_id": capability.get("source_id"),
        "mapper": "author-dfs-insertion-order",
        "config_form": form,
        "sha256": digest(form),
    }


def transcribe_independent(capability: dict[str, Any]) -> dict[str, Any]:
    body = capability.get("body", capability)
    body2 = json.loads(json.dumps(body, sort_keys=True))
    hit = find_inexpressible_independent(body2)
    if hit:
        return {
            "verdict": "INEXPRESSIBLE",
            "first_construct": hit,
            "id": capability.get("id"),
            "kind": capability.get("kind"),
            "source_id": capability.get("source_id"),
            "mapper": "independent-reverse-sorted-walk",
        }
    cap2 = dict(capability)
    cap2["body"] = body2
    form = _work_unit_form(cap2, body2)
    return {
        "verdict": "EXPRESSIBLE",
        "first_construct": None,
        "id": capability.get("id"),
        "kind": capability.get("kind"),
        "source_id": capability.get("source_id"),
        "mapper": "independent-reverse-sorted-walk",
        "config_form": form,
        "sha256": digest(form),
    }


def same_verdict(a: dict[str, Any], b: dict[str, Any]) -> tuple[bool, str]:
    if a.get("verdict") != b.get("verdict"):
        return False, f"verdict {a.get('verdict')} != {b.get('verdict')}"
    if a.get("verdict") == "EXPRESSIBLE":
        if a.get("sha256") != b.get("sha256"):
            return False, f"sha256 {a.get('sha256')} != {b.get('sha256')}"
    else:
        ka = str(a.get("first_construct") or "")
        kb = str(b.get("first_construct") or "")
        token = "dispatcher-local-success-from-exit-code-0"
        if token in ka and token in kb:
            return True, "inexpressible-same-construct-class"
        if ka.split(":")[-1] != kb.split(":")[-1]:
            return False, f"first_construct class {ka!r} vs {kb!r}"
    return True, "match"
