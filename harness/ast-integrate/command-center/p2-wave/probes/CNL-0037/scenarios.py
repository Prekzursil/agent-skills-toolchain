"""Named fixtures for CNL-0037."""
from fanin import evidence_digest

EV_PASS_A = {"id": "ev-alpha-method", "body": "Child alpha measured predicate P on artifact A; bytes=4096; sha recorded."}
EV_PASS_B = {"id": "ev-beta-method", "body": "Child beta measured the same predicate P on artifact A independently."}
EV_REFUTE_C = {"id": "ev-gamma-counter", "body": "Child gamma produced counterexample X that falsifies P on artifact A."}


def _child(cid, verdict, ev, dissent=None, present=True, nbytes=4096):
    rec = dict(ev)
    rec["digest"] = evidence_digest(ev["id"], ev["body"])
    return {
        "child_id": cid,
        "verdict": verdict,
        "artifact_present": present,
        "artifact_bytes": nbytes,
        "evidence": [rec],
        "dissent": list(dissent or []),
    }


def agreeing_pass():
    return {"id": "agreeing-pass", "children": [_child("alpha", "PASS", EV_PASS_A), _child("beta", "PASS", EV_PASS_B)], "parent_ingested": {}, "overrule": None}


def disagree_irreducible():
    return {
        "id": "disagree-irreducible",
        "children": [
            _child("alpha", "PASS", EV_PASS_A),
            _child("gamma", "REFUTED", EV_REFUTE_C, dissent=[{"id": "dissent-gamma-1", "text": "P fails on X"}]),
        ],
        "parent_ingested": {},
        "overrule": None,
    }


def majority_trap():
    return {
        "id": "majority-trap",
        "children": [
            _child("alpha", "PASS", EV_PASS_A),
            _child("beta", "PASS", EV_PASS_B),
            _child("gamma", "REFUTED", EV_REFUTE_C, dissent=[{"id": "dissent-gamma-1", "text": "P fails on X"}]),
        ],
        "parent_ingested": {},
        "overrule": None,
    }


def overrule_cited():
    rec = EV_REFUTE_C
    digest = evidence_digest(rec["id"], rec["body"])
    return {
        "id": "overrule-cited",
        "children": [
            _child("alpha", "PASS", EV_PASS_A),
            _child("gamma", "REFUTED", EV_REFUTE_C, dissent=[{"id": "dissent-gamma-1", "text": "P fails on X"}]),
        ],
        "parent_ingested": {rec["id"]: rec["body"]},
        "overrule": {
            "target_child_id": "gamma",
            "new_verdict": "PASS",
            "cited": [{"id": rec["id"], "digest": digest}],
            "rationale": "Parent read gamma's counterexample X and judged it out of scope.",
        },
    }


def overrule_blind():
    rec = EV_REFUTE_C
    digest = evidence_digest(rec["id"], rec["body"])
    return {
        "id": "overrule-blind",
        "children": [_child("alpha", "PASS", EV_PASS_A), _child("gamma", "REFUTED", EV_REFUTE_C)],
        "parent_ingested": {},
        "overrule": {
            "target_child_id": "gamma",
            "new_verdict": "PASS",
            "cited": [{"id": rec["id"], "digest": digest}],
            "rationale": "Parent copied gamma's evidence id from the header and never read the body.",
        },
    }


def overrule_wrong_digest():
    rec = EV_REFUTE_C
    return {
        "id": "overrule-wrong-digest",
        "children": [_child("alpha", "PASS", EV_PASS_A), _child("gamma", "REFUTED", EV_REFUTE_C)],
        "parent_ingested": {rec["id"]: rec["body"]},
        "overrule": {
            "target_child_id": "gamma",
            "new_verdict": "PASS",
            "cited": [{"id": rec["id"], "digest": "0" * 64}],
            "rationale": "Parent cited the id with a fabricated digest.",
        },
    }


def overrule_cross_child():
    rec = EV_PASS_A
    digest = evidence_digest(rec["id"], rec["body"])
    return {
        "id": "overrule-cross-child",
        "children": [_child("alpha", "PASS", EV_PASS_A), _child("gamma", "REFUTED", EV_REFUTE_C)],
        "parent_ingested": {rec["id"]: rec["body"]},
        "overrule": {
            "target_child_id": "gamma",
            "new_verdict": "PASS",
            "cited": [{"id": rec["id"], "digest": digest}],
            "rationale": "Parent cited alpha's evidence to overrule gamma.",
        },
    }


def claim_without_artifact():
    return {
        "id": "claim-without-artifact",
        "children": [_child("alpha", "PASS", EV_PASS_A, present=False, nbytes=0), _child("beta", "PASS", EV_PASS_B)],
        "parent_ingested": {},
        "overrule": None,
    }


def completion_split():
    return {
        "id": "completion-split",
        "children": [_child("done-child", "PASS", EV_PASS_A), _child("blocked-child", "BLOCKED", EV_REFUTE_C)],
        "parent_ingested": {},
        "overrule": None,
    }
