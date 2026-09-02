#!/usr/bin/env python3
"""Static checks on RES-0038.json (no jsonschema; avoids worktree platform shadow)."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/research/RES-0038.json"
# Catalog output_schema is command-center/schema/research-registry.schema.json,
# which RES-0128 overwrote (required list size 6, unit_id const RES-0128).
# This unit pins the freeze teardown schema next to the probes.
SCHEMA = HERE / "research-registry.schema.json"
SENTINEL = (
    "SUCCESS:RES-0038 in the receipt AND a signal table split into "
    "client-verifiable and display-only with one signal actually recomputed"
)
REQUIRED_TOP = [
    "unit_id",
    "state",
    "sentinel",
    "completion_sentinel",
    "question",
    "required_metadata",
    "publish_flow",
    "signal_table",
    "recomputed_signal",
    "claims",
    "evidence_rails",
    "tests",
    "reviewer",
    "artifacts",
]
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(why: str) -> tuple[bool, str]:
    return False, why


def load_schema_required() -> list[str]:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    req = schema.get("required") or []
    if not isinstance(req, list) or len(req) < 8:
        raise ValueError("schema required list too small")
    return [str(x) for x in req]


def check_artifact(doc: dict, *, text: str | None = None) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return fail("artifact-not-object")
    if str(doc.get("unit_id")) != "RES-0038":
        return fail("unit_id")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared:{st}")
    if st != "SUCCESS":
        return fail(f"state:{st}")
    blob = text if text is not None else json.dumps(doc)
    if SENTINEL not in blob:
        return fail("completion-sentinel-absent")
    for k in load_schema_required():
        if k not in doc:
            return fail(f"missing:{k}")

    table = doc.get("signal_table") or []
    if not isinstance(table, list) or len(table) < 4:
        return fail("signal_table-short")
    classes = {str(r.get("class")) for r in table if isinstance(r, dict)}
    if "client-verifiable" not in classes or "display-only" not in classes:
        return fail("signal_table-not-split")
    recomputed = []
    for row in table:
        if not isinstance(row, dict):
            return fail("signal-row-type")
        for k in ("id", "signal", "class", "justification"):
            if not str(row.get(k) or "").strip():
                return fail(f"signal-missing:{k}")
        if len(str(row.get("justification") or "")) < 16:
            return fail(f"justification-short:{row.get('id')}")
        klass = row.get("class")
        rec = row.get("recomputed_end_to_end")
        if klass == "display-only" and rec is True:
            return fail(f"display-only-claimed-recomputed:{row.get('id')}")
        if klass == "client-verifiable" and rec is True:
            recomputed.append(str(row.get("id")))
    if not recomputed:
        return fail("no-signal-recomputed")

    rec = doc.get("recomputed_signal") or {}
    if rec.get("computed_not_asserted") is not True:
        return fail("recomputed_signal.computed_not_asserted")
    if rec.get("outcome") not in {"MATCH", "PASS", "CONFIRMED"}:
        return fail(f"recomputed_outcome:{rec.get('outcome')}")
    if str(rec.get("signal_id") or "") not in recomputed:
        return fail("recomputed_signal-not-in-table")

    rails = doc.get("evidence_rails") or []
    if not isinstance(rails, list) or len(rails) < 4:
        return fail("evidence_rails-short")
    by_id = {}
    for rail in rails:
        if not isinstance(rail, dict):
            return fail("rail-type")
        for k in ("id", "kind", "permalink", "fetched_at", "sha256"):
            if rail.get(k) in (None, ""):
                return fail(f"rail-missing:{k}")
        if rail.get("kind") not in {"structured-api", "prose-source"}:
            return fail(f"rail-kind:{rail.get('kind')}")
        sha = str(rail.get("sha256") or "")
        if len(sha) != 64:
            return fail(f"rail-sha:{rail.get('id')}")
        rel = str(rail.get("path") or "")
        if rel:
            p = REPO / rel
            if not p.is_file():
                return fail(f"rail-path-missing:{rel}")
            live = hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
            if live != sha:
                return fail(f"rail-sha-mismatch:{rel}")
        by_id[str(rail.get("id"))] = rail

    claims = doc.get("claims") or []
    if not isinstance(claims, list) or len(claims) < 3:
        return fail("claims-short")
    confirmed = 0
    for c in claims:
        if not isinstance(c, dict):
            return fail("claim-type")
        rails_ref = c.get("rails") or []
        if not isinstance(rails_ref, list):
            return fail("claim-rails-type")
        tier = str(c.get("evidence_tier") or "")
        verdict = str(c.get("verdict") or "")
        n = len(rails_ref)
        if verdict == "CONFIRMED":
            if n < 2:
                return fail(f"confirmed-single-rail:{c.get('id')}")
            if tier == "E3":
                return fail(f"confirmed-graded-E3:{c.get('id')}")
            confirmed += 1
        if verdict == "CONFIRMED" or (tier in {"E1", "E2"} and verdict != "E3-NOT-FACT"):
            kinds = set()
            for rid in rails_ref:
                key = str(rid)
                if key not in by_id:
                    return fail(f"claim-rail-unresolved:{c.get('id')}:{key}")
                kinds.add(str(by_id[key].get("kind")))
            if len(kinds) < 2:
                return fail(f"claim-rails-not-independent:{c.get('id')}:{sorted(kinds)}")
    if confirmed < 3:
        return fail(f"confirmed-count:{confirmed}")

    meta = doc.get("required_metadata") or {}
    sreq = meta.get("server_detail_required") or []
    if sorted(sreq) != ["description", "name", "version"]:
        return fail(f"server_detail_required:{sreq}")
    preq = meta.get("package_required") or []
    if set(preq) != {"identifier", "registryType", "transport"}:
        return fail(f"package_required:{preq}")

    flow = doc.get("publish_flow") or {}
    steps = flow.get("steps") or []
    verifies = flow.get("verifies") or []
    if not isinstance(steps, list) or len(steps) < 4:
        return fail("publish_flow.steps")
    if not isinstance(verifies, list) or len(verifies) < 3:
        return fail("publish_flow.verifies")

    tests = doc.get("tests") or []
    if not isinstance(tests, list) or len(tests) < 2:
        return fail("tests-short")
    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        return fail("reviewer-not-independent")

    arts = doc.get("artifacts") or []
    if not any(
        isinstance(a, dict)
        and str(a.get("path") or "").replace("\\", "/")
        == "command-center/research/RES-0038.json"
        and a.get("exists") is True
        for a in arts
    ):
        return fail("primary-artifact-row")
    return True, "ok"


def mutant_display_only_recomputed(doc: dict) -> dict:
    mutant = copy.deepcopy(doc)
    flipped = False
    for row in mutant.get("signal_table") or []:
        if row.get("recomputed_end_to_end") is True:
            row["class"] = "display-only"
            flipped = True
            break
    if not flipped:
        raise RuntimeError("no recomputed row to flip")
    return mutant


def mutant_strip_rail(doc: dict) -> dict:
    mutant = copy.deepcopy(doc)
    for c in mutant.get("claims") or []:
        if c.get("verdict") == "CONFIRMED" and len(c.get("rails") or []) >= 2:
            c["rails"] = c["rails"][:1]
            c["evidence_tier"] = "E2"
            break
    return mutant
