"""Thin wrappers around the five SHIPPED gates named by REL-0019.

Fire convention: True means the gate treated the input as the positive class
(blocked / flagged / selected / duplicate / DIVERGED). False means silent.
These wrappers call production functions; they do not reimplement them.

This Linux worktree does not ship tools/plugin/credential_boundary.py,
tools/plugin/drift.py, or tools/router/route.py (those trees are schema-only
or absent). The live decision surfaces on THIS tree are:

  completion   command-center/ready_units.py:artifact_delivered
  credential   platform/plugin/payload.py classify_forbidden + scan_secrets
  capability   hooks/skill-router/route.py _tok + IDF score >= 3.0
  near-dup     the same _tok primitive, Jaccard
  drift        tools/harness-drift/harness_drift.py:compare_pair
"""
from __future__ import annotations

import importlib.util
import math
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

PLUGIN_ROOT = REPO / "platform"
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
HD_ROOT = REPO / "tools" / "harness-drift"
if str(HD_ROOT) not in sys.path:
    sys.path.insert(0, str(HD_ROOT))

from plugin.payload import classify_forbidden, scan_secrets  # noqa: E402
import harness_drift as HD  # noqa: E402

READY = None
SKILL_ROUTER = None

NEAR_DUP_THRESHOLD = 0.50
ROUTER_SCORE_FLOOR = 3.0
ROUTER_SHARED_FLOOR = 2


def _ready():
    global READY
    if READY is None:
        path = REPO / "command-center" / "ready_units.py"
        spec = importlib.util.spec_from_file_location("ready_units_rel0019", path)
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load command-center/ready_units.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        READY = mod
    return READY


def _skill_router():
    global SKILL_ROUTER
    if SKILL_ROUTER is None:
        path = REPO / "hooks" / "skill-router" / "route.py"
        spec = importlib.util.spec_from_file_location("rel0019_skill_router", path)
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load hooks/skill-router/route.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        SKILL_ROUTER = mod
    return SKILL_ROUTER


def fire_completion(payload: dict[str, Any]) -> bool:
    """Fire = completion predicate REJECTS (artifact is not delivered)."""
    unit = {
        "id": payload["id"],
        "output_path": payload["output_path"],
        "completion_sentinel": payload.get("completion_sentinel") or "",
        "output_schema": payload.get("output_schema"),
    }
    delivered, _why = _ready().artifact_delivered(unit, None)
    return not delivered


def fire_credential(payload: dict[str, Any]) -> bool:
    """Fire = forbidden credential class OR a blocking secret-shape finding."""
    kind = payload["kind"]
    if kind == "path":
        return classify_forbidden(payload["path"]) == "credential"
    path = Path(payload["file"])
    rel = payload.get("rel") or path.name
    findings = scan_secrets(path, rel)
    return any(f.severity == "blocking" for f in findings)


def _index_from_capabilities(raw: Any, tok_fn) -> dict[str, Any]:
    if isinstance(raw, dict) and "units" in raw:
        return raw
    units: list[dict[str, Any]] = []
    df: dict[str, int] = {}
    for cap in raw or []:
        name = str(cap.get("name") or cap.get("capability_id") or "unit")
        desc = str(cap.get("description") or "")
        trig = cap.get("triggers") or {}
        extra = " ".join(str(x) for x in (trig.get("keywords") or []))
        extra += " " + " ".join(str(x) for x in (trig.get("verbs") or []))
        toks = tok_fn(f"{name} {name} {desc} {extra}")
        units.append({"name": name, "type": cap.get("kind") or "skill", "toks": sorted(toks)})
        for t in toks:
            df[t] = df.get(t, 0) + 1
    return {"units": units, "df": df, "n": max(1, len(units))}


def fire_capability(payload: dict[str, Any]) -> bool:
    """Fire = skill-router SELECTED (IDF score >= 3.0 with >=2 shared tokens)."""
    sr = _skill_router()
    ptoks = sr._tok(payload["query"])
    idx = _index_from_capabilities(payload["index"], sr._tok)
    df, n = idx.get("df", {}), idx.get("n", 1)

    def idf(t: str) -> float:
        return math.log(1 + n / df.get(t, 1))

    for entry in idx.get("units", []):
        shared = ptoks & set(entry["toks"])
        if len(shared) < ROUTER_SHARED_FLOOR:
            continue
        score = sum(idf(t) for t in shared)
        if score >= ROUTER_SCORE_FLOOR:
            return True
    return False


def jaccard(left: str, right: str) -> float:
    sr = _skill_router()
    a, b = sr._tok(left), sr._tok(right)
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def fire_near_duplicate(payload: dict[str, Any]) -> bool:
    """Fire = Jaccard of shipped skill-router tokens >= threshold."""
    score = jaccard(payload["left"], payload["right"])
    return score >= float(payload.get("threshold", NEAR_DUP_THRESHOLD))


def fire_drift(payload: dict[str, Any]) -> bool:
    """Fire = production two-directional classifier reports DIVERGED."""
    repo = payload["repo"]
    live = payload["live"]
    if isinstance(repo, str):
        repo = repo.encode("utf-8")
    if isinstance(live, str):
        live = live.encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="rel0019-drift-") as tmp:
        root = Path(tmp)
        rp = root / "repo.txt"
        lp = root / "live.txt"
        rp.write_bytes(repo)
        lp.write_bytes(live)
        row = HD.compare_pair("fixture", "repo.txt", rp, lp)
        return row.verdict == HD.V_DIVERGED


DISPATCH = {
    "completion_predicate": fire_completion,
    "credential_scanner": fire_credential,
    "capability_router": fire_capability,
    "near_duplicate_detector": fire_near_duplicate,
    "drift_detector": fire_drift,
}


def evaluate(gate_id: str, payload: dict[str, Any], *, always_accept: str | None = None) -> bool:
    if always_accept and gate_id == always_accept:
        return False
    fn = DISPATCH[gate_id]
    try:
        return bool(fn(payload))
    except Exception:
        if gate_id == "credential_scanner":
            return True
        raise


def source_module(gate_id: str) -> str:
    return {
        "completion_predicate": "command-center/ready_units.py:artifact_delivered",
        "credential_scanner": "platform/plugin/payload.py:classify_forbidden+scan_secrets",
        "capability_router": "hooks/skill-router/route.py:_tok+idf (score>=3.0)",
        "near_duplicate_detector": "hooks/skill-router/route.py:_tok (Jaccard overlap)",
        "drift_detector": "tools/harness-drift/harness_drift.py:compare_pair",
    }[gate_id]
