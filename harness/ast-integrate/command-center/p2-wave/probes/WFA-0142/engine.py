#!/usr/bin/env python3
"""WFA-0142 supersession engine: supersede + migrate + rehearsed rollback.

Triggered by a superior replacement, not a failed regression. Distinct from
WFA-0137 revocation (CERTIFIED -> DECERTIFIED only). This engine emits the
exact caller/preset/fusion migration set and preserves rollback to the
superseded workflow and its decomposed source components.

A rollback that would drop a live caller is refused, not applied.
"""
from __future__ import annotations

import copy
import hashlib
import inspect
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE = HERE / "fixtures" / "registry.json"
OLD_ID = "wf.legacy"
NEW_ID = "wf.replacement"
NEW_CALLER_ID = "pack.new-on-b"


def _anchor(fn) -> str:
    src = inspect.getsourcefile(fn) or __file__
    line = inspect.getsourcelines(fn)[1]
    try:
        rel = Path(src).resolve().relative_to(REPO).as_posix()
    except ValueError:
        rel = Path(src).name
    return f"{rel}:{line}"


def load_fixture(path: Path | None = None) -> dict[str, Any]:
    raw = json.loads((path or FIXTURE).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "workflows" not in raw or "callers" not in raw:
        raise ValueError("fixture must contain workflows and callers")
    return raw


def canonical_bytes(obj: Any) -> bytes:
    """Signal 1 dump: one canonical JSON blob."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@dataclass
class MigrationStep:
    caller_id: str
    kind: str
    from_id: str
    to_id: str

    def as_dict(self) -> dict[str, str]:
        return {
            "caller_id": self.caller_id,
            "kind": self.kind,
            "from_id": self.from_id,
            "to_id": self.to_id,
        }


@dataclass
class OpResult:
    ok: bool
    reason: str
    dropped_callers: list[str] = field(default_factory=list)
    supersession_id: str = ""
    migration: list[MigrationStep] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reason": self.reason,
            "dropped_callers": list(self.dropped_callers),
            "supersession_id": self.supersession_id,
            "migration": [m.as_dict() for m in self.migration],
        }


class Registry:
    """In-memory workflow registry with a frozen serving snapshot for rollback."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.workflows: dict[str, Any] = copy.deepcopy(data["workflows"])
        self.callers: dict[str, Any] = copy.deepcopy(data["callers"])
        self._frozen: dict[str, Any] | None = None
        self._seq = 0

    def serving_view(self) -> dict[str, Any]:
        return {
            "workflows": copy.deepcopy(self.workflows),
            "callers": copy.deepcopy(self.callers),
        }

    def freeze_serving(self) -> dict[str, Any]:
        snap = self.serving_view()
        self._frozen = snap
        return snap


def serving_canonical_bytes(reg: Registry) -> bytes:
    """Independent signal 1: hash of the whole serving view."""
    return canonical_bytes(reg.serving_view())


def per_object_digests(reg: Registry) -> dict[str, str]:
    """Independent signal 2: per-id sha256 of each document and caller.

    Distinct from serving_canonical_bytes: each object is hashed in isolation.
    A dump-concatenation cheat cannot keep this map aligned with every restored
    document.
    """
    out: dict[str, str] = {}
    for wid, wf in reg.workflows.items():
        out[f"workflow:{wid}"] = sha256_bytes(canonical_bytes(wf.get("document")))
        out[f"lineage:{wid}"] = sha256_bytes(
            canonical_bytes(
                {
                    "sources_declared": list(wf.get("sources_declared") or []),
                    "sources_unresolved": list(wf.get("sources_unresolved") or []),
                    "status": wf.get("status"),
                    "superseded_by": wf.get("superseded_by"),
                }
            )
        )
    for cid, caller in reg.callers.items():
        out[f"caller:{cid}"] = sha256_bytes(canonical_bytes(caller))
    return dict(sorted(out.items()))


def digest_map_sha(digests: dict[str, str]) -> str:
    return sha256_bytes(canonical_bytes(digests))


def decompose(reg: Registry, workflow_id: str) -> list[str]:
    """Recover declared source ids (WFA-0138-shaped lineage, fixture-local)."""
    wf = reg.workflows.get(workflow_id)
    if wf is None:
        raise KeyError(workflow_id)
    return list(wf.get("sources_declared") or [])


def migration_set(reg: Registry, old_id: str, new_id: str) -> list[MigrationStep]:
    """Exact caller/preset/fusion set that embeds old_id and must retarget."""
    steps: list[MigrationStep] = []
    for cid, caller in sorted(reg.callers.items()):
        embeds = list(caller.get("embeds") or [])
        if old_id in embeds:
            steps.append(
                MigrationStep(
                    caller_id=cid,
                    kind=str(caller.get("kind") or "unknown"),
                    from_id=old_id,
                    to_id=new_id,
                )
            )
    return steps


def _retarget(embeds: list[str], old_id: str, new_id: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in embeds:
        nxt = new_id if item == old_id else item
        if nxt not in seen:
            out.append(nxt)
            seen.add(nxt)
    return out


def supersede(
    reg: Registry,
    old_id: str,
    new_id: str,
    *,
    reason: str = "superior-replacement",
) -> OpResult:
    if old_id == new_id:
        return OpResult(False, "refuse-self-supersession")
    if old_id not in reg.workflows:
        return OpResult(False, f"missing-old:{old_id}")
    if new_id not in reg.workflows:
        return OpResult(False, f"missing-new:{new_id}")
    old = reg.workflows[old_id]
    if str(old.get("status") or "") == "SUPERSEDED":
        return OpResult(False, "already-superseded")
    if str(old.get("status") or "") == "DECERTIFIED":
        return OpResult(False, "refuse-decertified-source")
    steps = migration_set(reg, old_id, new_id)
    if not steps:
        return OpResult(False, "no-callers-to-migrate")
    reg.freeze_serving()
    old["status"] = "SUPERSEDED"
    old["superseded_by"] = new_id
    old["supersession_reason"] = reason
    for step in steps:
        caller = reg.callers[step.caller_id]
        caller["embeds"] = _retarget(list(caller.get("embeds") or []), old_id, new_id)
        caller["migrated_from"] = old_id
    reg._seq += 1
    sid = f"sup-{reg._seq:04d}-{old_id}->{new_id}"
    return OpResult(True, "superseded", supersession_id=sid, migration=steps)


def _would_drop_callers(reg: Registry) -> list[str]:
    if reg._frozen is None:
        return []
    live = set(reg.callers)
    prior = set(reg._frozen.get("callers") or {})
    return sorted(live - prior)


def rollback(reg: Registry, *, allow_drop_callers: bool = False) -> OpResult:
    if reg._frozen is None:
        return OpResult(False, "no-frozen-prestate")
    dropped = _would_drop_callers(reg)
    if dropped and not allow_drop_callers:
        return OpResult(
            False,
            "rollback-would-drop-callers:" + ",".join(dropped),
            dropped_callers=dropped,
        )
    restored = copy.deepcopy(reg._frozen)
    reg.workflows = restored["workflows"]
    reg.callers = restored["callers"]
    return OpResult(True, "rolled-back")


def restore_sources(reg: Registry, workflow_id: str) -> dict[str, Any]:
    """Decomposed source documents from the frozen pre-supersession copy."""
    if reg._frozen is None:
        sources = decompose(reg, workflow_id)
        wfs = reg.workflows
    else:
        wfs = reg._frozen["workflows"]
        sources = list((wfs.get(workflow_id) or {}).get("sources_declared") or [])
    out: dict[str, Any] = {}
    for sid in sources:
        src = wfs.get(sid)
        if src is None:
            raise KeyError(sid)
        out[sid] = copy.deepcopy(src.get("document"))
    return out


@dataclass
class CycleReport:
    pass_: bool
    reason: str
    old_id: str
    new_id: str
    migration: list[dict[str, str]]
    pre_serving_sha256: str
    post_serving_sha256: str
    byte_equal: bool
    pre_digest_map_sha256: str
    post_digest_map_sha256: str
    digest_map_equal: bool
    sources_restored_equal: bool
    decomposed_sources: list[str]
    tamper_cleared: bool
    supersession_ok: bool
    rollback_ok: bool
    anchors: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "pass": self.pass_,
            "reason": self.reason,
            "old_id": self.old_id,
            "new_id": self.new_id,
            "migration": self.migration,
            "pre_serving_sha256": self.pre_serving_sha256,
            "post_serving_sha256": self.post_serving_sha256,
            "byte_equal": self.byte_equal,
            "pre_digest_map_sha256": self.pre_digest_map_sha256,
            "post_digest_map_sha256": self.post_digest_map_sha256,
            "digest_map_equal": self.digest_map_equal,
            "sources_restored_equal": self.sources_restored_equal,
            "decomposed_sources": self.decomposed_sources,
            "tamper_cleared": self.tamper_cleared,
            "supersession_ok": self.supersession_ok,
            "rollback_ok": self.rollback_ok,
            "anchors": self.anchors,
        }


def rehearse_clean_cycle(
    data: dict[str, Any] | None = None,
    *,
    old_id: str = OLD_ID,
    new_id: str = NEW_ID,
) -> CycleReport:
    """Supersede, tamper a source, roll back, byte-compare with pre-state."""
    anchors = {
        "serving_canonical_bytes": _anchor(serving_canonical_bytes),
        "per_object_digests": _anchor(per_object_digests),
        "supersede": _anchor(supersede),
        "rollback": _anchor(rollback),
        "decompose": _anchor(decompose),
        "restore_sources": _anchor(restore_sources),
        "migration_set": _anchor(migration_set),
    }
    reg = Registry(data or load_fixture())
    pre_bytes = serving_canonical_bytes(reg)
    pre_sha = sha256_bytes(pre_bytes)
    pre_map = per_object_digests(reg)
    pre_map_sha = digest_map_sha(pre_map)
    source_docs_pre = {
        sid: copy.deepcopy(reg.workflows[sid]["document"])
        for sid in decompose(reg, old_id)
    }

    sup = supersede(reg, old_id, new_id)
    if not sup.ok:
        return CycleReport(
            False,
            f"supersede-failed:{sup.reason}",
            old_id,
            new_id,
            [],
            pre_sha,
            "",
            False,
            pre_map_sha,
            "",
            False,
            False,
            decompose(reg, old_id) if old_id in reg.workflows else [],
            False,
            False,
            False,
            anchors,
        )

    tamper_id = decompose(reg, old_id)[0]
    reg.workflows[tamper_id]["document"] = dict(reg.workflows[tamper_id]["document"])
    reg.workflows[tamper_id]["document"]["tamper"] = "during-supersession"

    rb = rollback(reg)
    post_bytes = serving_canonical_bytes(reg)
    post_sha = sha256_bytes(post_bytes)
    post_map = per_object_digests(reg)
    post_map_sha = digest_map_sha(post_map)
    sources = decompose(reg, old_id)
    restored_src = {
        sid: copy.deepcopy(reg.workflows[sid]["document"]) for sid in sources
    }
    sources_ok = restored_src == source_docs_pre
    tamper_cleared = "tamper" not in json.dumps(restored_src, sort_keys=True)
    byte_eq = pre_bytes == post_bytes
    map_eq = pre_map == post_map and pre_map_sha == post_map_sha
    expected_sources = ["src.review", "src.test"]
    ok = (
        sup.ok
        and rb.ok
        and byte_eq
        and map_eq
        and sources_ok
        and tamper_cleared
        and sources == expected_sources
    )
    reason = "ok"
    if not rb.ok:
        reason = f"rollback-failed:{rb.reason}"
    elif not byte_eq:
        reason = "serving-bytes-not-equal"
    elif not map_eq:
        reason = "digest-map-not-equal"
    elif not sources_ok:
        reason = "source-documents-not-restored"
    elif not tamper_cleared:
        reason = "source-tamper-survived"
    elif sources != expected_sources:
        reason = f"decompose-mismatch:{sources}"
    elif not ok:
        reason = "cycle-mismatch"
    return CycleReport(
        ok,
        reason,
        old_id,
        new_id,
        [m.as_dict() for m in sup.migration],
        pre_sha,
        post_sha,
        byte_eq,
        pre_map_sha,
        post_map_sha,
        map_eq,
        sources_ok,
        sources,
        tamper_cleared,
        sup.ok,
        rb.ok,
        anchors,
    )


@dataclass
class RefusalReport:
    pass_: bool
    reason: str
    good_rollback_ok: bool
    good_byte_equal: bool
    bad_rollback_ok: bool
    bad_reason: str
    dropped_named: list[str]
    mutant_dropped: bool
    both_states: bool
    anchors: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "pass": self.pass_,
            "reason": self.reason,
            "good_rollback_ok": self.good_rollback_ok,
            "good_byte_equal": self.good_byte_equal,
            "bad_rollback_ok": self.bad_rollback_ok,
            "bad_reason": self.bad_reason,
            "dropped_named": self.dropped_named,
            "mutant_dropped": self.mutant_dropped,
            "both_states": self.both_states,
            "anchors": self.anchors,
        }


def _add_new_caller(reg: Registry, embeds: list[str]) -> None:
    reg.callers[NEW_CALLER_ID] = {
        "id": NEW_CALLER_ID,
        "kind": "pack",
        "embeds": list(embeds),
    }


def rehearse_drop_caller_refusal(
    data: dict[str, Any] | None = None,
    *,
    old_id: str = OLD_ID,
    new_id: str = NEW_ID,
) -> RefusalReport:
    """Both-states: clean rollback succeeds; drop-caller rollback is refused."""
    anchors = {
        "rollback": _anchor(rollback),
        "supersede": _anchor(supersede),
        "_would_drop_callers": _anchor(_would_drop_callers),
    }
    src = data or load_fixture()

    good = Registry(src)
    pre = serving_canonical_bytes(good)
    sup_g = supersede(good, old_id, new_id)
    rb_g = rollback(good)
    good_eq = serving_canonical_bytes(good) == pre

    bad = Registry(src)
    sup_b = supersede(bad, old_id, new_id)
    _add_new_caller(bad, [new_id])
    rb_b = rollback(bad)
    still_present = NEW_CALLER_ID in bad.callers

    mutant = Registry(src)
    supersede(mutant, old_id, new_id)
    _add_new_caller(mutant, [new_id])
    rb_m = rollback(mutant, allow_drop_callers=True)
    mutant_dropped = NEW_CALLER_ID not in mutant.callers

    both = (
        sup_g.ok
        and rb_g.ok
        and good_eq
        and sup_b.ok
        and (not rb_b.ok)
        and NEW_CALLER_ID in rb_b.dropped_callers
        and still_present
        and rb_m.ok
        and mutant_dropped
    )
    named = list(rb_b.dropped_callers)
    reason = "ok"
    if not rb_g.ok:
        reason = f"good-rollback-failed:{rb_g.reason}"
    elif rb_b.ok:
        reason = "drop-caller-rollback-was-allowed"
    elif NEW_CALLER_ID not in named:
        reason = "refused-without-naming-dropped-caller"
    elif not mutant_dropped:
        reason = "mutant-did-not-drop-caller"
    elif not both:
        reason = "both-states-collapsed"
    return RefusalReport(
        both,
        reason,
        rb_g.ok,
        good_eq,
        rb_b.ok,
        rb_b.reason,
        named,
        mutant_dropped,
        both,
        anchors,
    )


def estate_census(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    catalog = json.loads(
        (root / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    dep_paths: dict[str, str | None] = {"WFA-0137": None, "WFA-0138": None}
    for unit in catalog.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") in dep_paths:
            dep_paths[str(unit["id"])] = str(unit.get("output_path") or "")
    rows = []
    for uid, rel in dep_paths.items():
        p = root / rel if rel else None
        rows.append(
            {
                "id": uid,
                "output_path": rel or "",
                "present": bool(p and p.is_file() and p.stat().st_size > 0),
            }
        )
    candidates = [
        "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
        "command-center/sources/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
        "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
        "command-center/foundry/WFA-0138-fusion-lineage-record-and-the-decomposition-round-tr.json",
        "command-center/foundry/WFA-0137-decertification-path-when-a-certified-workflow-later.json",
    ]
    files = []
    for rel in candidates:
        p = root / rel
        files.append({"path": rel, "present": p.is_file()})
    return {"dependency_artifacts": rows, "estate_files": files}
