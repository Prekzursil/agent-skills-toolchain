"""A8 product-surface expressibility mapper.

A named capability is EXPRESSIBLE iff it uses the kind.class.slug grammar,
is discovered on the catalog surface, and is invoked on the command surface.
The FIRST inexpressible construct is a subsystem portal that bypasses those
three surfaces.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

ID_RE = {
    "skill": re.compile(r"^skill\.[a-z0-9-]+$"),
    "workflow_blueprint": re.compile(r"^wf\.[a-z0-9-]+\.[a-z0-9-]+$"),
    "council_preset": re.compile(r"^council\.preset\.[a-z0-9-]+\.[a-z0-9-]+$"),
    "hook": re.compile(r"^hook\.[a-z0-9-]+$"),
    "rule": re.compile(r"^rule\.[a-z0-9-]+$"),
    "mcp_mount": re.compile(r"^mcp\.[a-z0-9-]+$"),
}


def _digest(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def first_inexpressible(cap: dict[str, Any]) -> str | None:
    body = cap.get("body") if isinstance(cap.get("body"), dict) else cap
    if not isinstance(body, dict):
        return "$.body:not-object"
    if body.get("entry") == "subsystem-ui" or body.get("bypasses_surfaces"):
        return "$.entry:subsystem-portal-bypasses-command-cockpit-catalog"
    kind = cap.get("kind")
    cap_id = str(cap.get("id") or body.get("name") or "")
    pattern = ID_RE.get(str(kind))
    if pattern is None:
        return f"$.kind:unsupported:{kind}"
    if not pattern.match(cap_id):
        return f"$.id:grammar-fail:{cap_id}"
    discovery = body.get("discovery") if isinstance(body.get("discovery"), dict) else {}
    invoke = body.get("invoke") if isinstance(body.get("invoke"), dict) else {}
    if discovery.get("surface") != "catalog":
        return "$.discovery.surface:not-catalog"
    if invoke.get("surface") != "command":
        return "$.invoke.surface:not-command"
    argv = invoke.get("argv")
    if not isinstance(argv, list) or not argv or argv[0] != "cc":
        return "$.invoke.argv:not-single-command-cc"
    return None


def transcribe(cap: dict[str, Any]) -> dict[str, Any]:
    hit = first_inexpressible(cap)
    form = {
        "form": "a8-product-surface/v1",
        "id": cap.get("id"),
        "kind": cap.get("kind"),
        "source_id": cap.get("source_id"),
        "body": cap.get("body"),
    }
    if hit:
        return {
            "verdict": "INEXPRESSIBLE",
            "first_construct": hit,
            "sha256": _digest(form),
            "config_form": form,
        }
    return {
        "verdict": "EXPRESSIBLE",
        "first_construct": None,
        "sha256": _digest(form),
        "config_form": form,
    }


def transcribe_author(cap: dict[str, Any]) -> dict[str, Any]:
    return transcribe(cap)


def transcribe_independent(cap: dict[str, Any]) -> dict[str, Any]:
    """Round-trip JSON then transcribe (mechanically different walk)."""
    clone = json.loads(json.dumps(cap, sort_keys=True))
    return transcribe(clone)


def same_verdict(a: dict[str, Any], b: dict[str, Any]) -> tuple[bool, str]:
    if a.get("verdict") != b.get("verdict"):
        return False, f"verdict {a.get('verdict')} vs {b.get('verdict')}"
    if a.get("sha256") != b.get("sha256"):
        return False, "sha256-mismatch"
    if a.get("first_construct") != b.get("first_construct"):
        return False, "first-construct-mismatch"
    return True, "ok"
