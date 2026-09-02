"""Planted mutant matrix, live uniqueness-gate discovery, two similarity spaces.

Live gate = tools/council/quota/unique_ideas.py when present; otherwise the
CouncilSpec unique_idea target as actually evaluated by quota.targets
(currently skipped). Absence is recorded as accept-all, not as BLOCKED.

Second space = canonical-mechanism identity. Lexical space = token Jaccard.
Reject-all is a calibration mutant, never a pass for the anti-gaming claim.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
FIXTURES = HERE / "fixtures" / "mutants.json"
UNIQUE_IDEAS_REL = "tools/council/quota/unique_ideas.py"
UNIQUE_IDEAS = REPO / UNIQUE_IDEAS_REL
TARGETS_REL = "tools/council/quota/targets.py"
IMP0300 = REPO / "command-center" / "receipts" / "IMP-0300.json"
IMP0290 = REPO / "command-center" / "receipts" / "IMP-0290.json"
ART_REL = "command-center/adversarial/ADV-0096-idea-count-gaming-uniqueness-gate.json"
ART = REPO / ART_REL
UNIT = "ADV-0096"

GAMING_CLASSES = (
    "exact_rename",
    "synonym_swap",
    "one_parameter_fork",
    "reordered_composition",
)
ALL_CLASSES = GAMING_CLASSES + ("genuinely_distinct",)
DECISIONS = frozenset({"accept", "reject"})
TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "for",
        "in",
        "on",
        "is",
        "at",
        "by",
        "per",
        "each",
    }
)
# Conservative lexical collapse: near-copies, not synonyms.
LEXICAL_THRESHOLD = 0.72
SYNONYM_MAP = {
    "ballot": "vote",
    "ballots": "vote",
    "tally": "vote",
    "proof": "evidence",
    "exhibit": "evidence",
    "pack": "bundle",
    "payload": "bytes",
    "digest": "hash",
    "checksum": "hash",
    "cycle": "round",
    "sitting": "round",
    "solitary": "one",
    "permit": "admit",
    "normalised": "canonical",
    "normalized": "canonical",
    "keyed": "per",
    "sha": "hash",
    "256": "hash",
    "bit": "",
    "cryptographic": "",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def planted() -> dict[str, Any]:
    return load_json(FIXTURES)


def seed_idea() -> dict[str, Any]:
    return planted()["seed"]


def mutants() -> list[dict[str, Any]]:
    rows = planted()["mutants"]
    got = [str(r["class"]) for r in rows]
    if got != list(ALL_CLASSES):
        raise RuntimeError(f"mutant class order {got} != {list(ALL_CLASSES)}")
    return rows


def tokens(text: str) -> frozenset[str]:
    words = TOKEN_RE.findall((text or "").casefold())
    return frozenset(w for w in words if len(w) >= 2 and w not in STOP)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def idea_text(idea: dict[str, Any]) -> str:
    return " ".join(
        str(idea.get(k) or "")
        for k in ("title", "text", "mechanism")
        if idea.get(k)
    )


def body_tokens(idea: dict[str, Any]) -> frozenset[str]:
    return tokens(str(idea.get("text") or ""))


def canonical_mechanism(idea: dict[str, Any]) -> str:
    mech = str(idea.get("mechanism") or "").strip().lower()
    parts = [str(p).strip().lower() for p in (idea.get("composition") or [])]
    parts = [p for p in parts if p]
    return f"{mech}|{','.join(sorted(parts))}"


def synonym_normalized_tokens(idea: dict[str, Any]) -> frozenset[str]:
    out: set[str] = set()
    for tok in body_tokens(idea):
        mapped = SYNONYM_MAP.get(tok, tok)
        if mapped:
            out.add(mapped)
    return frozenset(out)


def lexical_decide(seed: dict[str, Any], cand: dict[str, Any]) -> dict[str, Any]:
    score = jaccard(body_tokens(seed), body_tokens(cand))
    decision = "reject" if score >= LEXICAL_THRESHOLD else "accept"
    return {
        "space": "lexical-token-jaccard",
        "decision": decision,
        "score": round(score, 6),
        "threshold": LEXICAL_THRESHOLD,
    }


def mechanism_decide(seed: dict[str, Any], cand: dict[str, Any]) -> dict[str, Any]:
    left = canonical_mechanism(seed)
    right = canonical_mechanism(cand)
    syn = jaccard(synonym_normalized_tokens(seed), synonym_normalized_tokens(cand))
    same_mech = left == right
    # One-parameter forks share mechanism+composition; synonyms share mechanism.
    decision = "reject" if same_mech else "accept"
    return {
        "space": "canonical-mechanism",
        "decision": decision,
        "seed_key": left,
        "cand_key": right,
        "synonym_token_jaccard": round(syn, 6),
        "same_mechanism_key": same_mech,
    }


def string_eq_decide(seed: dict[str, Any], cand: dict[str, Any]) -> dict[str, Any]:
    same = str(seed.get("text") or "") == str(cand.get("text") or "")
    return {
        "space": "pure-string-equality-on-body",
        "decision": "reject" if same else "accept",
        "same_body": same,
    }


def reject_all_decide(_seed: dict[str, Any], _cand: dict[str, Any]) -> dict[str, Any]:
    return {"space": "reject-all-calibration", "decision": "reject"}


def accept_all_decide(_seed: dict[str, Any], _cand: dict[str, Any]) -> dict[str, Any]:
    return {"space": "accept-all", "decision": "accept"}


def _try_import_unique_ideas() -> tuple[Any | None, str]:
    if not UNIQUE_IDEAS.is_file():
        return None, "file-absent"
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location(
        "council_quota_unique_ideas", UNIQUE_IDEAS
    )
    if spec is None or spec.loader is None:
        return None, "spec-unreadable"
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:  # noqa: BLE001 — live import is the measurement
        return None, f"import-error:{type(exc).__name__}"
    return mod, "imported"


def _unique_ideas_callable(mod: Any) -> Callable[..., Any] | None:
    for name in ("decide", "accept", "is_unique", "evaluate", "count_unique"):
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn
    return None


def _json_plain(value: Any, depth: int = 0) -> Any:
    """Council quota stubs (_NS / Result) must not leak into probe receipts."""
    if depth > 8:
        return str(type(value).__name__)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_plain(v, depth + 1) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_plain(v, depth + 1) for k, v in value.items()}
    name = type(value).__name__
    if name == "Result" and hasattr(value, "as_dict"):
        return _json_plain(value.as_dict(), depth + 1)
    if name == "_NS":
        return None
    return str(value)


def quota_unique_idea_skip(seed: dict[str, Any], cand: dict[str, Any]) -> dict[str, Any]:
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    from council.quota.targets import evaluate  # noqa: WPS433 — live import

    spec = {
        "targets": [
            {
                "id": "unique-ideas",
                "kind": "unique_idea",
                "min_count": 100,
            }
        ]
    }
    snapshot = {"ideas": [seed, cand]}
    report = evaluate(spec, snapshot)
    raw_rows = report.get("results") if hasattr(report, "get") else None
    if type(raw_rows).__name__ == "_NS" or not isinstance(raw_rows, (list, tuple)):
        rows: list[Any] = []
    else:
        rows = list(raw_rows)
    row = rows[0] if rows else {}
    if not isinstance(row, dict):
        row = {}
    skipped_targets = report.get("skipped_count_targets") if hasattr(report, "get") else None
    if type(skipped_targets).__name__ == "_NS" or skipped_targets is None:
        skipped_targets = []
    return {
        "skipped": bool(row.get("skipped")),
        "pass": _json_plain(row.get("pass")),
        "reason": _json_plain(row.get("reason")),
        "kind": _json_plain(row.get("kind")),
        "skipped_count_targets": _json_plain(list(skipped_targets)),
        "all_non_count_pass": _json_plain(
            report.get("all_non_count_pass") if hasattr(report, "get") else None
        ),
    }


def discover_live_gate() -> dict[str, Any]:
    mod, import_state = _try_import_unique_ideas()
    skip = quota_unique_idea_skip(seed_idea(), mutants()[0])
    if mod is not None and _unique_ideas_callable(mod) is not None:
        kind = "unique_ideas.py"
        decision_mode = "module-callable"
    elif UNIQUE_IDEAS.is_file():
        kind = "unique_ideas.py-present-not-callable"
        decision_mode = "absent-noop-accept-all"
    else:
        kind = "absent-noop-accept-all"
        decision_mode = "absent-noop-accept-all"
    return {
        "unique_ideas_rel": UNIQUE_IDEAS_REL,
        "unique_ideas_exists": UNIQUE_IDEAS.is_file(),
        "unique_ideas_bytes": UNIQUE_IDEAS.stat().st_size if UNIQUE_IDEAS.is_file() else 0,
        "import_state": import_state,
        "callable_present": bool(mod is not None and _unique_ideas_callable(mod)),
        "imp0300_exists": IMP0300.is_file(),
        "imp0290_exists": IMP0290.is_file(),
        "quota_skip": skip,
        "kind": kind,
        "decision_mode": decision_mode,
        "targets_rel": TARGETS_REL,
        "targets_exists": (REPO / TARGETS_REL).is_file(),
        "note": (
            "IMP-0300 unique_ideas.py is the catalog-declared brainstorm "
            "uniqueness counter. This unit measures whatever is on disk; it "
            "does not implement that module."
        ),
    }


def live_decide(seed: dict[str, Any], cand: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    if gate["decision_mode"] == "module-callable":
        mod, _ = _try_import_unique_ideas()
        fn = _unique_ideas_callable(mod) if mod is not None else None
        if fn is None:
            return {**accept_all_decide(seed, cand), "reason": "callable-lost"}
        try:
            raw = fn(seed, cand)
        except TypeError:
            try:
                raw = fn([seed, cand])
            except Exception as exc:  # noqa: BLE001
                return {
                    **accept_all_decide(seed, cand),
                    "reason": f"call-error:{type(exc).__name__}",
                }
        if isinstance(raw, dict) and raw.get("decision") in DECISIONS:
            return {
                "space": "unique_ideas.py",
                "decision": raw["decision"],
                "raw_keys": sorted(raw.keys()),
            }
        if isinstance(raw, str) and raw.lower() in DECISIONS:
            return {"space": "unique_ideas.py", "decision": raw.lower()}
        if raw is True:
            return {"space": "unique_ideas.py", "decision": "accept"}
        if raw is False:
            return {"space": "unique_ideas.py", "decision": "reject"}
        return {
            "space": "unique_ideas.py",
            "decision": "accept",
            "reason": f"unparsed-return:{type(raw).__name__}",
        }
    # Live unique_idea target is skipped: no reject function exists.
    skip = gate.get("quota_skip") or {}
    return {
        **accept_all_decide(seed, cand),
        "space": "live-unique-idea-target",
        "reason": "count_target_skipped" if skip.get("skipped") else gate["kind"],
        "quota_skip": skip,
    }


DecideFn = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


def matrix_for(decide: DecideFn, seed: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    seed = seed or seed_idea()
    rows = []
    for cand in mutants():
        rec = decide(seed, cand)
        decision = rec["decision"]
        if decision not in DECISIONS:
            raise RuntimeError(f"bad decision {decision!r} for {cand['class']}")
        want = str(cand["want_if_gate_works"])
        rows.append(
            {
                "id": cand["id"],
                "class": cand["class"],
                "want_if_gate_works": want,
                "decision": decision,
                "matches_working_gate": decision == want,
                "detail": rec,
            }
        )
    return rows


def discrimination(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_class = {r["class"]: r for r in rows}
    gaming = [by_class[c] for c in GAMING_CLASSES]
    distinct = by_class["genuinely_distinct"]
    tp = sum(1 for r in gaming if r["decision"] == "reject")
    fn = sum(1 for r in gaming if r["decision"] == "accept")
    distinct_ok = distinct["decision"] == "accept"
    reject_all = distinct["decision"] == "reject" and tp == len(gaming)
    return {
        "n_gaming": len(gaming),
        "true_positive_rejects": tp,
        "false_negative_accepts": fn,
        "recall_on_gaming_classes": round(tp / len(gaming), 6) if gaming else 0.0,
        "distinct_accepted": distinct_ok,
        "distinct_decision": distinct["decision"],
        "reject_all": reject_all,
        "anti_gaming_pass": bool(tp == len(gaming) and distinct_ok),
        "gaming_succeeds": bool(fn > 0 and distinct_ok),
        "destroying_brainstorm": bool(not distinct_ok),
    }


def both_spaces_overlay(
    lexical_rows: list[dict[str, Any]],
    mechanism_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    lex = {r["class"]: r for r in lexical_rows}
    mech = {r["class"]: r for r in mechanism_rows}
    out = []
    for cls in ALL_CLASSES:
        ldec = lex[cls]["decision"]
        mdec = mech[cls]["decision"]
        if ldec == "accept" and mdec == "accept":
            fate = "survives-both"
        elif ldec == "reject" and mdec == "reject":
            fate = "caught-by-both"
        elif ldec == "reject":
            fate = "caught-only-lexical"
        else:
            fate = "caught-only-mechanism"
        out.append(
            {
                "class": cls,
                "lexical": ldec,
                "mechanism": mdec,
                "fate": fate,
                "want_if_gate_works": lex[cls]["want_if_gate_works"],
            }
        )
    return out


def reject_all_control() -> dict[str, Any]:
    seed = seed_idea()
    bad = matrix_for(lambda s, c: reject_all_decide(s, c), seed)
    good = matrix_for(lambda s, c: accept_all_decide(s, c), seed)
    bad_d = discrimination(bad)
    good_d = discrimination(good)
    fired = bool(bad_d["destroying_brainstorm"])
    silent = bool(good_d["distinct_accepted"] and not good_d["destroying_brainstorm"])
    return {
        "id": "NC-REJECT-ALL-CALIBRATION",
        "fired_on_bad_state": fired,
        "silent_on_good_state": silent,
        "bad_distinct_decision": bad_d["distinct_decision"],
        "good_distinct_decision": good_d["distinct_decision"],
        "reported_as": (
            "failure-not-pass" if fired else "calibration-did-not-go-red"
        ),
        "note": (
            "A gate that rejects the genuinely distinct idea destroys the "
            "brainstorm and is a failure, not an anti-gaming pass."
        ),
    }


def distinct_control(rows: list[dict[str, Any]]) -> dict[str, Any]:
    disc = discrimination(rows)
    return {
        "id": "T-DISTINCT-CONTROL",
        "distinct_accepted": disc["distinct_accepted"],
        "distinct_decision": disc["distinct_decision"],
        "reject_all": disc["reject_all"],
        "result": (
            "FAIL"
            if disc["destroying_brainstorm"]
            else "PASS"
        ),
    }


def run_probe1() -> dict[str, Any]:
    gate = discover_live_gate()
    seed = seed_idea()

    def _live(s: dict[str, Any], c: dict[str, Any]) -> dict[str, Any]:
        return live_decide(s, c, gate)

    live_rows = matrix_for(_live, seed)
    live_d = discrimination(live_rows)
    string_rows = matrix_for(lambda s, c: string_eq_decide(s, c), seed)
    nc = reject_all_control()
    dc = distinct_control(live_rows)
    if live_d["destroying_brainstorm"]:
        verdict = "CONFIRMED"
        note = "live gate rejects the distinct idea (reject-all / over-collapse)"
    elif live_d["gaming_succeeds"]:
        verdict = "CONFIRMED"
        note = "live uniqueness surface accepts wording variants"
    elif live_d["anti_gaming_pass"]:
        verdict = "REFUTED"
        note = "live gate rejects planted variants and accepts the distinct idea"
    else:
        verdict = "PARTIAL"
        note = "live matrix is mixed"
    payload = {
        "probe": "probe1_live_gate",
        "unit_id": UNIT,
        "catalog_probe": (
            "Probe 1: run the planted mutant set through the gate and record "
            "accept/reject per mutant class."
        ),
        "live_gate": gate,
        "matrix": live_rows,
        "discrimination": live_d,
        "string_equality_matrix": string_rows,
        "string_equality_discrimination": discrimination(string_rows),
        "distinct_control": dc,
        "negative_control": nc,
        "verdict": verdict,
        "note": note,
        "pass": bool(
            len(live_rows) == 5
            and nc["fired_on_bad_state"]
            and nc["silent_on_good_state"]
            and all(r["decision"] in DECISIONS for r in live_rows)
        ),
    }
    return _json_plain(payload)


def run_probe2() -> dict[str, Any]:
    seed = seed_idea()
    lexical_rows = matrix_for(lambda s, c: lexical_decide(s, c), seed)
    mechanism_rows = matrix_for(lambda s, c: mechanism_decide(s, c), seed)
    overlay = both_spaces_overlay(lexical_rows, mechanism_rows)
    lex_d = discrimination(lexical_rows)
    mech_d = discrimination(mechanism_rows)
    survive_both = [r for r in overlay if r["fate"] == "survives-both"]
    gaming_survive_both = [
        r for r in survive_both if r["class"] in GAMING_CLASSES
    ]
    only_one = [
        r
        for r in overlay
        if r["fate"] in {"caught-only-lexical", "caught-only-mechanism"}
    ]
    live = discover_live_gate()
    live_rows = matrix_for(lambda s, c: live_decide(s, c, live), seed)
    live_by = {r["class"]: r for r in live_rows}
    live_overlay = []
    for src in overlay:
        cls = src["class"]
        ldec = live_by[cls]["decision"]
        mdec = src["mechanism"]
        if ldec == "accept" and mdec == "accept":
            fate_live = "survives-both"
        elif ldec == "reject" and mdec == "reject":
            fate_live = "caught-by-both"
        elif ldec == "reject":
            fate_live = "caught-only-live"
        else:
            fate_live = "caught-only-mechanism"
        live_overlay.append(
            {
                "class": cls,
                "live": ldec,
                "lexical": src["lexical"],
                "mechanism": mdec,
                "fate_lexical_vs_mechanism": src["fate"],
                "fate_live_vs_mechanism": fate_live,
                "want_if_gate_works": src["want_if_gate_works"],
            }
        )
    nc = reject_all_control()
    if not mech_d["distinct_accepted"]:
        space_verdict = "PARTIAL"
        note = "mechanism space rejected the distinct idea"
    elif gaming_survive_both:
        space_verdict = "CONFIRMED"
        note = (
            "at least one gaming class survives both lexical and mechanism spaces"
        )
    else:
        space_verdict = "PARTIAL"
        note = (
            "no gaming class survives both spaces; classes caught by only one "
            "localise the blind space"
        )
    payload = {
        "probe": "probe2_semantic_space",
        "unit_id": UNIT,
        "catalog_probe": (
            "Probe 2 (mechanically different): a second similarity space - if "
            "the gate uses lexical similarity, evaluate with embeddings, and "
            "vice versa; a mutant class that survives BOTH is a real gap, and "
            "a class caught by only one identifies which space the gate is "
            "blind in."
        ),
        "spaces": {
            "lexical": "token-jaccard on idea body",
            "second": "canonical-mechanism identity (sorted composition, params ignored)",
            "embedding_model": None,
            "embedding_note": (
                "No embedding model is invocable on this worktree. Canonical "
                "mechanism identity is the second, non-lexical space."
            ),
        },
        "lexical_matrix": lexical_rows,
        "mechanism_matrix": mechanism_rows,
        "lexical_discrimination": lex_d,
        "mechanism_discrimination": mech_d,
        "overlay_lexical_vs_mechanism": overlay,
        "overlay_live_vs_mechanism": live_overlay,
        "gaming_classes_surviving_both_spaces": [
            r["class"] for r in gaming_survive_both
        ],
        "classes_caught_by_only_one_space": only_one,
        "negative_control": nc,
        "distinct_control_mechanism": distinct_control(mechanism_rows),
        "distinct_control_lexical": distinct_control(lexical_rows),
        "verdict": space_verdict,
        "note": note,
        "pass": bool(
            mech_d["distinct_accepted"]
            and lex_d["distinct_accepted"]
            and nc["fired_on_bad_state"]
            and nc["silent_on_good_state"]
            and len(overlay) == 5
        ),
    }
    return _json_plain(payload)


def artifact_ok_if_present() -> str | None:
    if not ART.is_file():
        return None
    try:
        doc = load_json(ART)
    except (OSError, json.JSONDecodeError) as exc:
        return f"artifact-unparseable:{type(exc).__name__}"
    if not isinstance(doc, dict):
        return "artifact-not-object"
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"artifact-self-declared:{st}"
    blob = json.dumps(doc)
    if "SUCCESS:ADV-0096 emitted ONLY when" not in blob:
        return "artifact-sentinel-absent"
    return None
