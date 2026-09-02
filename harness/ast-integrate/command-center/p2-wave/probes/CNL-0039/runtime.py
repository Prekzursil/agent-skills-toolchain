"""Executable attack-real checker for the 7 ADVERSARIAL protocols."""
from __future__ import annotations

import hashlib
from typing import Any

FAMILY = "ADVERSARIAL"

# Turn order is the executable schedule. Missing schedule => NOT-EXECUTABLE.
SCHEDULES: dict[str, list[str]] = {
    "P07": ["proposition", "opposition", "proposition", "opposition"],
    "P08": ["blue", "red", "referee"],
    "P09": ["thesis", "antithesis", "thesis"],
    "P10": ["majority", "devil", "majority"],
    "P11": ["team_a", "team_b", "comparator"],
    "P12": ["side_yes", "side_no", "registrar"],
    "P13": ["witness", "examiner", "witness", "examiner"],
}

ATTACKING_ROLE = {
    "P07": "opposition",
    "P08": "red",
    "P09": "antithesis",
    "P10": "devil",
    "P11": "team_b",
    "P12": "side_no",
    "P13": "examiner",
}

ARTIFACT_KIND = {
    "P07": "clash_ledger",
    "P08": "exploit_repro",
    "P09": "contradiction_witness",
    "P10": "steelman_opposite",
    "P11": "discrepancy_table",
    "P12": "preregistered_falsifier",
    "P13": "pin_exhibit",
}


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _turns(transcript: dict) -> list[dict]:
    turns = transcript.get("turns") or []
    if not isinstance(turns, list):
        return []
    return [t for t in turns if isinstance(t, dict)]


def _arts(transcript: dict) -> dict:
    arts = transcript.get("artifacts") or {}
    return arts if isinstance(arts, dict) else {}


def _texts(turns: list[dict], role: str) -> list[str]:
    return [str(t.get("text") or "") for t in turns if t.get("role") == role]


def check_schedule(protocol_id: str, turns: list[dict]) -> str | None:
    expected = SCHEDULES.get(protocol_id)
    if not expected:
        return "missing-turn-schedule"
    got = [str(t.get("role") or "") for t in turns]
    if got != expected:
        return f"schedule-mismatch expected={expected} got={got}"
    return None


def _p07(turns: list[dict], arts: dict) -> list[str]:
    v: list[str] = []
    prop = _texts(turns, "proposition")
    prop_hash = {digest_text(t): t for t in prop}
    ledger = arts.get("clash_ledger") or []
    if not isinstance(ledger, list) or not ledger:
        return ["empty-clash-ledger"]
    bound = 0
    for row in ledger:
        if not isinstance(row, dict):
            v.append("malformed-clash-row")
            continue
        qh = str(row.get("quoted_sha256") or "")
        defeater = str(row.get("defeater") or "")
        if qh not in prop_hash:
            v.append("unbound-quote")
            continue
        bound += 1
        if not defeater.strip():
            v.append("empty-defeater")
        elif defeater.strip() == prop_hash[qh].strip():
            v.append("defeater-restates-prop")
    if bound < 1:
        v.append("no-bound-clash")
    return v


def _p08(turns: list[dict], arts: dict) -> list[str]:
    v: list[str] = []
    body = str(arts.get("blue_artifact") or "")
    repro = arts.get("exploit_repro") or {}
    if not isinstance(repro, dict):
        return ["malformed-exploit-repro"]
    needle = str(repro.get("needle") or "")
    if not needle:
        return ["empty-exploit-needle"]
    if needle not in body:
        v.append("oracle-did-not-fail")
    blue = _texts(turns, "blue")
    if blue and digest_text(blue[0]) != str(arts.get("blue_artifact_sha256") or ""):
        v.append("artifact-unbound-from-blue-turn")
    return v


def _p09(turns: list[dict], arts: dict) -> list[str]:
    claims = arts.get("thesis_claims") or []
    if not isinstance(claims, list) or not claims:
        return ["empty-thesis-claims"]
    by_id = {
        str(c.get("id")): str(c.get("text") or "")
        for c in claims
        if isinstance(c, dict) and c.get("id")
    }
    wit = arts.get("contradiction_witness") or {}
    if not isinstance(wit, dict):
        return ["malformed-contradiction-witness"]
    cid = str(wit.get("negates") or "")
    if cid not in by_id:
        return ["witness-unbound-claim"]
    form = str(wit.get("form") or "")
    of = str(wit.get("of") or "")
    if form != "not" or of != cid:
        return ["witness-not-negation"]
    expected = f"NOT({by_id[cid]})"
    anti = _texts(turns, "antithesis")
    if not anti or anti[0].strip() != expected:
        return ["antithesis-text-not-negation"]
    return []


def _p10(turns: list[dict], arts: dict) -> list[str]:
    maj = _texts(turns, "majority")
    devil = _texts(turns, "devil")
    if not maj or not devil:
        return ["missing-majority-or-devil-turn"]
    steel = arts.get("steelman_opposite") or {}
    if not isinstance(steel, dict):
        return ["malformed-steelman"]
    v: list[str] = []
    if steel.get("majority_sha256") != digest_text(maj[0]):
        v.append("steelman-unbound-majority")
    if steel.get("opposite_sha256") != digest_text(devil[0]):
        v.append("steelman-not-devil-text")
    if devil[0].strip() == maj[0].strip():
        v.append("devil-restates-majority")
    return v


def _p11(turns: list[dict], arts: dict) -> list[str]:
    a = arts.get("team_a_judgments") or {}
    b = arts.get("team_b_judgments") or {}
    table = arts.get("discrepancy_table") or []
    if not isinstance(a, dict) or not isinstance(b, dict):
        return ["malformed-estimates"]
    if not isinstance(table, list) or not table:
        return ["empty-discrepancy-table"]
    v: list[str] = []
    diffs = 0
    for row in table:
        if not isinstance(row, dict):
            v.append("malformed-discrepancy-row")
            continue
        key = str(row.get("key") or "")
        if key not in a or key not in b:
            v.append("discrepancy-key-missing")
            continue
        if row.get("team_a") != a.get(key) or row.get("team_b") != b.get(key):
            v.append("discrepancy-does-not-match-estimates")
            continue
        if a.get(key) != b.get(key):
            diffs += 1
    if diffs < 1:
        v.append("no-actual-discrepancy")
    a_turns = _texts(turns, "team_a")
    b_turns = _texts(turns, "team_b")
    if a_turns and digest_text(a_turns[0]) != str(arts.get("team_a_sha256") or ""):
        v.append("team-a-unbound")
    if b_turns and digest_text(b_turns[0]) != str(arts.get("team_b_sha256") or ""):
        v.append("team-b-unbound")
    return v


def _p12(_turns: list[dict], arts: dict) -> list[str]:
    pre = arts.get("preregistered_falsifier") or {}
    if not isinstance(pre, dict):
        return ["malformed-preregistered-falsifier"]
    yes_p = str(pre.get("yes_prediction") or "")
    no_p = str(pre.get("no_prediction") or "")
    v: list[str] = []
    if not yes_p or not no_p:
        v.append("empty-prediction")
    if yes_p == no_p:
        v.append("compatible-predictions")
    if pre.get("yes_sig") != digest_text("side_yes|" + yes_p):
        v.append("bad-yes-sig")
    if pre.get("no_sig") != digest_text("side_no|" + no_p):
        v.append("bad-no-sig")
    return v


def _p13(turns: list[dict], arts: dict) -> list[str]:
    uttered = _texts(turns, "witness")
    hashes = {digest_text(t): t for t in uttered}
    pin = arts.get("pin_exhibit") or {}
    if not isinstance(pin, dict):
        return ["malformed-pin-exhibit"]
    a_h = str(pin.get("statement_a_sha256") or "")
    b_h = str(pin.get("statement_b_sha256") or "")
    v: list[str] = []
    if a_h not in hashes or b_h not in hashes:
        v.append("pin-unbound-witness")
        return v
    if a_h == b_h:
        v.append("pin-same-statement")
    if pin.get("relation") != "contradicts":
        v.append("pin-relation-not-contradicts")
    a_txt, b_txt = hashes[a_h], hashes[b_h]
    if b_txt.strip() != f"NOT({a_txt.strip()})" and a_txt.strip() != f"NOT({b_txt.strip()})":
        v.append("pin-not-syntactic-negation")
    return v


_CHECKERS = {
    "P07": _p07,
    "P08": _p08,
    "P09": _p09,
    "P10": _p10,
    "P11": _p11,
    "P12": _p12,
    "P13": _p13,
}


def check_transcript(transcript: dict[str, Any]) -> dict[str, Any]:
    pid = str(transcript.get("protocol_id") or "")
    turns = _turns(transcript)
    arts = _arts(transcript)
    violations: list[str] = []
    sched = check_schedule(pid, turns)
    if sched:
        violations.append(sched)
    checker = _CHECKERS.get(pid)
    if checker is None:
        violations.append("no-checker")
    elif sched is None:
        violations.extend(checker(turns, arts))
    fired = len(violations) > 0
    return {
        "protocol_id": pid,
        "fired": fired,
        "silent": not fired,
        "violations": violations,
        "verdict": "PERFORMED-ATTACK" if fired else "REAL-ATTACK",
        "attacking_role": ATTACKING_ROLE.get(pid),
        "artifact_kind": ARTIFACT_KIND.get(pid),
    }


def schedule_for(protocol_id: str) -> list[str] | None:
    return SCHEDULES.get(protocol_id)


def verdict_for(protocol_id: str) -> dict[str, Any]:
    sched = SCHEDULES.get(protocol_id)
    if not sched:
        return {
            "verdict": "NOT-EXECUTABLE",
            "missing_element": "turn_schedule",
            "turn_schedule": [],
        }
    return {
        "verdict": "EXECUTABLE",
        "missing_element": None,
        "turn_schedule": list(sched),
        "attacking_role": ATTACKING_ROLE[protocol_id],
        "artifact_kind": ARTIFACT_KIND[protocol_id],
    }
