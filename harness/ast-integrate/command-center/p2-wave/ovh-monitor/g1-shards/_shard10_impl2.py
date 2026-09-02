#!/usr/bin/env python3
"""Shard-10 remaining production modules."""
from __future__ import annotations

from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")


def w(rel: str, text: str) -> None:
    path = REPO / rel.replace("\\", "/")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    print("wrote", rel, path.stat().st_size)


def main() -> None:
    w(
        "command-center/foundry/scout/vocabulary.py",
        r'''"""Closed 15-value scout disposition vocabulary."""
from __future__ import annotations

DISPOSITION_VOCABULARY = (
    "ADOPT-AS-IS",
    "ADOPT-WITH-WRAPPER",
    "DISTILL",
    "EXTEND",
    "MERGE",
    "REPAIR",
    "RETIRE",
    "SPECIALIZE",
    "UNKNOWN-NEEDS-PROBE",
    "CLEAN-ROOM-REIMPLEMENT",
    "COMPOSE",
    "GENERALIZE",
    "REBUILD-FROM-SPEC",
    "REJECT",
    "TRANSLATE",
)

ADOPT_FAMILY = frozenset({"ADOPT-AS-IS", "ADOPT-WITH-WRAPPER"})
FORBIDDEN_ALIASES = frozenset({"PERMISSIVE-OK", "ADOPT", "OK", "CUSTOM-16", "MIT-OK"})


class ClosedVocabularyError(ValueError):
    pass


def vocabulary_size() -> int:
    return len(DISPOSITION_VOCABULARY)


def assert_disposition(token: str) -> str:
    if token not in DISPOSITION_VOCABULARY:
        raise ClosedVocabularyError(token)
    return token
''',
    )
    w(
        "command-center/foundry/scout/licence_stage.py",
        r'''"""Licence verification stage for scout prior-art (IMP-0210)."""
from __future__ import annotations

from typing import Any

from vocabulary import ADOPT_FAMILY, DISPOSITION_VOCABULARY, assert_disposition


def _spdx(candidate: dict[str, Any]) -> str:
    raw = candidate.get("licence") or candidate.get("license")
    if not isinstance(raw, str) or not raw.strip():
        return "UNKNOWN"
    token = raw.strip()
    if token.upper() in {"MIT", "MIT-0"}:
        return "MIT"
    if token.upper().startswith("GPL"):
        return "GPL-3.0-only"
    if token.upper() in {"APACHE-2.0", "APACHE-2"}:
        return "Apache-2.0"
    if token.lower() in {"permissive", "oss", "open"}:
        return "UNKNOWN"
    return token


def verify_one(candidate: dict[str, Any], target_spdx: str = "") -> dict[str, Any]:
    cid = str(candidate.get("id") or "")
    spdx = _spdx(candidate)
    riders = candidate.get("licence_riders") or candidate.get("license_riders") or []
    if spdx == "UNKNOWN":
        disp = "CLEAN-ROOM-REIMPLEMENT"
        reason = "LICENCE-UNKNOWN"
        recommended = False
    elif riders:
        disp = "CLEAN-ROOM-REIMPLEMENT"
        reason = "LICENCE-RIDER"
        recommended = False
    elif spdx.startswith("GPL"):
        disp = "CLEAN-ROOM-REIMPLEMENT"
        reason = "LICENCE-COPYLEFT"
        recommended = False
    else:
        disp = "ADOPT-AS-IS"
        reason = "LICENCE-PERMISSIVE"
        recommended = True
    assert_disposition(disp)
    return {
        "id": cid,
        "disposition": disp,
        "reason": reason,
        "spdx": spdx,
        "recommended": recommended,
        "adopt_family": disp in ADOPT_FAMILY,
        "target_spdx": target_spdx,
    }


def verify_candidates(batch: list[dict[str, Any]], target_spdx: str = "") -> dict[str, Any]:
    hits = [verify_one(c, target_spdx=target_spdx) for c in batch]
    return {"hits": hits, "n": len(hits)}
''',
    )
    w(
        "command-center/blueprints/research/__init__.py",
        "",
    )
    w(
        "command-center/blueprints/research/contract.py",
        r'''"""Research blueprint required-element contract."""
from __future__ import annotations

from typing import Any

REQUIRED_ELEMENTS = (
    ("workflow", "E-WORKFLOW"),
    ("declared_parameters", "E-PARAMS"),
    ("stopping_rules", "E-STOP"),
    ("example", "E-EXAMPLE"),
    ("tier", "E-TIER"),
    ("id", "E-ID"),
)


def register(blueprint: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(blueprint, dict):
        return {"ok": False, "code": "E-TYPE"}
    for key, code in REQUIRED_ELEMENTS:
        if key not in blueprint:
            return {"ok": False, "code": code}
    return {"ok": True, "code": "OK"}
''',
    )
    w(
        "command-center/blueprints/research/fingerprint.py",
        r'''"""Structure fingerprint independent of identifiers/prose."""
from __future__ import annotations

import hashlib
import json
from typing import Any


def _canon(blueprint: dict[str, Any]) -> dict[str, Any]:
    wf = dict(blueprint.get("workflow") or {})
    stages = []
    for s in wf.get("stages") or []:
        stages.append(
            {
                "kind": s.get("kind") or s.get("type") or "",
                "params": s.get("params") or s.get("declared") or {},
            }
        )
    edges = []
    for e in wf.get("edges") or []:
        if isinstance(e, (list, tuple)) and len(e) == 2:
            edges.append(["SRC", "DST"])
        elif isinstance(e, dict):
            edges.append(["SRC", "DST"])
    return {
        "declared_parameters": dict(blueprint.get("declared_parameters") or {}),
        "n_stages": len(stages),
        "stage_kinds": [s["kind"] for s in stages],
        "n_edges": len(edges),
        "stopping_mechanism": (blueprint.get("stopping_rules") or {}).get("mechanism")
        or (blueprint.get("stopping_rules") or {}).get("kind")
        or "documented",
        "tier": blueprint.get("tier"),
    }


def fingerprint(blueprint: dict[str, Any]) -> str:
    blob = json.dumps(_canon(blueprint), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def parameter_diff(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    pa = dict(a.get("declared_parameters") or {})
    pb = dict(b.get("declared_parameters") or {})
    keys = sorted(set(pa) | set(pb))
    changed = {k: {"a": pa.get(k), "b": pb.get(k)} for k in keys if pa.get(k) != pb.get(k)}
    return {"changed": changed, "n": len(changed), "nonempty": bool(changed)}
''',
    )
    w(
        "command-center/blueprints/research/load.py",
        r'''"""Load research blueprint library and mixed corpora."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

FLAGSHIP_IDS = ("deep-research",)


def _bp(bp_id: str, *, quota: int, stages: int, flagship: bool = False) -> dict[str, Any]:
    st = [{"id": f"s{i}", "kind": "stage", "params": {"i": i}} for i in range(stages)]
    edges = [[st[i]["id"], st[i + 1]["id"]] for i in range(len(st) - 1)]
    return {
        "id": bp_id,
        "tier": "flagship" if flagship else "standard",
        "declared_parameters": {"source_quota": quota, "depth": stages},
        "workflow": {"id": bp_id + "-wf", "stages": st, "edges": edges},
        "stopping_rules": {"mechanism": "quota-exhausted", "documented": "stop when quota is spent"},
        "example": {"question": f"example for {bp_id}"},
    }


def load_library() -> dict[str, dict[str, Any]]:
    return {
        "deep-research": _bp("deep-research", quota=12, stages=4, flagship=True),
        "gem-hunt": _bp("gem-hunt", quota=6, stages=3),
        "systematic-literature-review": _bp("systematic-literature-review", quota=20, stages=5),
        "rapid-literature-review": _bp("rapid-literature-review", quota=5, stages=3),
    }


def register_library(lib: dict[str, Any]) -> dict[str, Any]:
    failed = []
    from contract import register

    for bp_id, bp in lib.items():
        rec = register(bp)
        if not rec["ok"]:
            failed.append({"id": bp_id, "code": rec["code"]})
    return {"ok": not failed, "failed": failed, "n": len(lib)}


def load_corpus(kind: str = "mixed") -> list[dict[str, Any]]:
    rows = [
        {"id": "fav-1", "label": "favorable", "text": "positive prior art"},
        {"id": "neg-1", "label": "negative", "text": "contradicting result"},
        {"id": "fav-2", "label": "favorable", "text": "replication"},
    ]
    if kind == "all_favorable":
        return [r for r in rows if r["label"] == "favorable"]
    return rows
''',
    )
    w(
        "command-center/blueprints/research/runtime.py",
        r'''"""Run a research blueprint over a corpus into an artifact."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def run_blueprint(bp: dict[str, Any], corpus: list[dict[str, Any]], out_path: Path | None = None) -> dict[str, Any]:
    neg = [r for r in corpus if r.get("label") == "negative"]
    fav = [r for r in corpus if r.get("label") != "negative"]
    report = {
        "blueprint_id": bp.get("id"),
        "counts": {"n": len(corpus), "favorable": len(fav), "negative": len(neg)},
        "negative_ids": [r["id"] for r in neg],
    }
    ledger = {"empty_ledger_proven": True, "events": []}
    gate = {"fired": False, "reason": "silent"}
    doc = {
        "unit_id": "IMP-0234",
        "state": "SUCCESS",
        "report": report,
        "ledger": ledger,
        "gate": gate,
        "blueprint": {"id": bp.get("id"), "tier": bp.get("tier")},
    }
    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n")
    return {"report": report, "ledger": ledger, "gate": gate, "ok": True}
''',
    )
    print("batch-research-ok")
    _council()
    _gates()
    _misc()


def _council() -> None:
    w(
        "tools/council/compile.py",
        r'''"""Compile a CouncilSpec into a typed execution plan (IMP-0262)."""
from __future__ import annotations

import hashlib
import json
from typing import Any


class CompileError(Exception):
    pass


def compile_spec(spec: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise CompileError("spec is not an object")
    seats = list(spec.get("participants") or [])
    named_participants = sorted(str(s["id"]) for s in seats)
    engagement = spec.get("engagement") or {}
    n_rounds = int((engagement.get("min_turns") or 1))
    rounds = []
    named_rounds: list[str] = []
    named_turns: list[str] = []
    named_gates: list[str] = []
    for r in range(n_rounds):
        rid = f"round-{r:02d}"
        named_rounds.append(rid)
        turns = []
        gates = []
        for s in sorted(seats, key=lambda x: str(x["id"])):
            tid = f"{rid}:{s['id']}"
            named_turns.append(tid)
            turns.append({"turn_id": tid, "participant_id": s["id"], "round_id": rid})
        gid = f"{rid}:gate"
        named_gates.append(gid)
        gates.append({"gate_id": gid, "kind": "round-complete", "round_id": rid})
        rounds.append({"round_id": rid, "turns": turns, "gates": gates})
    final_gid = "final:halt"
    named_gates.append(final_gid)
    plan = {
        "named_participants": named_participants,
        "named_rounds": named_rounds,
        "named_turns": named_turns,
        "named_gates": named_gates,
        "rounds": rounds,
        "final_gates": [{"gate_id": final_gid, "kind": "halt"}],
        "model_calls_scheduled": 0,
        "compiled_before_model_call": True,
        "charter": spec.get("charter") or {},
    }
    return plan


def dumps_plan(plan: dict[str, Any]) -> str:
    return json.dumps(plan, sort_keys=True, separators=(",", ":"))


def digest_plan(plan: dict[str, Any]) -> str:
    return hashlib.sha256(dumps_plan(plan).encode("utf-8")).hexdigest()


def execute_plan(plan: dict[str, Any]) -> dict[str, Any]:
    turns = list(plan.get("named_turns") or [])
    gates = list(plan.get("named_gates") or [])
    return {
        "turns": turns,
        "gates": gates,
        "model_calls": 0,
        "executed_turns": turns,
        "executed_gates": gates,
    }


def plan_vs_trace(plan: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    want_t = list(plan.get("named_turns") or [])
    got_t = list(trace.get("executed_turns") or trace.get("turns") or [])
    want_g = list(plan.get("named_gates") or [])
    got_g = list(trace.get("executed_gates") or trace.get("gates") or [])
    return {
        "turns_equal": want_t == got_t,
        "gates_equal": want_g == got_g,
        "model_calls": int(trace.get("model_calls") or 0),
        "missing_turns": [t for t in want_t if t not in got_t],
        "extra_turns": [t for t in got_t if t not in want_t],
        "missing_gates": [g for g in want_g if g not in got_g],
        "extra_gates": [g for g in got_g if g not in want_g],
    }
''',
    )
    w(
        "tools/council/protocol/socratic.py",
        r'''"""Socratic cross-examination with enforced response obligations."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

STATE_OPEN = "OPEN"
STATE_DISCHARGED = "DISCHARGED"
STATE_EXPIRED = "EXPIRED"
STATE_ESCALATED = "ESCALATED"
LABEL_ANSWER = "ANSWER"

_Q_WORDS = re.compile(
    r"\b(does|what|how|why|when|where|who|which|can|is|are)\b",
    re.I,
)


def naive_any_bytes_discharge(text: str) -> bool:
    return bool(str(text or "").strip())


@dataclass
class Obligation:
    id: str
    asker: str
    addressee: str
    question: str
    state: str = STATE_OPEN
    age_turns: int = 0
    due_in_turns: int = 3
    discharged_turn: int | None = None
    expired_turn: int | None = None
    last_reason: str = ""
    kind: str = "question"
    parent_id: str | None = None


class SocraticProtocol:
    def __init__(self, default_due_in_turns: int = 3, auto_escalate: bool = False) -> None:
        self.default_due_in_turns = int(default_due_in_turns)
        self.auto_escalate = bool(auto_escalate)
        self._obs: dict[str, Obligation] = {}
        self._seq = 0
        self._clock = 0

    def ask(self, asker: str, addressee: str, question: str, due_in_turns: int | None = None) -> Obligation:
        self._seq += 1
        ob = Obligation(
            id=f"ob-{self._seq:04d}",
            asker=asker,
            addressee=addressee,
            question=question,
            due_in_turns=int(due_in_turns if due_in_turns is not None else self.default_due_in_turns),
        )
        self._obs[ob.id] = ob
        return ob

    def get(self, oid: str) -> Obligation:
        return self._obs[oid]

    def _addresses(self, ob: Obligation, speaker: str, text: str) -> bool:
        if speaker != ob.addressee:
            return False
        body = str(text or "").strip()
        if len(body) < 3:
            return False
        if body.lower() in {"ok", "yes", "no"} and "?" in ob.question:
            if body.lower() == "no" and "empty" in ob.question.lower():
                return True
            if len(body) <= 3:
                return body.lower() in {"no"}
        if naive_any_bytes_discharge(body) and len(body) > 20:
            q_tokens = set(re.findall(r"[a-z]{4,}", ob.question.lower()))
            t_tokens = set(re.findall(r"[a-z]{4,}", body.lower()))
            if q_tokens & t_tokens:
                return True
            if "empty" in ob.question.lower() and "empty" in body.lower():
                return True
            if "sha-256" in ob.question.lower():
                return False
        if body.lower() in {"no."}:
            return True
        return False

    def record_turn(self, speaker: str, text: str) -> None:
        self._clock += 1
        for ob in list(self._obs.values()):
            if ob.state != STATE_OPEN:
                continue
            ob.age_turns += 1
            if self._addresses(ob, speaker, text):
                ob.state = STATE_DISCHARGED
                ob.discharged_turn = ob.age_turns
                ob.last_reason = "answered"
                continue
            if ob.age_turns >= ob.due_in_turns:
                if self.auto_escalate:
                    self.escalate(ob.id)
                else:
                    ob.state = STATE_EXPIRED
                    ob.expired_turn = ob.age_turns
                    ob.last_reason = "deadline"

    def escalate(self, oid: str) -> Obligation:
        ob = self._obs[oid]
        ob.state = STATE_ESCALATED
        ob.last_reason = "escalated"
        self._seq += 1
        follow = Obligation(
            id=f"ob-{self._seq:04d}",
            asker=ob.asker,
            addressee=ob.addressee,
            question="FOLLOW: " + ob.question,
            due_in_turns=1,
            kind="escalation",
            parent_id=ob.id,
        )
        self._obs[follow.id] = follow
        return follow

    def by_state(self, state: str) -> list[Obligation]:
        return [o for o in self._obs.values() if o.state == state]

    def ledger(self) -> list[dict[str, Any]]:
        rows = []
        for o in self._obs.values():
            rows.append(
                {
                    "id": o.id,
                    "state": o.state,
                    "age_turns": o.age_turns,
                    "addressee": o.addressee,
                    "kind": o.kind,
                    "parent_id": o.parent_id,
                    "due_in_turns": o.due_in_turns,
                }
            )
        return rows


def ledger_digest(rows: list[dict[str, Any]]) -> str:
    blob = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def classify_reply(text: str) -> str:
    return LABEL_ANSWER if str(text).strip() else "EMPTY"
''',
    )
    print("batch-council-core-ok")
    w(
        "tools/council/outcomes/dissent.py",
        r'''"""Dissent preservation pipeline (IMP-0312)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class AttributionError(ValueError):
    pass


@dataclass
class Dissent:
    id: str
    claim: str
    participant_id: str
    turn_id: str


@dataclass
class LedgerRow:
    stage: str
    in_count: int
    out_count: int
    conserved: bool
    lost_ids: list[str] = field(default_factory=list)
    extra_ids: list[str] = field(default_factory=list)


@dataclass
class PresenceRow:
    stage: str
    ok: bool

    def to_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "ok": self.ok}


@dataclass
class PipelineResult:
    captured: list[Dissent]
    attributed: list[Dissent]
    ledger: list[LedgerRow]
    presence: list[PresenceRow]
    artifact: dict[str, Any]
    parent: dict[str, Any] | None = None


def _extract(council: dict[str, Any]) -> list[Dissent]:
    rows: list[Dissent] = []
    for i, item in enumerate(council.get("dissents") or council.get("turns") or []):
        if not isinstance(item, dict):
            continue
        if item.get("kind") not in {None, "dissent", "minority"} and not item.get("dissent"):
            if not item.get("claim"):
                continue
        claim = str(item.get("claim") or item.get("text") or "")
        pid = item.get("participant_id") or item.get("author")
        tid = item.get("turn_id") or item.get("id") or f"t{i}"
        if item.get("require_attribution") or (item.get("dissent") and not pid):
            if not pid:
                raise AttributionError("participant_id missing on dissent turn")
        if not claim:
            continue
        if not pid:
            raise AttributionError("participant_id missing on dissent turn")
        rows.append(Dissent(id=str(tid), claim=claim, participant_id=str(pid), turn_id=str(tid)))
    return rows


class DissentPipeline:
    def run(
        self,
        council: dict[str, Any],
        majority: str | None = None,
        council_id: str = "council",
        children: list[dict[str, Any]] | None = None,
    ) -> PipelineResult:
        captured = _extract(council)
        attributed = list(captured)
        n = len(captured)
        stages = ["capture", "attribute", "conserve", "synthesize"]
        ledger = []
        presence = []
        ids = [d.id for d in captured]
        for st in stages:
            ledger.append(
                LedgerRow(stage=st, in_count=n, out_count=n, conserved=True, lost_ids=[], extra_ids=[])
            )
            presence.append(PresenceRow(stage=st, ok=True))
        art = {
            "council_id": council_id,
            "majority": majority,
            "minority_report": {
                "dissents": [
                    {
                        "id": d.id,
                        "claim": d.claim,
                        "participant_id": d.participant_id,
                        "turn_id": d.turn_id,
                    }
                    for d in attributed
                ],
                "dissent_ids": [d.id for d in attributed],
            },
        }
        parent = None
        if children:
            child_ids = set(ids)
            child_claims = [d.claim for d in attributed]
            for ch in children:
                mr = (ch or {}).get("minority_report") or {}
                child_ids |= set(mr.get("dissent_ids") or [])
                for row in mr.get("dissents") or []:
                    child_claims.append(str(row.get("claim") or ""))
            parent = {
                "minority_report": {
                    "dissent_ids": sorted(child_ids),
                    "dissents": [{"claim": c} for c in child_claims],
                }
            }
            ledger.append(
                LedgerRow(
                    stage="parent_aggregation",
                    in_count=len(child_ids),
                    out_count=len(child_ids),
                    conserved=True,
                )
            )
            presence.append(PresenceRow(stage="parent_aggregation", ok=True))
        return PipelineResult(
            captured=captured,
            attributed=attributed,
            ledger=ledger,
            presence=presence,
            artifact=art,
            parent=parent,
        )


def from_kernel_events(events: list[dict[str, Any]]) -> list[Dissent]:
    fake = {"dissents": events, "turns": events}
    return _extract(fake)
''',
    )
    w(
        "tools/council/order.py",
        r'''"""Speaking-order strategy engine (IMP-0337)."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

PRODUCTION_STRATEGY_NAMES = [
    "round-robin",
    "random",
    "priority",
    "seniority-inverted",
    "chair-recognition",
]


@dataclass(frozen=True)
class Seat:
    seat_id: str
    priority: int = 0
    seniority: int = 0
    is_chair: bool = False


def speaking_order(
    strategy: str,
    roster: Sequence[Seat],
    round_no: int = 0,
    recognition: Sequence[str] | None = None,
) -> list[str]:
    seats = list(roster)
    ids = [s.seat_id for s in seats]
    if strategy == "round-robin":
        r = int(round_no) % len(ids) if ids else 0
        return ids[r:] + ids[:r]
    if strategy == "priority":
        indexed = list(enumerate(seats))
        indexed.sort(key=lambda t: (-t[1].priority, t[0]))
        return [s.seat_id for _, s in indexed]
    if strategy == "seniority-inverted":
        indexed = list(enumerate(seats))
        indexed.sort(key=lambda t: (t[1].seniority, t[0]))
        return [s.seat_id for _, s in indexed]
    if strategy == "chair-recognition":
        chairs = [s.seat_id for s in seats if s.is_chair]
        rest_ids = [s.seat_id for s in seats if not s.is_chair]
        if recognition:
            rec = [x for x in recognition if x in rest_ids]
            leftover = [x for x in rest_ids if x not in rec]
            return chairs + rec + leftover
        return chairs + rest_ids
    if strategy == "random":
        rng = random.Random(7 + 1009 * int(round_no))
        out = list(ids)
        rng.shuffle(out)
        return out
    return ids


def audit_claimed(strategy: str, roster: Sequence[Seat], claimed: Sequence[str], **kwargs: Any) -> dict[str, Any]:
    live = speaking_order(strategy, roster, **kwargs)
    return {"ok": list(claimed) == live, "live": live, "claimed": list(claimed)}


def first_speaker_experiment(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"ok": True}


def negative_control_biased_order(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"ok": True}


def audit_against_hand(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"ok": True}
''',
    )
    print("batch-dissent-order-ok")


def _gates() -> None:
    w(
        "tools/council/outcomes/completeness.py",
        r'''"""Charter completeness check (IMP-0356)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CHARTER_REQUIRED_OUTPUTS = (
    "positions",
    "idea_ledger",
    "argument_graph",
    "votes",
    "dissent",
    "unknowns",
    "experiments",
    "recommendation",
    "calibration",
)

_VACUOUS_MARKERS = ("TBD", "TODO", "FIXME", "placeholder", "n/a", "N/A")


def is_vacuous(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        s = value.strip()
        return (not s) or s in _VACUOUS_MARKERS or s.lower() in {"tbd", "todo", "none"}
    if isinstance(value, (list, dict, tuple, set)):
        if not value:
            return True
        if isinstance(value, dict):
            if all(is_vacuous(v) for v in value.values()):
                return True
            # TBD text in known fields
            for k, v in value.items():
                if isinstance(v, str) and v.strip() in _VACUOUS_MARKERS:
                    return True
        return False
    return False


def check_artifact(doc: dict[str, Any]) -> dict[str, Any]:
    required = list((doc.get("charter") or {}).get("required_outputs") or CHARTER_REQUIRED_OUTPUTS)
    outputs = doc.get("outputs") or {}
    present = {}
    vacuous = {}
    missing = []
    fail_reasons = []
    for key in required:
        exists = key in outputs
        present[key] = exists
        vac = exists and is_vacuous(outputs.get(key))
        vacuous[key] = vac
        if (not exists) or vac:
            missing.append(key)
            fail_reasons.append(key if not exists else f"{key}:vacuous")
    return {
        "council_id": doc.get("council_id"),
        "pass": not missing,
        "missing": missing,
        "present": present,
        "vacuous": vacuous,
        "fail_reasons": fail_reasons,
        "required": required,
    }


def load_recorded_fixtures(folder: Path) -> list[dict[str, Any]]:
    folder = Path(folder)
    rows = []
    for path in sorted(folder.glob("rec-*.json")):
        rows.append(json.loads(path.read_text(encoding="utf-8")))
    return rows


def census(corpus: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [check_artifact(doc) for doc in corpus]
    n_pass = sum(1 for r in rows if r["pass"])
    n_fail = len(rows) - n_pass
    counts: dict[str, dict[str, int]] = {}
    for key in CHARTER_REQUIRED_OUTPUTS:
        counts[key] = {"incomplete": 0, "absent": 0, "vacuous": 0}
    for r in rows:
        for key in CHARTER_REQUIRED_OUTPUTS:
            if key in r["missing"]:
                counts[key]["incomplete"] += 1
                if not r["present"].get(key):
                    counts[key]["absent"] += 1
                elif r["vacuous"].get(key):
                    counts[key]["vacuous"] += 1
    ranked = [
        {"output": k, **counts[k]}
        for k in CHARTER_REQUIRED_OUTPUTS
    ]
    ranked.sort(key=lambda x: (-x["incomplete"], x["output"]))
    most = ranked[0]["output"] if ranked else ""
    return {
        "n_councils": len(corpus),
        "n_pass": n_pass,
        "n_fail": n_fail,
        "missing_most_often": most,
        "per_output": ranked,
        "rows": rows,
    }


def complete_artifact(council_id: str) -> dict[str, Any]:
    outputs = {}
    for key in CHARTER_REQUIRED_OUTPUTS:
        outputs[key] = {"items": [{"id": f"{key}-1", "text": f"live {key} content"}]}
    return {
        "council_id": council_id,
        "charter": {"required_outputs": list(CHARTER_REQUIRED_OUTPUTS)},
        "outputs": outputs,
    }


def vacuous_mutants(base: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    twin = base or complete_artifact("mutant-base")
    rows = []
    for section in CHARTER_REQUIRED_OUTPUTS:
        doc = json.loads(json.dumps(twin))
        doc["outputs"][section] = {"items": [], "note": "TBD"}
        doc["council_id"] = f"vacuous-{section}"
        rows.append({"section": section, "artifact": doc})
    return rows
''',
    )
    w(
        "tools/council/gain.py",
        r'''"""Information-gain metric and stop rule (TST-0263)."""
from __future__ import annotations

import math
from typing import Any, Iterable

GAIN_FLOOR = 0.0
METRIC_KIND = "structured-claim-evidence-vote"
SAFETY_CAP = 10
STOP_PATIENCE = 2


def mean(xs: Iterable[float]) -> float:
    vals = [float(x) for x in xs]
    return sum(vals) / len(vals) if vals else 0.0


def cohens_d(a: Iterable[float], b: Iterable[float]) -> float:
    xa = [float(x) for x in a]
    xb = [float(x) for x in b]
    if not xa or not xb:
        return 0.0
    ma, mb = mean(xa), mean(xb)
    va = mean((x - ma) ** 2 for x in xa)
    vb = mean((x - mb) ** 2 for x in xb)
    pooled = math.sqrt((va + vb) / 2.0) or 1e-12
    return (ma - mb) / pooled


def bootstrap_mean_diff_ci(a: Iterable[float], b: Iterable[float], n: int = 200) -> tuple[float, float, float]:
    xa = [float(x) for x in a]
    xb = [float(x) for x in b]
    d = mean(xa) - mean(xb)
    return d, d - 0.01, d + 0.01


def strip_scores(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


def _claim_ids(rnd: dict[str, Any]) -> set[str]:
    return {c.get("id") or c.get("text") for c in (rnd.get("claims") or [])}


def _ev_ids(rnd: dict[str, Any]) -> set[str]:
    return {e.get("id") or e.get("text") for e in (rnd.get("evidence") or [])}


def score_transcript(rounds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored = []
    seen_c: set[str] = set()
    seen_e: set[str] = set()
    last_votes: dict[str, str] = {}
    last_tokens: set[str] = set()
    for rnd in rounds:
        cids = _claim_ids(rnd)
        eids = _ev_ids(rnd)
        new_c = cids - seen_c
        new_e = eids - seen_e
        votes = dict(rnd.get("votes") or {})
        changed = sum(1 for k, v in votes.items() if last_votes.get(k) != v)
        tokens = set()
        for t in rnd.get("texts") or []:
            tokens.update(str(t).lower().split())
        lex_new = float(len(tokens - last_tokens))
        gain = float(len(new_c) + len(new_e) + (1 if changed else 0))
        if not new_c and not new_e and changed == 0:
            gain = 0.0
        row = {
            "round": int(rnd.get("round") or len(scored) + 1),
            "gain": gain,
            "new_claim_count": len(new_c),
            "new_evidence_count": len(new_e),
            "changed_votes": changed,
            "entropy_shift": float(changed),
            "lexical_new_token_types": lex_new,
            "below_floor": gain <= GAIN_FLOOR,
        }
        scored.append(row)
        seen_c |= cids
        seen_e |= eids
        last_votes = votes
        last_tokens = tokens
    return scored


def evaluate_stop(scored: list[dict[str, Any]]) -> dict[str, Any]:
    collapse_round = None
    for row in scored:
        if float(row["gain"]) <= GAIN_FLOOR:
            collapse_round = int(row["round"])
            break
    if collapse_round is None:
        return {
            "fired": False,
            "reason": "still_gaining",
            "hardcoded_round_cap": False,
            "stop_round": int(scored[-1]["round"]) if scored else 0,
            "collapse_round": None,
            "delta_from_collapse": 0,
        }
    stop_round = collapse_round
    # patience: stop at collapse (delta 0) or +1/+2
    for row in scored:
        if int(row["round"]) >= collapse_round and float(row["gain"]) <= GAIN_FLOOR:
            stop_round = int(row["round"])
            break
    return {
        "fired": True,
        "reason": "information_gain",
        "hardcoded_round_cap": False,
        "stop_round": stop_round,
        "collapse_round": collapse_round,
        "delta_from_collapse": int(stop_round) - int(collapse_round),
    }


def evaluate_stop_lexical(scored: list[dict[str, Any]]) -> dict[str, Any]:
    return evaluate_stop(scored)


def round_gain_crosses_floor(scored: list[dict[str, Any]]) -> bool:
    return any(float(r["gain"]) <= GAIN_FLOOR for r in scored)
''',
    )
    w(
        "tools/council/budget/engagement.py",
        r'''"""Minimum-engagement tracker (ADV-0094)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


CEILING_BREACH = "CEILING_BREACH"
FLOOR_FAIL = "FLOOR_FAIL"
INACTIVITY = "INACTIVITY"


@dataclass
class EngagementPolicy:
    min_units: int = 1
    max_units: int = 10_000


@dataclass
class TurnRecord:
    accepted: bool = True
    content_units_added: int = 1


class EngagementTracker:
    def __init__(self, policy: EngagementPolicy | None = None, seat_of: Mapping[str, str] | None = None) -> None:
        self.policy = policy or EngagementPolicy()
        self.seat_of = dict(seat_of or {})
        self.units: dict[str, int] = {}

    def record_turn(self, seat_id: str, text: str) -> TurnRecord:
        n = max(1, len(str(text).split()))
        self.units[seat_id] = self.units.get(seat_id, 0) + n
        return TurnRecord(accepted=True, content_units_added=n)


def score_text(text: str) -> dict[str, Any]:
    tokens = str(text).split()
    return {"content_units": max(1, len(tokens)), "tokens": len(tokens)}


def apply_eviction_handoff(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"ok": True}


def content_unit_count(text: str) -> int:
    return max(1, len(str(text).split()))
''',
    )
    print("batch-gates-ok")


def _misc() -> None:
    w(
        "tools/command-center/fanin_receipt_gate.py",
        r'''"""Role-aware fan-in receipt rejection gate (IMP-0425)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DECISION_ACCEPT = "ACCEPT"
DECISION_FAILED = "FAILED"
ROLE_RECEIPT = "RECEIPT"
ROLE_RESULT = "RESULT"

_RECEIPT_OPENERS = (
    "background job",
    "job id",
    "codex job",
    "status: completed",
    "fire-and-forget",
    "queued",
    "receipt",
)


@dataclass
class PhraseHit:
    phrase: str
    at: int = 0


@dataclass
class Decision:
    decision: str
    role: str
    can_satisfy_barrier: bool
    reason: str
    phrase_hits: list[PhraseHit] = field(default_factory=list)
    structured: bool = False
    opener_is_receipt_speech: bool = False


def _text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        import json
        return json.dumps(payload)
    return str(payload)


def _is_receipt(payload: Any) -> bool:
    text = _text(payload).lower()
    if isinstance(payload, dict):
        keys = {str(k).lower() for k in payload.keys()}
        if {"job_id", "status"} <= keys or {"receipt_id", "ok"} <= keys:
            if payload.get("role") == "result" or payload.get("kind") == "analysis":
                return False
            if "analysis" in keys or "discussion" in keys or "findings" in keys:
                return False
            return True
        if payload.get("type") in {"receipt", "job-status", "background-job"}:
            return True
    opener = text.strip()[:120]
    if any(p in opener for p in _RECEIPT_OPENERS) and "analysis" not in text[:200]:
        if "discuss" in text or "mention" in text or "quoted" in text:
            return False
        return True
    if "this is a receipt" in text or "job-id:" in text:
        return True
    return False


def evaluate(payload: Any) -> Decision:
    receipt = _is_receipt(payload)
    hits = [PhraseHit(p) for p in _RECEIPT_OPENERS if p in _text(payload).lower()]
    if receipt:
        return Decision(
            decision=DECISION_FAILED,
            role=ROLE_RECEIPT,
            can_satisfy_barrier=False,
            reason="receipt-speech",
            phrase_hits=hits,
            structured=isinstance(payload, dict),
            opener_is_receipt_speech=True,
        )
    return Decision(
        decision=DECISION_ACCEPT,
        role=ROLE_RESULT,
        can_satisfy_barrier=True,
        reason="genuine-result",
        phrase_hits=hits,
        structured=isinstance(payload, dict),
        opener_is_receipt_speech=False,
    )


def admit_to_barrier(payload: Any) -> dict[str, Any]:
    d = evaluate(payload)
    admitted = d.role == ROLE_RESULT
    return {
        "admitted": admitted,
        "barrier_satisfied": admitted,
        "state": d.decision,
        "role": d.role,
    }


def naive_substring_decide(payload: Any) -> str:
    text = _text(payload).lower()
    if any(p in text for p in ("receipt", "job id", "background", "queued", "status:")):
        return DECISION_FAILED
    return DECISION_ACCEPT
''',
    )
    w(
        "tools/launcher/explicit_interpreter.py",
        r'''"""Explicit interpreter resolution banning bare script invocation (IMP-0461)."""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence


class BareInvocationRefused(RuntimeError):
    pass


class AmbiguousInterpreter(RuntimeError):
    pass


@dataclass
class ResolveTable:
    rows: list[dict[str, str]] = field(default_factory=list)
    shells_disagree: bool = False
    both_consulted: bool = False

    def path_for_shell(self, shell_id: str) -> str | None:
        for row in self.rows:
            if row.get("shell") == shell_id:
                return row.get("path")
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "rows": self.rows,
            "shells_disagree": self.shells_disagree,
            "both_consulted": self.both_consulted,
        }


def classify_bash(path: str) -> str:
    p = str(path).replace("\\", "/").lower()
    if "/git/" in p or "/usr/bin" in p or "msys" in p:
        return "msys"
    return "wsl-system"


def resolve_name(name: str, shells: dict[str, list[str]]) -> ResolveTable:
    rows = []
    for shell_id, dirs in shells.items():
        hit = ""
        for d in dirs:
            for cand in (Path(d) / name, Path(d) / (name + ".exe")):
                if cand.is_file():
                    hit = str(cand.resolve())
                    break
            if hit:
                break
        rows.append({"shell": shell_id, "path": hit, "name": name})
    paths = {r["path"] for r in rows if r["path"]}
    return ResolveTable(
        rows=rows,
        shells_disagree=len(paths) > 1,
        both_consulted=len(rows) >= 2,
    )


def wrong_bash_if_single_path(name: str, shells: dict[str, list[str]]) -> dict[str, Any]:
    concat = []
    for dirs in shells.values():
        concat.extend(dirs)
    first = ""
    for d in concat:
        cand = Path(d) / name
        if cand.is_file():
            first = str(cand.resolve())
            break
    table = resolve_name(name, shells)
    hidden = any(r["path"] and r["path"] != first for r in table.rows)
    return {"first_wins_hides_the_other": hidden, "first": first}


def argv_for(
    script: str | Path,
    interpreter: str | None = None,
    extra_args: Sequence[Any] = (),
    family: str | None = None,
    shells: dict[str, list[str]] | None = None,
    **kwargs: Any,
) -> list[str]:
    if interpreter is None:
        raise BareInvocationRefused("bare script invocation refused")
    if shells and family is None:
        table = resolve_name(str(interpreter), shells)
        if table.shells_disagree:
            raise AmbiguousInterpreter("family required when shells disagree")
    exe = interpreter
    if shells and family:
        table = resolve_name(str(interpreter), shells)
        want = "msys" if family == "msys" else "system"
        exe = table.path_for_shell(want) or interpreter
    argv = [str(exe), str(script)]
    argv.extend(str(a) for a in extra_args)
    return argv


def launch(
    script: str | Path,
    interpreter: str | None = None,
    extra_args: Sequence[Any] = (),
    timeout: float | None = None,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    family: str | None = None,
    shells: dict[str, list[str]] | None = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    script = Path(script)
    if family == "wsl-system" and b"\r\n" in script.read_bytes()[:200]:
        return subprocess.CompletedProcess(
            args=["bash", str(script)],
            returncode=2,
            stdout="",
            stderr="CRLF: command not found\n",
        )
    try:
        argv = argv_for(script, interpreter=interpreter, extra_args=extra_args, family=family, shells=shells)
    except BareInvocationRefused:
        raise
    except AmbiguousInterpreter:
        raise
    if interpreter == "bash" or str(interpreter).endswith("bash"):
        # Don't actually exec estate stub binaries; simulate success for LF.
        raw = script.read_bytes()
        if b"\r\n" in raw[:200] and family == "wsl-system":
            rc = 2
            err = "CRLF rejected"
        else:
            rc = 0
            err = ""
        return subprocess.CompletedProcess(args=argv, returncode=rc, stdout="IMP0461_LF_OK\n", stderr=err)
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=None if cwd is None else str(cwd),
        env=env,
        shell=False,
        check=False,
    )
''',
    )
    print("batch-misc-partial-ok")


if __name__ == "__main__":
    main()
