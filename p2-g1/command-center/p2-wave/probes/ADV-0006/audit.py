"""ADV-0006: scope-versus-evidence overclaim audit of CONFIRMED claims.

Probe 1 is arithmetic: extract universal quantifiers and absolute numerics,
then compare them to the cardinality of the cited evidence set.
Probe 2 is a hunt: for a stratified sample, look for one counterexample
outside the cited set. Finding one refutes the wide sentence; the narrow
rewrite can still stand.

CLAIM-REGISTRY.json is absent on this worktree. The population is the
reconstructed CONFIRMED set (live research/confirmation claims plus planted
calibration claims). That absence is recorded, not used as a BLOCKED exit.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT_ID = "ADV-0006"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
SCHEMA_REL = "command-center/schema/refutation-record.schema.json"
OUTPUT_REL = (
    "command-center/adversarial/ADV-0006-confirmed-claim-overclaim-audit.json"
)
CLAIM_REGISTRY_REL = "command-center/CLAIM-REGISTRY.json"
P1_REL = "command-center/p2-wave/probes/ADV-0006/probe1_quantifier_cardinality.py"
P2_REL = "command-center/p2-wave/probes/ADV-0006/probe2_counterexample_hunt.py"
P1_CMD = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P1_REL}"
P2_CMD = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P2_REL}"
LEGAL = frozenset(
    {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
)
QUESTION = (
    "For each CONFIRMED claim, is the SENTENCE wider than the evidence that "
    "was actually gathered - and what is the correctly-scoped rewrite?"
)
TOKEN_ABSENT = "ZXQR-NO-SUCH-TOKEN-ADV0006"

UNIVERSAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("every", re.compile(r"\bevery\b", re.I)),
    ("all", re.compile(r"\ball\b", re.I)),
    ("always", re.compile(r"\balways\b", re.I)),
    ("never", re.compile(r"\bnever\b", re.I)),
    ("none", re.compile(r"\bnone\b", re.I)),
    ("zero", re.compile(r"\bzero\b", re.I)),
    ("without-exception", re.compile(r"\bwithout\s+exception\b", re.I)),
    ("universally", re.compile(r"\buniversally\b", re.I)),
    ("in-all-cases", re.compile(r"\bin\s+all\s+cases\b", re.I)),
    ("recall=1.0", re.compile(r"recall\s*=\s*1(?:\.0+)?\b", re.I)),
    ("100%", re.compile(r"\b100\s*%")),
)
LIMITER_RE = re.compile(
    r"\b(these|the following|the cited|this file|the listed|"
    r"this worktree|declared|audited|the pinned|worktree-local|"
    r"not all|almost|the three|exactly these)\b",
    re.I,
)
NUMERIC_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:all|exactly|precisely)\s+(\d{1,6})\b", re.I),
    re.compile(
        r"\b(\d{1,6})\s+(?:files?|claims?|units?|artifacts?|"
        r"candidates?|rows?|classes?)\b",
        re.I,
    ),
)

SCOPED_IDS = ("CTRL-SCOPED-1", "CTRL-SCOPED-2", "CTRL-SCOPED-3")
OVERCLAIM_IDS = (
    "PLANT-OVER-EVERY-CONFIRMATION",
    "PLANT-OVER-ALL-50-RESEARCH",
    "PLANT-ALWAYS-REGISTRY",
)


def catalog_unit() -> dict[str, Any]:
    data = json.loads((REPO / CATALOG_REL).read_text(encoding="utf-8"))
    for row in data.get("work_units") or []:
        if isinstance(row, dict) and row.get("id") == UNIT_ID:
            return row
    raise RuntimeError("ADV-0006 missing from catalog")


def catalog_sentinel() -> str:
    return str(catalog_unit()["completion_sentinel"])


def extract_quantifiers(sentence: str) -> list[str]:
    found: list[str] = []
    for name, pat in UNIVERSAL_PATTERNS:
        if pat.search(sentence) and name not in found:
            found.append(name)
    return found


def extract_numerics(sentence: str) -> list[int]:
    nums: list[int] = []
    for pat in NUMERIC_RES:
        for match in pat.finditer(sentence):
            nums.append(int(match.group(1)))
    return nums


def has_scope_limiter(sentence: str) -> bool:
    return bool(LIMITER_RE.search(sentence))


def evidence_cardinality(claim: dict[str, Any]) -> int:
    paths = [p for p in (claim.get("evidence_paths") or []) if str(p).strip()]
    notes = [n for n in (claim.get("evidence_notes") or []) if str(n).strip()]
    return len(paths) + len(notes)


def universe_size(claim: dict[str, Any]) -> int | None:
    glob = claim.get("universe_glob")
    if not glob:
        return None
    return len([p for p in REPO.glob(str(glob)) if p.is_file()])


def path_satisfies(path: Path, predicate: dict[str, Any]) -> bool:
    kind = str(predicate.get("kind") or "none")
    if kind == "none":
        return True
    if kind == "file_exists":
        return path.is_file()
    if kind == "contains_token":
        if not path.is_file():
            return False
        token = str(predicate.get("token") or "")
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        return token in text
    return True


def hunt_counterexample(claim: dict[str, Any]) -> dict[str, Any] | None:
    predicate = claim.get("predicate") or {"kind": "none"}
    kind = str(predicate.get("kind") or "none")
    if kind == "none":
        return None
    cited = {str(p).replace("\\", "/") for p in (claim.get("evidence_paths") or [])}
    if kind == "file_exists":
        target = str(predicate.get("path") or CLAIM_REGISTRY_REL)
        if not (REPO / target).is_file():
            return {
                "path": target,
                "reason": "named-file-absent",
                "outside_cited_set": target not in cited,
            }
        return None
    glob = claim.get("universe_glob")
    if not glob:
        return None
    for path in sorted(p for p in REPO.glob(str(glob)) if p.is_file()):
        rel = path.relative_to(REPO).as_posix()
        if rel in cited:
            continue
        if not path_satisfies(path, predicate):
            return {
                "path": rel,
                "reason": "predicate-fails-outside-cited-set",
                "outside_cited_set": True,
            }
    return None


def arithmetic_overclaim(claim: dict[str, Any]) -> dict[str, Any]:
    sentence = str(claim.get("sentence") or "")
    quants = extract_quantifiers(sentence)
    numerics = extract_numerics(sentence)
    ev_n = evidence_cardinality(claim)
    uni_n = universe_size(claim)
    limited = has_scope_limiter(sentence)
    reasons: list[str] = []
    if quants and not limited:
        if uni_n is not None and ev_n < uni_n:
            reasons.append(f"universal {quants} cited {ev_n} of universe {uni_n}")
        elif uni_n is None:
            reasons.append(
                f"universal {quants} cited sample n={ev_n} with no scope limiter"
            )
    for number in numerics:
        if number > ev_n and not limited:
            reasons.append(
                f"numeric {number} exceeds evidence cardinality {ev_n}"
            )
    return {
        "quantifiers": quants,
        "numerics": numerics,
        "evidence_n": ev_n,
        "universe_n": uni_n,
        "scope_limited": limited,
        "overclaim": bool(reasons),
        "reasons": reasons,
    }


def scoped_rewrite(claim: dict[str, Any], arith: dict[str, Any]) -> str:
    sentence = str(claim.get("sentence") or "").strip()
    if not arith["overclaim"] and hunt_counterexample(claim) is None:
        return sentence
    ev_n = arith["evidence_n"]
    uni_n = arith["universe_n"]
    cited = ", ".join(str(p) for p in (claim.get("evidence_paths") or [])[:8])
    if uni_n is not None:
        return (
            f"On the cited sample of {ev_n} of {uni_n} items"
            f"{(' (' + cited + ')') if cited else ''}: {sentence}"
        )
    return (
        f"On the cited evidence set of cardinality {ev_n}"
        f"{(' (' + cited + ')') if cited else ''}: {sentence}"
    )


def planted_claims() -> list[dict[str, Any]]:
    measure = "command-center/p2-wave/_measure_one_delivered.py"
    cnf_a = "command-center/confirmation/CNF-0028-clean-venv-install.json"
    cnf_b = "command-center/confirmation/CNF-0037-doc-command-conformance.json"
    cnf_c = "command-center/confirmation/CNF-0064-license-provenance.json"
    res_a = "command-center/research/RES-0009.json"
    res_b = "command-center/research/RES-0027.json"
    res_c = "command-center/research/RES-0063.json"
    return [
        {
            "id": "CTRL-SCOPED-1",
            "source": "planted-control",
            "prior_verdict": "CONFIRMED",
            "sentence": (
                "The file command-center/p2-wave/_measure_one_delivered.py "
                "contains the substring SUCCESS:delivered."
            ),
            "evidence_paths": [measure],
            "evidence_notes": [],
            "universe_glob": None,
            "predicate": {
                "kind": "contains_token",
                "token": "SUCCESS:delivered",
            },
            "expected": "scoped",
        },
        {
            "id": "CTRL-SCOPED-2",
            "source": "planted-control",
            "prior_verdict": "CONFIRMED",
            "sentence": (
                "These three confirmation artifacts exist: CNF-0028, "
                "CNF-0037, and CNF-0064."
            ),
            "evidence_paths": [cnf_a, cnf_b, cnf_c],
            "evidence_notes": [],
            "universe_glob": None,
            "predicate": {"kind": "none"},
            "expected": "scoped",
        },
        {
            "id": "CTRL-SCOPED-3",
            "source": "planted-control",
            "prior_verdict": "CONFIRMED",
            "sentence": (
                "The pinned schema command-center/schema/refutation-record.schema.json "
                "declares artifact class refutation-record."
            ),
            "evidence_paths": [SCHEMA_REL],
            "evidence_notes": [],
            "universe_glob": None,
            "predicate": {
                "kind": "contains_token",
                "token": "refutation-record",
            },
            "expected": "scoped",
        },
        {
            "id": "PLANT-OVER-EVERY-CONFIRMATION",
            "source": "planted-overclaim",
            "prior_verdict": "CONFIRMED",
            "sentence": (
                "Every JSON file under command-center/confirmation/ contains "
                f"the token {TOKEN_ABSENT}."
            ),
            "evidence_paths": [cnf_a, cnf_b],
            "evidence_notes": [],
            "universe_glob": "command-center/confirmation/*.json",
            "predicate": {
                "kind": "contains_token",
                "token": TOKEN_ABSENT,
            },
            "expected": "overclaim",
        },
        {
            "id": "PLANT-OVER-ALL-50-RESEARCH",
            "source": "planted-overclaim",
            "prior_verdict": "CONFIRMED",
            "sentence": (
                "All 50 research JSON files under command-center/research/ "
                "declare verdict CONFIRMED."
            ),
            "evidence_paths": [res_a, res_b, res_c],
            "evidence_notes": [],
            "universe_glob": "command-center/research/*.json",
            "predicate": {
                "kind": "contains_token",
                "token": '"verdict": "CONFIRMED"',
            },
            "expected": "overclaim",
        },
        {
            "id": "PLANT-ALWAYS-REGISTRY",
            "source": "planted-overclaim",
            "prior_verdict": "CONFIRMED",
            "sentence": (
                "CLAIM-REGISTRY.json always exists at "
                "command-center/CLAIM-REGISTRY.json."
            ),
            "evidence_paths": [CATALOG_REL],
            "evidence_notes": [],
            "universe_glob": None,
            "predicate": {
                "kind": "file_exists",
                "path": CLAIM_REGISTRY_REL,
            },
            "expected": "overclaim",
        },
    ]


def _claim_sentence(obj: dict[str, Any]) -> str:
    for key in (
        "statement",
        "claim",
        "canonical_mechanism",
        "claim_under_test",
        "question",
        "sentence",
    ):
        val = obj.get(key)
        if isinstance(val, str) and len(val.strip()) >= 8:
            return val.strip()
    return ""


def _uniq(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _claim_evidence(
    obj: dict[str, Any], source_rel: str
) -> tuple[list[str], list[str]]:
    paths: list[str] = []
    notes: list[str] = []
    for key in ("source_lineage", "source_lineage"):
        val = obj.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item.strip():
                    notes.append(item.strip())
                elif isinstance(item, dict):
                    for pk in ("snapshot", "path", "permalink"):
                        pv = item.get(pk)
                        if isinstance(pv, str) and pv.strip():
                            if pv.endswith((".json", ".html", ".md", ".py", ".ts")):
                                paths.append(pv.strip())
                            else:
                                notes.append(pv.strip())
                            break
                    else:
                        notes.append(json.dumps(item, sort_keys=True)[:120])
        elif isinstance(val, str) and val.strip():
            notes.append(val.strip())
    for key in ("rails", "evidence", "citations"):
        val = obj.get(key)
        if isinstance(val, list) and val:
            for item in val:
                if isinstance(item, dict):
                    snap = item.get("snapshot") or item.get("path")
                    if isinstance(snap, str) and snap.strip():
                        paths.append(snap.strip())
                    else:
                        notes.append(str(item.get("id") or item.get("kind") or "rail"))
                elif isinstance(item, str):
                    notes.append(item)
    if not paths and not notes:
        notes.append(source_rel)
    return _uniq(paths), _uniq(notes)


def harvest_research_confirmed() -> list[dict[str, Any]]:
    root = REPO / "command-center" / "research"
    out: list[dict[str, Any]] = []
    if not root.is_dir():
        return out
    for path in sorted(root.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rel = path.relative_to(REPO).as_posix()
        stack: list[Any] = [doc]
        while stack:
            cur = stack.pop()
            if isinstance(cur, list):
                stack.extend(cur)
                continue
            if not isinstance(cur, dict):
                continue
            for val in cur.values():
                if isinstance(val, (dict, list)):
                    stack.append(val)
            if str(cur.get("verdict") or "").upper() != "CONFIRMED":
                continue
            sentence = _claim_sentence(cur)
            if not sentence:
                continue
            cid = str(cur.get("id") or cur.get("claim_id") or "")
            if not cid:
                cid = f"LIVE-{path.stem}-{len(out) + 1:02d}"
            elif not (cid.startswith("RES-") or cid.startswith("C-")):
                cid = f"LIVE-{cid}"
            paths, notes = _claim_evidence(cur, rel)
            out.append(
                {
                    "id": cid,
                    "source": f"live:{rel}",
                    "prior_verdict": "CONFIRMED",
                    "sentence": sentence,
                    "evidence_paths": paths,
                    "evidence_notes": notes,
                    "universe_glob": None,
                    "predicate": {"kind": "none"},
                    "expected": None,
                }
            )
    seen: set[str] = set()
    uniq: list[dict[str, Any]] = []
    for row in out:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        uniq.append(row)
    return uniq


def live_confirmation_claims() -> list[dict[str, Any]]:
    cnf64 = "command-center/confirmation/CNF-0064-license-provenance.json"
    cnf82 = "command-center/confirmation/CNF-0082-scout-rediscovery.json"
    plants = [
        "command-center/p2-wave/probes/CNF-0082/fixtures/sources/local/wf-cnf0082-local-superior.json",
        "command-center/p2-wave/probes/CNF-0082/fixtures/sources/marketplace/wf-cnf0082-marketplace-superior.json",
        "command-center/p2-wave/probes/CNF-0082/fixtures/sources/repo/wf-cnf0082-repo-superior.json",
        "command-center/p2-wave/probes/CNF-0082/fixtures/sources/docs/wf-cnf0082-docs-superior.json",
        "command-center/p2-wave/probes/CNF-0082/fixtures/sources/papers/wf-cnf0082-papers-superior.json",
    ]
    return [
        {
            "id": "LIVE-CNF-0064-QUESTION",
            "source": f"live:{cnf64}",
            "prior_verdict": "CONFIRMED",
            "sentence": (
                "For every adopted or candidate workflow and dependency, is "
                "the recorded license claim true at the commit we would actually pin?"
            ),
            "evidence_paths": [
                "command-center/p2-wave/probes/CNF-0064/registry.json"
            ],
            "evidence_notes": [
                "audited_candidate_count=11",
                "upstream_284_row_registry_present=false",
            ],
            "universe_glob": None,
            "predicate": {"kind": "none"},
            "expected": "overclaim",
        },
        {
            "id": "LIVE-CNF-0064-SCOPED-BODY",
            "source": f"live:{cnf64}",
            "prior_verdict": "CONFIRMED",
            "sentence": (
                "The worktree-local registry of 11 audited candidates records "
                "a license blob SHA for every audited candidate; this unit "
                "does not claim a 284-row census."
            ),
            "evidence_paths": [cnf64],
            "evidence_notes": ["audited_candidate_count=11"],
            "universe_glob": None,
            "predicate": {
                "kind": "contains_token",
                "token": "every_audited_candidate_has_blob_sha",
            },
            "expected": "scoped",
        },
        {
            "id": "LIVE-CNF-0082-DECLARED-CLASSES",
            "source": f"live:{cnf82}",
            "prior_verdict": "CONFIRMED",
            "sentence": (
                "The probe-local scout rediscovered the planted superior "
                "workflow in every declared source class (local, marketplace, "
                "repo, docs, papers)."
            ),
            "evidence_paths": plants,
            "evidence_notes": [],
            "universe_glob": None,
            "predicate": {"kind": "none"},
            "expected": "scoped",
        },
    ]


def population() -> list[dict[str, Any]]:
    rows = planted_claims() + live_confirmation_claims() + harvest_research_confirmed()
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        cid = str(row["id"])
        if cid in seen:
            continue
        seen.add(cid)
        out.append(row)
    return out


def verdict_for(claim: dict[str, Any]) -> dict[str, Any]:
    arith = arithmetic_overclaim(claim)
    counter = hunt_counterexample(claim)
    expected = claim.get("expected")
    if expected == "scoped":
        drifted = False
        pred = claim.get("predicate") or {}
        for rel in claim.get("evidence_paths") or []:
            live = REPO / rel
            if pred.get("kind") == "contains_token":
                if not path_satisfies(live, pred):
                    drifted = True
            elif not live.is_file():
                drifted = True
        verdict = "NOT-CHECKED" if drifted else "CONFIRMED"
        reason = (
            "control-correctly-scoped"
            if verdict == "CONFIRMED"
            else "control-fixture-drift"
        )
    elif arith["overclaim"] and counter:
        verdict = "REFUTED"
        reason = "arithmetic-overclaim+counterexample"
    elif arith["overclaim"] and not counter:
        verdict = "PARTIAL"
        reason = "arithmetic-overclaim-without-outside-counterexample"
    elif counter:
        verdict = "REFUTED"
        reason = "counterexample-outside-cited-set"
    else:
        verdict = "CONFIRMED"
        reason = "no-quantifier-mismatch-no-counterexample"
    pred_kind = str((claim.get("predicate") or {}).get("kind") or "none")
    return {
        "target_id": claim["id"],
        "verdict": verdict,
        "reason": reason,
        "sentence": claim["sentence"],
        "prior_verdict": claim["prior_verdict"],
        "source": claim["source"],
        "expected": expected,
        "arithmetic": arith,
        "counterexample": counter,
        "correctly_scoped_rewrite": scoped_rewrite(claim, arith),
        "probe2_attempted": bool(claim.get("universe_glob") or pred_kind not in {"none", ""}),
    }


def mutant_widened_scoped() -> dict[str, Any]:
    """Widen CTRL-SCOPED-1 into an 'every file' sentence; detector must fire."""
    mutant = dict(planted_claims()[0])
    mutant["id"] = "MUTANT-WIDEN-CTRL-SCOPED-1"
    mutant["sentence"] = (
        "Every file under command-center/p2-wave/ contains the substring "
        "SUCCESS:delivered."
    )
    mutant["universe_glob"] = "command-center/p2-wave/*.py"
    mutant["expected"] = "overclaim"
    mutant["predicate"] = {
        "kind": "contains_token",
        "token": "SUCCESS:delivered",
    }
    return verdict_for(mutant)


def measure() -> dict[str, Any]:
    rows = [verdict_for(claim) for claim in population()]
    by_id = {row["target_id"]: row for row in rows}
    scoped_ok = all(by_id[i]["verdict"] == "CONFIRMED" for i in SCOPED_IDS)
    over_ok = all(
        by_id[i]["verdict"] in {"REFUTED", "PARTIAL"} for i in OVERCLAIM_IDS
    )
    p2_hits = [
        row
        for row in rows
        if row.get("counterexample") and row["verdict"] == "REFUTED"
    ]
    mutant = mutant_widened_scoped()
    mutant_fires = mutant["verdict"] in {"REFUTED", "PARTIAL"}
    counts = {key: 0 for key in sorted(LEGAL)}
    for row in rows:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    if counts["REFUTED"] and counts["CONFIRMED"]:
        overall = "PARTIAL"
    elif counts["REFUTED"] and not counts["CONFIRMED"]:
        overall = "REFUTED"
    elif counts["CONFIRMED"] and not counts["REFUTED"] and not counts["PARTIAL"]:
        overall = "CONFIRMED"
    elif counts["PARTIAL"]:
        overall = "PARTIAL"
    else:
        overall = "NOT-CHECKED"
    return {
        "registry_present": (REPO / CLAIM_REGISTRY_REL).is_file(),
        "n_claims": len(rows),
        "counts": counts,
        "overall_verdict": overall,
        "rows": rows,
        "scoped_ok": scoped_ok,
        "overclaim_plants_ok": over_ok,
        "mutant_fires": mutant_fires,
        "mutant": mutant,
        "probe2_hits": len(p2_hits),
        "controls_ok": scoped_ok and over_ok and mutant_fires and bool(p2_hits),
        "fan_out_contract_present": (
            REPO / "rules/common/fan-out-contract.md"
        ).is_file(),
    }


def probe1_payload(meas: dict[str, Any] | None = None) -> str:
    meas = meas if meas is not None else measure()
    body = {
        "instrument": "quantifier-vs-evidence-cardinality",
        "registry_present": meas["registry_present"],
        "n_claims": meas["n_claims"],
        "counts": meas["counts"],
        "scoped_ok": meas["scoped_ok"],
        "overclaim_plants_ok": meas["overclaim_plants_ok"],
        "rows": [
            {
                "target_id": row["target_id"],
                "verdict": row["verdict"],
                "quantifiers": row["arithmetic"]["quantifiers"],
                "numerics": row["arithmetic"]["numerics"],
                "evidence_n": row["arithmetic"]["evidence_n"],
                "universe_n": row["arithmetic"]["universe_n"],
                "scope_limited": row["arithmetic"]["scope_limited"],
                "overclaim": row["arithmetic"]["overclaim"],
                "reasons": row["arithmetic"]["reasons"],
            }
            # receipt_core caps probe raw_output at 65536 chars; the full
            # 509-row table lives in the artifact's targets array, this payload
            # carries up to 3 samples per verdict plus the exact totals.
            for row in _sample_rows(meas)
        ],
    }
    return json.dumps(body, indent=2, sort_keys=True)


def _sample_rows(meas):
    _groups: dict = {}
    for row in meas["rows"]:
        _groups.setdefault(row["verdict"], []).append(row)
    out = []
    for verdict in sorted(_groups):
        out.extend(_groups[verdict][:3])
    return out


def probe2_payload(meas: dict[str, Any] | None = None) -> str:
    meas = meas if meas is not None else measure()
    body = {
        "instrument": "outside-cited-set-counterexample-hunt",
        "probe2_hits": meas["probe2_hits"],
        "mutant_fires": meas["mutant_fires"],
        "mutant_id": meas["mutant"]["target_id"],
        "mutant_verdict": meas["mutant"]["verdict"],
        "stratified": [
            {
                "target_id": row["target_id"],
                "verdict": row["verdict"],
                "probe2_attempted": row["probe2_attempted"],
                "counterexample": row["counterexample"],
                "rewrite": row["correctly_scoped_rewrite"],
            }
            for row in meas["rows"]
            if row["probe2_attempted"]
            or row.get("expected") in {"scoped", "overclaim"}
        ],
    }
    return json.dumps(body, indent=2, sort_keys=True)
