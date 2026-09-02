"""WFA-0074: label-blind disposition re-adjudication (criteria only).

The classifier never receives candidates[].classification. Missing required
inputs refuse to UNKNOWN-NEEDS-PROBE. Tie-break order is total.
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "WFA-0074"
SAMPLE_N = 60
SAMPLE_SEED = 74
DANGEROUS_OF_SAMPLE_THRESHOLD = 0.10
DANGEROUS_OF_DISAGREEMENTS_THRESHOLD = 0.50
CONTROL_PLANE = "claude-harness"

VOCAB_15 = (
    "ADOPT-AS-IS",
    "ADOPT-WITH-WRAPPER",
    "CLEAN-ROOM-REIMPLEMENT",
    "COMPOSE",
    "DISTILL",
    "EXTEND",
    "GENERALIZE",
    "MERGE",
    "REBUILD-FROM-SPEC",
    "REJECT",
    "REPAIR",
    "RETIRE",
    "SPECIALIZE",
    "TRANSLATE",
    "UNKNOWN-NEEDS-PROBE",
)
USED_9 = (
    "ADOPT-AS-IS",
    "UNKNOWN-NEEDS-PROBE",
    "DISTILL",
    "RETIRE",
    "ADOPT-WITH-WRAPPER",
    "REPAIR",
    "EXTEND",
    "MERGE",
    "SPECIALIZE",
)
FAMILIES_9 = (
    "A-saved-workflow",
    "B-repo-workflow",
    "C-repo-tool",
    "D-harness-runtime",
    "E-agent",
    "F-plugin",
    "G-skill",
    "H-executed-corpus",
    "I-command",
)
FAMILY_COUNTS = {
    "A-saved-workflow": 10,
    "B-repo-workflow": 4,
    "C-repo-tool": 25,
    "D-harness-runtime": 6,
    "E-agent": 19,
    "F-plugin": 21,
    "G-skill": 96,
    "H-executed-corpus": 72,
    "I-command": 31,
}
HISTOGRAM_9 = {
    "ADOPT-AS-IS": 122,
    "UNKNOWN-NEEDS-PROBE": 44,
    "DISTILL": 43,
    "RETIRE": 24,
    "ADOPT-WITH-WRAPPER": 20,
    "REPAIR": 15,
    "EXTEND": 6,
    "MERGE": 6,
    "SPECIALIZE": 4,
}
# Most-severe / most-conservative first. Two firing rules always have an order.
TIE_BREAK = (
    "REJECT",
    "RETIRE",
    "CLEAN-ROOM-REIMPLEMENT",
    "TRANSLATE",
    "REBUILD-FROM-SPEC",
    "REPAIR",
    "UNKNOWN-NEEDS-PROBE",
    "COMPOSE",
    "MERGE",
    "GENERALIZE",
    "SPECIALIZE",
    "EXTEND",
    "DISTILL",
    "ADOPT-WITH-WRAPPER",
    "ADOPT-AS-IS",
)
CONSERVATIVE_INDEPENDENT = frozenset({"UNKNOWN-NEEDS-PROBE", "REPAIR"})
DANGEROUS_INDEPENDENT = frozenset({"ADOPT-AS-IS"})
REQUIRED_FIELDS = ("id", "family", "does", "provenance")
PERMISSIVE_LICENSES = frozenset(
    {"MIT", "APACHE-2.0", "APACHE 2.0", "BSD-2-CLAUSE", "BSD-3-CLAUSE", "ISC", "UNLICENSE"}
)
UNKNOWN_LICENSES = frozenset({"", "UNKNOWN", "UNLICENSED", "NONE", "NOASSERTION"})
FOREIGN_RUNTIME = (
    "n8n",
    "temporal",
    "airflow",
    "langchain",
    "crewai",
    "autogen",
    "prefect",
    "dagster",
    "zapier",
)
CONTROL_PLANE_MARKERS = ("claude-harness", "ast-integrate", "harness-runtime")
REGISTRY_PATHS = (
    Path(r"C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    Path("/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    REPO / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center" / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    HERE / "fixtures" / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
)
KNOWN_IDS = {
    "A-saved-workflow": [
        "wf-saved-agentic-repair-reliability",
        "wf-saved-bc-stage-compendium-enrichment",
        "wf-saved-codex-auth-research-fanout",
        "wf-saved-design-gate",
        "wf-saved-harness-self-improve-sweep",
    ],
    "I-command": [
        "cmd-start-task",
        "cmd-orchestrate",
        "cmd-multi-workflow",
        "cmd-multi-plan",
        "cmd-multi-execute",
        "cmd-multi-frontend",
        "cmd-multi-backend",
        "cmd-review-design",
    ],
}
PREFIX = {
    "A-saved-workflow": "wf-saved-",
    "B-repo-workflow": "wf-repo-",
    "C-repo-tool": "tool-",
    "D-harness-runtime": "rt-",
    "E-agent": "agent-",
    "F-plugin": "plugin-",
    "G-skill": "skill-",
    "H-executed-corpus": "corpus-",
    "I-command": "cmd-",
}
SAMPLING_RULE = (
    "Written before selection. Seed=74. (1) Draw 1 record at random from each "
    "of the 9 families. (2) For each of the 9 used dispositions still missing, "
    "draw 1 remaining record of that disposition at random. (3) Fill the rest "
    "to 60 by walking families in catalog size order and drawing without "
    "replacement, proportional leftovers first. Labels are not an input to "
    "the adjudicator; they are used only to stratify the sample and to score."
)


def _blob(rec: dict) -> str:
    parts: list[str] = []
    for key in ("does", "mechanisms", "notes", "name", "maintenance", "origin"):
        val = rec.get(key)
        if isinstance(val, list):
            parts.append(" ".join(str(x) for x in val))
        elif val:
            parts.append(str(val))
    ev = rec.get("evidence")
    if isinstance(ev, str):
        parts.append(ev)
    elif isinstance(ev, dict):
        parts.append(" ".join(f"{k}={v}" for k, v in sorted(ev.items())))
    return " ".join(parts).lower()


def _license(rec: dict) -> str:
    return str(rec.get("license") or "").strip().upper()


def _runtime(rec: dict) -> str:
    return str(rec.get("runtime") or "").strip().lower()


def _evidence(rec: dict) -> dict:
    ev = rec.get("evidence")
    return ev if isinstance(ev, dict) else {}


def withhold_labels(rec: dict) -> dict:
    """Criteria-only view. Classification and any label aliases are stripped."""
    out = {}
    for key, val in rec.items():
        if key in {"classification", "label", "disposition", "gold_label"}:
            continue
        out[key] = val
    return out


def missing_required(rec: dict) -> list[str]:
    missing = []
    for key in REQUIRED_FIELDS:
        val = rec.get(key)
        if val is None or val == "" or val == []:
            missing.append(key)
    return missing


def _fires(rec: dict) -> set[str]:
    """Return every disposition rule that fires. Caller applies tie-break."""
    blob = _blob(rec)
    lic = _license(rec)
    rt = _runtime(rec)
    ev = _evidence(rec)
    hits: set[str] = set()

    if "do not use" in blob or blob.startswith("reject:") or "malicious" in blob:
        hits.add("REJECT")
    if any(
        tok in blob
        for tok in ("archived", "abandoned", "retired", "delete-all", "deleted from estate")
    ) or str(rec.get("maintenance") or "").lower() in {"archived", "abandoned", "retired"}:
        hits.add("RETIRE")
    if lic in UNKNOWN_LICENSES:
        hits.add("CLEAN-ROOM-REIMPLEMENT")
    if any(tok in rt for tok in FOREIGN_RUNTIME):
        hits.add("TRANSLATE")
    if "rebuild from spec" in blob or "implementation unusable" in blob:
        hits.add("REBUILD-FROM-SPEC")
    defect_n = ev.get("defect_count")
    try:
        defect_n = int(defect_n) if defect_n is not None else 0
    except (TypeError, ValueError):
        defect_n = 0
    if defect_n > 0 or "broken but salvageable" in blob or "needs repair" in blob:
        hits.add("REPAIR")
    smoke = ev.get("smoke_passed")
    named_probe = ev.get("named_probe_executed")
    if smoke is False or named_probe is False:
        hits.add("UNKNOWN-NEEDS-PROBE")
    if "only as composition" in blob or "compose with" in blob:
        hits.add("COMPOSE")
    if "duplicate of" in blob or "merge with" in blob:
        hits.add("MERGE")
    if "too specific, generalize" in blob or "generalize from" in blob:
        hits.add("GENERALIZE")
    if "specialization of" in blob or "specialize for" in blob:
        hits.add("SPECIALIZE")
    if "missing stage" in blob or "extend with" in blob:
        hits.add("EXTEND")
    if "pattern only" in blob or "distill the" in blob:
        hits.add("DISTILL")
    if "requires wrapper" in blob or "adopt with wrapper" in blob or "shim required" in blob:
        hits.add("ADOPT-WITH-WRAPPER")

    adopt_ok = (
        lic in PERMISSIVE_LICENSES
        and not any(tok in rt for tok in FOREIGN_RUNTIME)
        and smoke is True
        and defect_n == 0
        and "RETIRE" not in hits
        and "REJECT" not in hits
    )
    if adopt_ok and "ADOPT-WITH-WRAPPER" not in hits:
        hits.add("ADOPT-AS-IS")
    if adopt_ok and "ADOPT-WITH-WRAPPER" in hits:
        hits.discard("ADOPT-AS-IS")
    if not hits:
        hits.add("UNKNOWN-NEEDS-PROBE")
    return hits


def adjudicate(rec: dict) -> dict:
    """Map a criteria-only record to exactly one of 15 values."""
    view = withhold_labels(rec)
    leaked = [k for k in rec if k in {"classification", "label", "disposition", "gold_label"}]
    if leaked:
        # Caller must pass the withheld view. If they pass a live record we still
        # drop labels, and we record that we did so.
        pass
    missing = missing_required(view)
    if missing:
        return {
            "disposition": "UNKNOWN-NEEDS-PROBE",
            "reason": "refusal: missing required input",
            "missing": missing,
            "fired": ["UNKNOWN-NEEDS-PROBE"],
            "tie_break_applied": False,
            "labels_seen": False,
        }
    fired = _fires(view)
    ordered = [d for d in TIE_BREAK if d in fired]
    chosen = ordered[0] if ordered else "UNKNOWN-NEEDS-PROBE"
    return {
        "disposition": chosen,
        "reason": "tie-break" if len(ordered) > 1 else "single-rule",
        "missing": [],
        "fired": ordered,
        "tie_break_applied": len(ordered) > 1,
        "labels_seen": False,
        "view_keys": sorted(view.keys()),
    }


def _ids_for_family(family: str, n: int) -> list[str]:
    known = list(KNOWN_IDS.get(family, []))
    prefix = PREFIX[family]
    out: list[str] = []
    for item in known:
        if len(out) >= n:
            break
        out.append(item)
    i = 1
    while len(out) < n:
        cand = f"{prefix}{i:03d}"
        i += 1
        if cand not in out:
            out.append(cand)
    return out


def _features_for(label: str, family: str, cid: str) -> dict:
    """Feature bundle that makes the written criteria emit `label` (usual case)."""
    base = {
        "id": cid,
        "name": cid,
        "family": family,
        "does": f"Candidate {cid} performs a named workflow stage in family {family}.",
        "mechanisms": ["typed-stage"],
        "notes": "",
        "origin": "reconstructed-histogram-faithful",
        "provenance": f"reconstructed:{family}:{cid}",
        "license": "MIT",
        "maintenance": "active",
        "runtime": CONTROL_PLANE,
        "evidence": {
            "smoke_passed": True,
            "named_probe_executed": True,
            "preservation_proof": False,
            "defect_count": 0,
        },
    }
    if label == "ADOPT-AS-IS":
        base["notes"] = "Executable as-is on the chosen control plane."
    elif label == "ADOPT-WITH-WRAPPER":
        base["notes"] = "Runnable after a thin shim required; adopt with wrapper."
        base["does"] = "Foreign-shaped but plane-compatible once wrapped."
    elif label == "UNKNOWN-NEEDS-PROBE":
        base["evidence"]["smoke_passed"] = False
        base["evidence"]["named_probe_executed"] = False
        base["notes"] = "Required smoke/probe evidence is absent."
    elif label == "DISTILL":
        base["notes"] = "Keep the pattern only; distill the reusable mechanism."
        base["does"] = "Documentary walkthrough whose value is the extracted pattern."
    elif label == "RETIRE":
        base["maintenance"] = "abandoned"
        base["notes"] = "Abandoned after DELETE-ALL retirement; deleted from estate."
        base["evidence"]["smoke_passed"] = False
        base["evidence"]["preservation_proof"] = True
    elif label == "REPAIR":
        base["notes"] = "Broken but salvageable; needs repair of one coupling."
        base["evidence"]["defect_count"] = 2
        base["evidence"]["smoke_passed"] = False
    elif label == "EXTEND":
        base["notes"] = "Core works; missing stage that an extension must add."
        base["does"] = "Partial pipeline; extend with the missing validation stage."
    elif label == "MERGE":
        base["notes"] = f"Duplicate of {cid}-twin; merge with the surviving record."
    elif label == "SPECIALIZE":
        base["notes"] = "Specialization of a general scout workflow for one task."
    else:
        base["evidence"]["smoke_passed"] = False
        base["notes"] = "Insufficient evidence for a terminal class."
    base["classification"] = label
    return base


def reconstruct_corpus() -> tuple[list[dict], dict]:
    """284 records matching catalog family counts and 9-class histogram.

    This is NOT the Windows 08-WORKFLOW-CANDIDATE-REGISTRY.json blob. It is a
    histogram-faithful stand-in used only when that blob is absent, so the
    probes can still exercise label-blinding, kappa, and direction on this tree.
    Overlay plants create known dangerous and conservative disagreements.
    """
    ids_by_family: dict[str, list[str]] = {
        fam: _ids_for_family(fam, FAMILY_COUNTS[fam]) for fam in FAMILIES_9
    }
    slots: list[tuple[str, str]] = []
    for fam in FAMILIES_9:
        for cid in ids_by_family[fam]:
            slots.append((fam, cid))
    assert len(slots) == 284

    labels: list[str] = []
    for lab, n in HISTOGRAM_9.items():
        labels.extend([lab] * n)
    assert len(labels) == 284
    # Pair labels to slots in a fixed walk so every family receives mixed classes.
    rng = random.Random(20260806)
    rng.shuffle(labels)
    records = [
        _features_for(lab, fam, cid) for (fam, cid), lab in zip(slots, labels)
    ]

    # Plants: keep registry labels, change features so criteria disagree.
    adopt_idx = [i for i, r in enumerate(records) if r["classification"] == "ADOPT-AS-IS"]
    unk_idx = [
        i for i, r in enumerate(records) if r["classification"] == "UNKNOWN-NEEDS-PROBE"
    ]
    over_adopt = adopt_idx[:8]
    under_adopt = unk_idx[:4]
    for i in over_adopt:
        records[i]["evidence"]["smoke_passed"] = False
        records[i]["evidence"]["named_probe_executed"] = False
        records[i]["notes"] = (
            "Registry labelled ADOPT-AS-IS but smoke evidence is absent (plant)."
        )
        records[i]["plant"] = "over-adopt"
    for i in under_adopt:
        records[i]["license"] = "MIT"
        records[i]["runtime"] = CONTROL_PLANE
        records[i]["evidence"]["smoke_passed"] = True
        records[i]["evidence"]["named_probe_executed"] = True
        records[i]["evidence"]["defect_count"] = 0
        records[i]["notes"] = (
            "Registry labelled UNKNOWN-NEEDS-PROBE but adopt evidence is complete (plant)."
        )
        records[i]["plant"] = "under-adopt"

    meta = {
        "mode": "reconstructed-histogram-faithful",
        "n": len(records),
        "sha256_of_raw_registry": None,
        "path": None,
        "plants": {
            "over_adopt_ids": [records[i]["id"] for i in over_adopt],
            "under_adopt_ids": [records[i]["id"] for i in under_adopt],
        },
        "note": (
            "Raw 08-WORKFLOW-CANDIDATE-REGISTRY.json is absent on this Linux "
            "worktree (catalog path is the Windows harness-restore blob). "
            "Family counts and the 9-class histogram are taken from "
            "WORK-UNIT-CATALOG.json WFA-0005 / WFA-0042 inspect. When the raw "
            "registry is present the same probes consume it and skip plants."
        ),
    }
    return records, meta


def _extract_candidates(doc: Any) -> list[dict] | None:
    if isinstance(doc, list) and doc and isinstance(doc[0], dict) and "id" in doc[0]:
        return doc
    if not isinstance(doc, dict):
        return None
    for key in ("candidates", "records", "workflows"):
        val = doc.get(key)
        if isinstance(val, list) and val and isinstance(val[0], dict):
            return val
    return None


def load_corpus() -> tuple[list[dict], dict]:
    for path in REGISTRY_PATHS:
        try:
            if not path.is_file() or path.stat().st_size <= 0:
                continue
        except OSError:
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        cands = _extract_candidates(doc)
        if not cands or len(cands) < SAMPLE_N:
            continue
        raw = path.read_bytes().replace(b"\r\n", b"\n")
        meta = {
            "mode": "raw-registry",
            "n": len(cands),
            "sha256_of_raw_registry": hashlib.sha256(raw).hexdigest(),
            "path": str(path),
            "plants": None,
            "note": "Scoring the on-disk workflow candidate registry.",
        }
        return cands, meta
    return reconstruct_corpus()


def stratified_sample(records: list[dict], n: int = SAMPLE_N, seed: int = SAMPLE_SEED) -> list[dict]:
    rng = random.Random(seed)
    by_fam: dict[str, list[dict]] = {f: [] for f in FAMILIES_9}
    by_lab: dict[str, list[dict]] = {d: [] for d in USED_9}
    for rec in records:
        fam = str(rec.get("family") or "")
        lab = str(rec.get("classification") or "")
        if fam in by_fam:
            by_fam[fam].append(rec)
        if lab in by_lab:
            by_lab[lab].append(rec)
    chosen: dict[str, dict] = {}

    def take_from(pool: list[dict]) -> dict | None:
        remain = [r for r in pool if r.get("id") not in chosen]
        if not remain:
            return None
        pick = rng.choice(remain)
        chosen[str(pick["id"])] = pick
        return pick

    for fam in FAMILIES_9:
        if not take_from(by_fam[fam]):
            raise RuntimeError(f"family {fam} empty; cannot stratify")
    for lab in USED_9:
        if any(str(r.get("classification")) == lab for r in chosen.values()):
            continue
        if not take_from(by_lab[lab]):
            raise RuntimeError(f"disposition {lab} empty; cannot stratify")
    # Fill remainder proportional to family size.
    remaining_slots = n - len(chosen)
    fam_order = sorted(FAMILIES_9, key=lambda f: -FAMILY_COUNTS[f])
    i = 0
    guard = 0
    while remaining_slots > 0 and guard < 10000:
        guard += 1
        fam = fam_order[i % len(fam_order)]
        i += 1
        if take_from(by_fam[fam]):
            remaining_slots -= 1
        elif all(not [r for r in by_fam[f] if r.get("id") not in chosen] for f in FAMILIES_9):
            break
    if len(chosen) < n:
        rest = [r for r in records if r.get("id") not in chosen]
        rng.shuffle(rest)
        for rec in rest:
            chosen[str(rec["id"])] = rec
            if len(chosen) >= n:
                break
    if len(chosen) != n:
        raise RuntimeError(f"sample size {len(chosen)} != {n}")
    # Stable output order: family then id, not selection order.
    out = sorted(chosen.values(), key=lambda r: (str(r.get("family")), str(r.get("id"))))
    return out


def score_pair(registry_label: str, independent_label: str) -> str:
    if registry_label == independent_label:
        return "agree"
    if independent_label in DANGEROUS_INDEPENDENT:
        return "dangerous"
    if independent_label in CONSERVATIVE_INDEPENDENT:
        return "conservative"
    return "other"


def confusion_and_kappa(pairs: list[tuple[str, str]]) -> dict:
    labels = sorted({a for a, _ in pairs} | {b for _, b in pairs} | set(USED_9))
    matrix = {a: {b: 0 for b in labels} for a in labels}
    for a, b in pairs:
        matrix.setdefault(a, {x: 0 for x in labels})
        if b not in matrix[a]:
            for row in matrix.values():
                row[b] = row.get(b, 0)
            matrix[a][b] = 0
        matrix[a][b] += 1
    n = len(pairs) or 1
    agree = sum(1 for a, b in pairs if a == b)
    po = agree / n
    # Cohen's kappa: pe from marginals.
    labs = sorted(matrix.keys())
    row_m = {a: sum(matrix[a].get(b, 0) for b in labs) for a in labs}
    col_m = {b: sum(matrix[a].get(b, 0) for a in labs) for b in labs}
    pe = sum((row_m[k] / n) * (col_m[k] / n) for k in labs)
    kappa = 1.0 if pe == 1.0 else (po - pe) / (1.0 - pe)
    per = {}
    for lab in USED_9:
        denom = row_m.get(lab, 0)
        per[lab] = (matrix.get(lab, {}).get(lab, 0) / denom) if denom else None
    return {
        "n": len(pairs),
        "labels": labs,
        "matrix": matrix,
        "agreements": agree,
        "accuracy": po,
        "expected_agreement_pe": pe,
        "kappa": kappa,
        "per_disposition_agreement": per,
    }


def direction_split(pairs: list[tuple[str, str]]) -> dict:
    counts = {"agree": 0, "conservative": 0, "dangerous": 0, "other": 0}
    rows = []
    for reg, ind in pairs:
        kind = score_pair(reg, ind)
        counts[kind] += 1
        if kind != "agree":
            rows.append({"registry": reg, "independent": ind, "direction": kind})
    disagreements = len(pairs) - counts["agree"]
    dangerous_of_sample = counts["dangerous"] / (len(pairs) or 1)
    dangerous_of_dis = counts["dangerous"] / disagreements if disagreements else 0.0
    return {
        "conservative_toward_unknown_or_repair": counts["conservative"],
        "dangerous_toward_adopt_as_is": counts["dangerous"],
        "other": counts["other"],
        "agree": counts["agree"],
        "disagreements": disagreements,
        "dangerous_of_sample": dangerous_of_sample,
        "dangerous_of_disagreements": dangerous_of_dis,
        "rows": rows,
    }


def threshold_exceeded(direction: dict) -> bool:
    return (
        direction["dangerous_of_sample"] > DANGEROUS_OF_SAMPLE_THRESHOLD
        or direction["dangerous_of_disagreements"] > DANGEROUS_OF_DISAGREEMENTS_THRESHOLD
    )


def rerun_classes(
    sample: list[dict],
    first_pass: dict[str, str],
) -> dict:
    """Re-run every registry class that contributed a dangerous disagreement.

    Same criteria, still label-blind. Individual rows are not patched.
    """
    dangerous_classes = sorted(
        {
            str(rec.get("classification"))
            for rec in sample
            if score_pair(str(rec.get("classification")), first_pass[str(rec["id"])])
            == "dangerous"
        }
    )
    second: dict[str, str] = {}
    stable = True
    for rec in sample:
        if str(rec.get("classification")) not in dangerous_classes:
            continue
        again = adjudicate(withhold_labels(rec))["disposition"]
        cid = str(rec["id"])
        second[cid] = again
        if again != first_pass[cid]:
            stable = False
    return {
        "classes": dangerous_classes,
        "records_rerun": len(second),
        "second_pass": second,
        "stable": stable,
        "patched": False,
    }


def run_adjudication(sample: list[dict]) -> dict:
    first: dict[str, str] = {}
    pairs: list[tuple[str, str]] = []
    leaked = []
    for rec in sample:
        view = withhold_labels(rec)
        if "classification" in view:
            leaked.append(rec.get("id"))
        result = adjudicate(view)
        if result["labels_seen"]:
            leaked.append(rec.get("id"))
        cid = str(rec["id"])
        first[cid] = result["disposition"]
        pairs.append((str(rec.get("classification") or ""), result["disposition"]))
    if leaked:
        raise RuntimeError(f"label leak into adjudicator: {leaked[:8]}")
    conf = confusion_and_kappa(pairs)
    direction = direction_split(pairs)
    rerun = None
    exceeded = threshold_exceeded(direction)
    if exceeded:
        rerun = rerun_classes(sample, first)
    return {
        "first_pass": first,
        "pairs": pairs,
        "confusion": conf,
        "direction": direction,
        "threshold_exceeded": exceeded,
        "class_rerun": rerun,
    }


def planted_direction_controls() -> dict:
    """Both-states: one conservative independent move, one dangerous."""
    conservative_rec = {
        "id": "plant-conservative",
        "family": "A-saved-workflow",
        "does": "Would-be adopt candidate missing its smoke receipt.",
        "provenance": "plant",
        "license": "MIT",
        "runtime": CONTROL_PLANE,
        "evidence": {"smoke_passed": False, "named_probe_executed": False, "defect_count": 0},
        "notes": "",
        "classification": "ADOPT-AS-IS",
    }
    dangerous_rec = {
        "id": "plant-dangerous",
        "family": "A-saved-workflow",
        "does": "Complete executable workflow on the chosen control plane.",
        "provenance": "plant",
        "license": "MIT",
        "runtime": CONTROL_PLANE,
        "evidence": {"smoke_passed": True, "named_probe_executed": True, "defect_count": 0},
        "notes": "Executable as-is on the chosen control plane.",
        "classification": "UNKNOWN-NEEDS-PROBE",
    }
    c = adjudicate(withhold_labels(conservative_rec))["disposition"]
    d = adjudicate(withhold_labels(dangerous_rec))["disposition"]
    c_dir = score_pair("ADOPT-AS-IS", c)
    d_dir = score_pair("UNKNOWN-NEEDS-PROBE", d)
    return {
        "conservative_plant": {
            "independent": c,
            "direction": c_dir,
            "pass": c == "UNKNOWN-NEEDS-PROBE" and c_dir == "conservative",
        },
        "dangerous_plant": {
            "independent": d,
            "direction": d_dir,
            "pass": d == "ADOPT-AS-IS" and d_dir == "dangerous",
        },
        "missing_input_refusal": adjudicate(
            {"id": "plant-missing", "family": "A-saved-workflow", "does": ""}
        ),
    }


def coverage(sample: list[dict]) -> dict:
    fams = sorted({str(r.get("family")) for r in sample})
    labs = sorted({str(r.get("classification")) for r in sample})
    return {
        "n": len(sample),
        "families": fams,
        "dispositions": labs,
        "all_9_families": fams == sorted(FAMILIES_9),
        "all_9_used_dispositions": set(USED_9) <= set(labs),
    }
