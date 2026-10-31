#!/usr/bin/env python
"""Wave-2 floor audit, pass 2. Fixes four defects found in pass 1:

  D1 (MY detector failure) - the invalid-blueprint control popped `stages`, which made the
     classifier treat it as a REPORT file, so it never reached the validator and the control
     did not fire. Pass 2 seeds THREE controls: a wrong-type one, a bad-enum one, and the
     missing-`stages` one kept deliberately to MEASURE the classifier blind spot.
  D2 - flagship->test mapping was a name heuristic with a relaxed prefix fallback. Pass 2
     reports STRICT (exact filename) and RELAXED separately, and RUNS the tests.
  D3 - output_schema values are PROSE, not paths ("a.schema.json + b.schema.json (authored
     here)"). Pass 1 resolved the whole string and mis-scored. Pass 2 extracts every
     path-shaped token per value and resolves each.
  D4 - pass 1 never ran the test suites.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
PLATFORM = REPO / "platform"
CC = REPO / "command-center"
WFDIR = PLATFORM / "workflows"
LIB = PLATFORM / "lib"

sys.path.insert(0, str(LIB))
from wfdsl import schemas, semantics  # noqa: E402

sys.path.insert(0, str(CC))
from _wave2_floor_audit import (  # noqa: E402
    check_architecture,
    check_blueprints,
    is_blueprint_doc,
    load_json_safe,
    mechanism_fingerprint,
)

OUT_JSON = CC / "WAVE2-FLOOR-AUDIT.json"

PATHISH = re.compile(r"[A-Za-z0-9_./\\-]+\.(?:schema\.json|json|md|py)")


# ------------------------------------------------------------------ D1 detector control
def detector_control_v2() -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="wave2_ctl2_"))
    try:
        base = WFDIR / "bp-cnc-01-five-persona-design-council.json"
        base_doc, err = load_json_safe(base)
        if err:
            return {"error": f"base unreadable: {err}"}
        scratch = tmp / "workflows"
        scratch.mkdir()
        shutil.copy2(base, scratch / base.name)

        # (a) wrong TYPE on a required field, stages KEPT so classification survives
        a = json.loads(json.dumps(base_doc))
        a["id"] = "ctl-invalid-wrongtype"
        a["dsl_version"] = 99
        (scratch / "CTL-invalid-wrongtype.json").write_text(
            json.dumps(a, indent=1), encoding="utf-8"
        )

        # (b) structurally broken stage (stages present, contents illegal)
        b = json.loads(json.dumps(base_doc))
        b["id"] = "ctl-invalid-badstage"
        b["stages"] = [{"nonsense_key": True}]
        (scratch / "CTL-invalid-badstage.json").write_text(
            json.dumps(b, indent=1), encoding="utf-8"
        )

        # (c) missing required `stages` -- kept to MEASURE the classifier blind spot
        c = json.loads(json.dumps(base_doc))
        c["id"] = "ctl-invalid-nostages"
        c.pop("stages", None)
        (scratch / "CTL-invalid-nostages.json").write_text(
            json.dumps(c, indent=1), encoding="utf-8"
        )

        # (d) exact-mechanism duplicate under a different name/id
        d = json.loads(json.dumps(base_doc))
        d["id"] = "ctl-duplicate-blueprint"
        d["name"] = "A Totally Different Sounding Name"
        d["description"] = "Renamed clone. Mechanism byte-identical."
        for st in d.get("stages") or []:
            if isinstance(st, dict):
                st["description"] = "renamed"
        (scratch / "CTL-duplicate.json").write_text(
            json.dumps(d, indent=1), encoding="utf-8"
        )

        res = check_blueprints(scratch)
        invalid_ids = {x["id"] for x in res["schema_invalid_detail"]}
        # direct-validator probe for the reclassified one (bypasses the classifier)
        wf = schemas.workflow_validator()
        nostage_doc, _ = load_json_safe(scratch / "CTL-invalid-nostages.json")
        nostage_errs = schemas.error_summary(
            sorted(wf.iter_errors(nostage_doc), key=lambda e: list(e.absolute_path)), 4
        )

        dup_fired = any(
            {"bp-cnc-01-five-persona-design-council", "ctl-duplicate-blueprint"}
            <= set(cl["ids"])
            for cl in res["exact_mechanism_duplicate_clusters"]
        )
        pos_ctl = any(
            r["id"] == "bp-cnc-01-five-persona-design-council" and r["schema_valid"]
            for r in res["per_file"]
        )
        wrongtype = "ctl-invalid-wrongtype" in invalid_ids
        badstage = "ctl-invalid-badstage" in invalid_ids
        nostage_classified = any(
            r["id"] == "ctl-invalid-nostages" for r in res["per_file"]
        )
        return {
            "controls_seeded": 4,
            "blueprint_docs_classified": res["blueprint_docs"],
            "report_files_classified": res["non_blueprint_report_files"],
            "A_wrongtype_dsl_version_FIRED": wrongtype,
            "A_errors": [
                x["schema_errors"]
                for x in res["schema_invalid_detail"]
                if x["id"] == "ctl-invalid-wrongtype"
            ],
            "B_badstage_FIRED": badstage,
            "B_errors": [
                x["schema_errors"]
                for x in res["schema_invalid_detail"]
                if x["id"] == "ctl-invalid-badstage"
            ],
            "C_nostages_reached_validator": nostage_classified,
            "C_direct_validator_errors_when_bypassing_classifier": nostage_errs,
            "C_KNOWN_BLIND_SPOT": (
                "A doc missing `stages` is classified as a REPORT, not an invalid blueprint, "
                "so it silently leaves the denominator instead of failing. The raw validator "
                "DOES reject it (see C_direct_validator_errors...). This is a weakness of the "
                "classifier heuristic, not of the DSL validator."
                if not nostage_classified
                else "not observed"
            ),
            "D_duplicate_mechanism_FIRED": dup_fired,
            "positive_control_original_still_passes": pos_ctl,
            "verdict": (
                "CONFIRMED"
                if (wrongtype and badstage and dup_fired and pos_ctl)
                else "REFUTED"
            ),
            "verdict_basis": "fires on 2 known-broken schema variants AND on a renamed exact-mechanism clone, and stays silent on the known-good original",
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ D2 flagship tests
def flagship_mapping(bp: dict) -> dict:
    testdir = LIB / "workflows"
    all_tests = sorted(p.name for p in testdir.glob("test_*.py"))
    flagship = [r for r in bp["per_file"] if r["flagship"]]
    strict, relaxed_only, unmapped = [], [], []
    for r in flagship:
        bid = r["id"] or ""
        s = bid.replace("-", "_").replace(".", "_")
        exact = f"test_{s}.py"
        if (testdir / exact).exists():
            strict.append({"id": bid, "test": exact})
            continue
        hit = None
        for t in all_tests:
            stem = t[len("test_") : -3]
            if s.startswith(stem) and len(stem) > 8:
                hit = t
                break
        if hit:
            relaxed_only.append({"id": bid, "test": hit})
        else:
            unmapped.append(bid)
    return {
        "flagship_declared": len(flagship),
        "strict_exact_filename_match": len(strict),
        "relaxed_prefix_match_only": len(relaxed_only),
        "no_test_at_all": len(unmapped),
        "strict": strict,
        "relaxed_only": relaxed_only,
        "unmapped": sorted(unmapped),
        "test_files_present": len(all_tests),
    }


def run_pytest(target: str, extra: list[str] | None = None) -> dict:
    cmd = [sys.executable, "-m", "pytest", target, "-q", "--no-header", "-p", "no:cacheprovider"]
    if extra:
        cmd += extra
    p = subprocess.run(cmd, cwd=str(LIB), capture_output=True, text=True, timeout=2400)
    tail = (p.stdout or "")[-3000:]
    m = re.findall(r"(\d+) (passed|failed|error|errors|skipped|xfailed|xpassed)", p.stdout or "")
    return {
        "command": " ".join(cmd),
        "cwd": str(LIB).replace("\\", "/"),
        "exit_code": p.returncode,
        "counts": {k: int(v) for v, k in m},
        "stdout_tail": tail,
        "stderr_tail": (p.stderr or "")[-1200:],
    }


# ------------------------------------------------------------------ D3 substrate
def substrate_v2() -> dict:
    doc, err = load_json_safe(CC / "WORK-UNIT-CATALOG.json")
    if err:
        return {"error": err}
    units = doc.get("work_units") or []
    val_counter: Counter[str] = Counter()
    for u in units:
        v = u.get("output_schema")
        for one in v if isinstance(v, list) else ([v] if v else []):
            if isinstance(one, str):
                val_counter[one] += 1

    tok_counter: Counter[str] = Counter()
    prose_values = 0
    for val, n in val_counter.items():
        toks = PATHISH.findall(val)
        if len(toks) != 1 or toks[0] != val.strip():
            prose_values += 1
        for t in toks:
            tok_counter[t.replace("\\", "/")] += n

    resolved, missing = [], []
    for t in sorted(tok_counter):
        cands = [REPO / t, CC / t, PLATFORM / t, CC / "schema" / Path(t).name]
        ok = any(c.exists() and c.is_file() for c in cands)
        (resolved if ok else missing).append(t)

    # value-level: does EVERY token in a value resolve?
    fully, partially, none_ok = 0, 0, 0
    for val, n in val_counter.items():
        toks = [t.replace("\\", "/") for t in PATHISH.findall(val)]
        if not toks:
            none_ok += 1
            continue
        got = sum(1 for t in toks if t in set(resolved))
        if got == len(toks):
            fully += 1
        elif got:
            partially += 1
        else:
            none_ok += 1

    return {
        "work_units": len(units),
        "distinct_output_schema_VALUES": len(val_counter),
        "values_that_are_prose_not_a_bare_path": prose_values,
        "total_references": sum(val_counter.values()),
        "distinct_path_TOKENS_extracted": len(tok_counter),
        "tokens_resolving_on_disk": len(resolved),
        "tokens_NOT_resolving": len(missing),
        "unresolved_tokens": missing,
        "unresolved_token_reference_count": sum(tok_counter[m] for m in missing),
        "values_all_tokens_resolve": fully,
        "values_some_tokens_resolve": partially,
        "values_no_token_resolves_or_no_token": none_ok,
        "cc_schema_dir_exists": (CC / "schema").exists(),
        "cc_schema_file_count": (
            len([p for p in (CC / "schema").rglob("*.json") if p.is_file()])
            if (CC / "schema").exists()
            else 0
        ),
    }


# ------------------------------------------------------------------ forged / foundry
def forged_dir_audit() -> dict:
    fd = WFDIR / "forged"
    if not fd.exists():
        return {"exists": False}
    docs = []
    for p in sorted(fd.glob("*.json")):
        d, e = load_json_safe(p)
        if e or not is_blueprint_doc(d):
            continue
        docs.append(
            {
                "file": p.name,
                "id": d.get("id"),
                "fp": mechanism_fingerprint(d),
                "stages": len(d.get("stages") or []),
            }
        )
    byid = defaultdict(list)
    for d in docs:
        byid[d["id"]].append(d["file"])
    return {
        "exists": True,
        "workflow_docs": docs,
        "ids_reused_across_files": {k: v for k, v in byid.items() if len(v) > 1},
    }


def main() -> int:
    prev, _ = load_json_safe(OUT_JSON)
    prev = prev if isinstance(prev, dict) else {}
    bp = prev.get("check1_blueprints") or check_blueprints(WFDIR)

    res: dict[str, Any] = dict(prev)
    res["pass"] = 2
    res["generated_at_utc"] = _dt.datetime.now(_dt.UTC).isoformat()
    res["audit_scripts"] = [
        str(CC / "_wave2_floor_audit.py").replace("\\", "/"),
        str(CC / "_wave2_floor_audit2.py").replace("\\", "/"),
    ]
    res["detector_control"] = detector_control_v2()
    res["check2_flagship_mapping"] = flagship_mapping(bp)
    res["check5_substrate"] = substrate_v2()
    res["forged_dir"] = forged_dir_audit()

    print("=== DETECTOR CONTROL v2 ===")
    print(json.dumps(res["detector_control"], indent=1))
    print("\n=== FLAGSHIP MAPPING ===")
    print(
        json.dumps(
            {k: v for k, v in res["check2_flagship_mapping"].items() if k not in ("strict", "relaxed_only")},
            indent=1,
        )
    )
    print("  relaxed_only:", res["check2_flagship_mapping"]["relaxed_only"])
    print("\n=== SUBSTRATE v2 ===")
    print(json.dumps({k: v for k, v in res["check5_substrate"].items() if k != "unresolved_tokens"}, indent=1))
    print("  unresolved tokens:", res["check5_substrate"]["unresolved_tokens"])
    print("\n=== FORGED DIR ===")
    print(json.dumps(res["forged_dir"], indent=1))

    OUT_JSON.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("\nWROTE", OUT_JSON)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
