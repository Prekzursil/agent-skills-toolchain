#!/usr/bin/env python
"""MECHANICAL audit of Wave 2 deliverables. Trusts no self-reported count.

Run:  python C:/Users/Prekzursil/source/ast-integrate/command-center/_wave2_floor_audit.py
"""

from __future__ import annotations

import hashlib
import json
import os
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

OUT_JSON = CC / "WAVE2-FLOOR-AUDIT.json"
OUT_MD = CC / "WAVE2-FLOOR-AUDIT.md"

# Files in workflows/ that are STATUS/VALIDATION reports, not blueprints.
# Detected structurally: a blueprint has dsl_version + id + name + version + stages.
REPORT_MARKER_KEYS = {"dsl_version", "stages"}


def is_blueprint_doc(doc: Any) -> bool:
    return isinstance(doc, dict) and REPORT_MARKER_KEYS.issubset(doc.keys())


def load_json_safe(p: Path) -> tuple[Any, str | None]:
    try:
        return json.loads(p.read_text(encoding="utf-8")), None
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------- mechanism norm
def norm_stages(doc: dict) -> list[tuple]:
    """Normalise a workflow's stage mechanism, name-independent."""
    out = []
    for st in doc.get("stages") or []:
        if not isinstance(st, dict):
            continue
        # mechanism-bearing fields only: NOT the stage id/name/description
        agents = st.get("agents") or st.get("agent") or []
        if isinstance(agents, dict):
            agents = [agents]
        roles = sorted(
            {
                (a.get("role") or a.get("role_ref") or "")
                for a in agents
                if isinstance(a, dict)
            }
        )
        out.append(
            (
                st.get("type") or st.get("kind") or "",
                st.get("mode") or ("parallel" if st.get("parallel") else ""),
                tuple(roles),
                len(agents) if isinstance(agents, list) else 0,
                bool(st.get("gate") or st.get("gate_ref")),
                str(st.get("barrier") or ""),
                str(st.get("subworkflow") or st.get("subworkflow_ref") or ""),
            )
        )
    return out


def norm_roles(doc: dict) -> tuple:
    r = doc.get("roles") or {}
    if isinstance(r, dict):
        items = []
        for k, v in r.items():
            if isinstance(v, dict):
                items.append(
                    (
                        v.get("kind") or v.get("type") or "",
                        v.get("vendor") or "",
                        v.get("model") or "",
                        bool(v.get("adversarial")),
                    )
                )
            else:
                items.append((str(v), "", "", False))
        return tuple(sorted(items))
    return ()


def norm_gates(doc: dict) -> tuple:
    g = doc.get("gates") or {}
    if isinstance(g, dict):
        items = []
        for k, v in g.items():
            if isinstance(v, dict):
                items.append(
                    (
                        v.get("kind") or v.get("type") or "",
                        str(v.get("predicate") or v.get("expr") or ""),
                        str(v.get("on_fail") or ""),
                        bool(v.get("blocking")),
                    )
                )
            else:
                items.append((str(v), "", "", False))
        return tuple(sorted(items))
    return ()


def norm_stopping(doc: dict) -> tuple:
    sr = doc.get("stopping_rules") or []
    items = []
    for s in sr:
        if isinstance(s, dict):
            items.append(str(s.get("expr") or s.get("predicate") or s.get("when") or ""))
        else:
            items.append(str(s))
    return tuple(sorted(items))


def mechanism_fingerprint(doc: dict) -> str:
    payload = json.dumps(
        {
            "stages": norm_stages(doc),
            "roles": norm_roles(doc),
            "gates": norm_gates(doc),
            "stopping": norm_stopping(doc),
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def mechanism_parts(doc: dict) -> dict:
    return {
        "stages": json.dumps(norm_stages(doc), sort_keys=True, default=str),
        "roles": json.dumps(norm_roles(doc), sort_keys=True, default=str),
        "gates": json.dumps(norm_gates(doc), sort_keys=True, default=str),
        "stopping": json.dumps(norm_stopping(doc), sort_keys=True, default=str),
    }


# ---------------------------------------------------------------- check 1
def check_blueprints(root: Path) -> dict:
    files = sorted(p for p in root.rglob("*.json") if p.is_file())
    blueprints, reports, unparseable = [], [], []
    for p in files:
        doc, err = load_json_safe(p)
        if err:
            unparseable.append({"file": str(p), "error": err})
            continue
        if is_blueprint_doc(doc):
            blueprints.append((p, doc))
        else:
            reports.append(str(p.relative_to(root)))

    wf_validator = schemas.workflow_validator()
    per_file = []
    for p, doc in blueprints:
        errs = sorted(wf_validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
        sem = semantics.check_workflow(doc)
        sv = sum(len(r.violations) for r in sem if r.severity == "violation")
        sa = sum(len(r.violations) for r in sem if r.severity == "advisory")
        per_file.append(
            {
                "file": str(p.relative_to(root)).replace("\\", "/"),
                "id": doc.get("id"),
                "flagship": bool(doc.get("flagship")),
                "schema_valid": not errs,
                "schema_errors": schemas.error_summary(errs, limit=4),
                "semantic_violations": sv,
                "semantic_advisories": sa,
                "mechanism_fp": mechanism_fingerprint(doc),
                "n_stages": len(doc.get("stages") or []),
            }
        )

    # ---- distinctness clustering by mechanism fingerprint
    byfp = defaultdict(list)
    for r in per_file:
        byfp[r["mechanism_fp"]].append(r["id"] or r["file"])
    exact_clusters = [
        {"fingerprint": fp, "size": len(ids), "ids": sorted(ids)}
        for fp, ids in byfp.items()
        if len(ids) > 1
    ]
    exact_clusters.sort(key=lambda c: -c["size"])

    # ---- partial-mechanism near-duplicates: identical stage-shape only
    bystage = defaultdict(list)
    for p, doc in blueprints:
        bystage[mechanism_parts(doc)["stages"]].append(doc.get("id") or p.name)
    stage_clusters = [
        {"size": len(v), "ids": sorted(v)} for v in bystage.values() if len(v) > 1
    ]
    stage_clusters.sort(key=lambda c: -c["size"])

    # ---- duplicate ids
    idc = Counter(r["id"] for r in per_file)
    dup_ids = {k: v for k, v in idc.items() if v > 1}

    return {
        "root": str(root).replace("\\", "/"),
        "json_files_total": len(files),
        "blueprint_docs": len(blueprints),
        "non_blueprint_report_files": len(reports),
        "non_blueprint_report_names": reports,
        "unparseable": unparseable,
        "schema_valid": sum(1 for r in per_file if r["schema_valid"]),
        "schema_invalid": sum(1 for r in per_file if not r["schema_valid"]),
        "schema_invalid_detail": [r for r in per_file if not r["schema_valid"]],
        "semantic_violation_files": sum(
            1 for r in per_file if r["semantic_violations"] > 0
        ),
        "semantic_violation_detail": [
            {"id": r["id"], "file": r["file"], "n": r["semantic_violations"]}
            for r in per_file
            if r["semantic_violations"] > 0
        ],
        "distinct_mechanism_fingerprints": len(byfp),
        "exact_mechanism_duplicate_clusters": exact_clusters,
        "stage_shape_duplicate_clusters": stage_clusters[:25],
        "stage_shape_cluster_count": len(stage_clusters),
        "duplicate_ids": dup_ids,
        "flagship_count": sum(1 for r in per_file if r["flagship"]),
        "flagship_ids": sorted(r["id"] for r in per_file if r["flagship"]),
        "per_file": per_file,
    }


# ---------------------------------------------------------------- detector control
def detector_control() -> dict:
    """Seed one INVALID and one EXACT-DUPLICATE blueprint into a scratch copy.
    A validator that does not FIRE on both measures nothing."""
    tmp = Path(tempfile.mkdtemp(prefix="wave2_ctl_"))
    try:
        # take a real, valid blueprint as the base
        base = WFDIR / "bp-cnc-01-five-persona-design-council.json"
        base_doc, err = load_json_safe(base)
        if err:
            return {"error": f"base blueprint unreadable: {err}"}

        scratch = tmp / "workflows"
        scratch.mkdir()
        shutil.copy2(base, scratch / base.name)

        # (a) KNOWN-BROKEN: drop a required field + inject a bad enum
        bad = json.loads(json.dumps(base_doc))
        bad["id"] = "ctl-invalid-blueprint"
        bad.pop("stages", None)  # 'stages' is REQUIRED
        bad["dsl_version"] = 99  # wrong type
        (scratch / "CTL-invalid.json").write_text(
            json.dumps(bad, indent=1), encoding="utf-8"
        )

        # (b) KNOWN-DUPLICATE: same mechanism, different name/id/description
        dup = json.loads(json.dumps(base_doc))
        dup["id"] = "ctl-duplicate-blueprint"
        dup["name"] = "A Totally Different Sounding Name"
        dup["description"] = (
            "Renamed clone used as a detector control. Mechanism byte-identical."
        )
        for st in dup.get("stages") or []:
            if isinstance(st, dict):
                st["description"] = "renamed"
        (scratch / "CTL-duplicate.json").write_text(
            json.dumps(dup, indent=1), encoding="utf-8"
        )

        res = check_blueprints(scratch)

        invalid_fired = any(
            d["id"] == "ctl-invalid-blueprint" for d in res["schema_invalid_detail"]
        )
        dup_fired = any(
            {"bp-cnc-01-five-persona-design-council", "ctl-duplicate-blueprint"}
            <= set(c["ids"])
            for c in res["exact_mechanism_duplicate_clusters"]
        )
        # positive control: the untouched original must still PASS + not be flagged alone
        known_present_passes = any(
            r["id"] == "bp-cnc-01-five-persona-design-council" and r["schema_valid"]
            for r in res["per_file"]
        )
        return {
            "scratch_dir": str(scratch).replace("\\", "/"),
            "docs_seen": res["blueprint_docs"],
            "schema_invalid_seen": res["schema_invalid"],
            "invalid_control_FIRED": invalid_fired,
            "invalid_control_errors": [
                d["schema_errors"]
                for d in res["schema_invalid_detail"]
                if d["id"] == "ctl-invalid-blueprint"
            ],
            "duplicate_control_FIRED": dup_fired,
            "duplicate_clusters_seen": res["exact_mechanism_duplicate_clusters"],
            "known_present_still_passes": known_present_passes,
            "verdict": (
                "CONFIRMED"
                if (invalid_fired and dup_fired and known_present_passes)
                else "REFUTED"
            ),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- check 2 flagship
def check_flagship_tests(bp: dict) -> dict:
    testdir = LIB / "workflows"
    tests = sorted(
        p.name for p in testdir.glob("test_*.py") if not p.name.startswith("test_bp1_")
    )
    all_tests = sorted(p.name for p in testdir.glob("test_*.py"))

    # map blueprint id -> plausible dedicated test file
    def cand(bid: str) -> list[str]:
        s = bid.replace("-", "_").replace(".", "_")
        return [f"test_{s}.py", f"test_{s.replace('_workflow','')}.py"]

    flagship = [r for r in bp["per_file"] if r["flagship"]]
    mapped, unmapped = [], []
    for r in flagship:
        bid = r["id"] or ""
        hit = None
        for c in cand(bid):
            if (testdir / c).exists():
                hit = c
                break
        if hit is None:
            # relaxed: any test file whose stem is a prefix of the normalised id
            s = bid.replace("-", "_").replace(".", "_")
            for t in all_tests:
                stem = t[len("test_") : -3]
                if s.startswith(stem) and len(stem) > 8:
                    hit = t
                    break
        if hit:
            mapped.append({"id": bid, "test": hit})
        else:
            unmapped.append(bid)
    return {
        "flagship_declared": len(flagship),
        "flagship_with_dedicated_test": len(mapped),
        "flagship_without_dedicated_test": len(unmapped),
        "unmapped_flagship_ids": sorted(unmapped),
        "mapped": mapped,
        "test_files_in_lib_workflows": len(all_tests),
    }


# ---------------------------------------------------------------- check 3 arch
def check_architecture() -> dict:
    ad = PLATFORM / "architecture"
    if not ad.exists():
        return {"exists": False}
    mds = sorted(p.name for p in ad.glob("*.md"))
    arch = [m for m in mds if m != "TOURNAMENT-VERDICT.md"]
    tv = ad / "TOURNAMENT-VERDICT.md"
    txt = tv.read_text(encoding="utf-8", errors="replace") if tv.exists() else ""
    low = txt.lower()
    minority_terms = {
        "minority report": low.count("minority report"),
        "minority": low.count("minority"),
        "dissent": low.count("dissent"),
        "dissenting": low.count("dissenting"),
        "objection": low.count("objection"),
    }
    # which architecture names does the verdict actually name?
    named = {a[:-3]: low.count(a[:-3].lower()) for a in arch}
    return {
        "exists": True,
        "architecture_md_count": len(arch),
        "architecture_files": arch,
        "tournament_verdict_present": tv.exists(),
        "tournament_verdict_bytes": len(txt.encode()),
        "minority_signal_counts": minority_terms,
        "architectures_named_in_verdict": named,
        "architectures_missing_from_verdict": [k for k, v in named.items() if v == 0],
    }


# ---------------------------------------------------------------- check 5 substrate
def check_substrate() -> dict:
    cat = CC / "WORK-UNIT-CATALOG.json"
    doc, err = load_json_safe(cat)
    if err:
        return {"error": err}
    units = doc.get("work_units") or []
    refs = Counter()
    for u in units:
        v = u.get("output_schema")
        for one in v if isinstance(v, list) else ([v] if v else []):
            if isinstance(one, str):
                refs[one] += 1
    distinct = sorted(refs)
    resolved, missing = [], []
    for r in distinct:
        # strip fragment/anchor + query
        raw = r.split("#")[0].split("?")[0].strip()
        cands = [REPO / raw, CC / raw, PLATFORM / raw]
        if raw.startswith(("command-center/", "platform/")):
            cands.insert(0, REPO / raw)
        ok = any(c.exists() and c.is_file() for c in cands)
        (resolved if ok else missing).append(r)
    return {
        "work_units": len(units),
        "distinct_output_schema_paths": len(distinct),
        "total_references": sum(refs.values()),
        "resolving_now": len(resolved),
        "not_resolving": len(missing),
        "unresolved_refs_sample": missing[:40],
        "unresolved_reference_count": sum(refs[m] for m in missing),
        "resolved_reference_count": sum(refs[r] for r in resolved),
    }


# ---------------------------------------------------------------- main
def main() -> int:
    result: dict[str, Any] = {
        "unit": "verify/wave2-floors",
        "generated_at_utc": subprocess.run(
            [sys.executable, "-c", "import datetime;print(datetime.datetime.now(datetime.UTC).isoformat())"],
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "audit_script": str(Path(__file__)).replace("\\", "/"),
        "method": "mechanical; every count read off disk by this script",
    }

    bp = check_blueprints(WFDIR)
    result["check1_blueprints"] = bp
    result["detector_control"] = detector_control()
    result["check2_flagship"] = check_flagship_tests(bp)
    result["check3_architecture"] = check_architecture()
    result["check5_substrate"] = check_substrate()

    OUT_JSON.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "check1_blueprints"}, indent=1)[:200])
    print("WROTE", OUT_JSON)

    # concise console summary
    print("\n=== CHECK 1 BLUEPRINTS ===")
    for k in (
        "json_files_total",
        "blueprint_docs",
        "non_blueprint_report_files",
        "schema_valid",
        "schema_invalid",
        "semantic_violation_files",
        "distinct_mechanism_fingerprints",
        "stage_shape_cluster_count",
        "flagship_count",
    ):
        print(f"  {k}: {bp[k]}")
    print("  exact_mechanism_dup_clusters:", len(bp["exact_mechanism_duplicate_clusters"]))
    for c in bp["exact_mechanism_duplicate_clusters"][:10]:
        print("    ", c["size"], c["ids"])
    print("  duplicate_ids:", bp["duplicate_ids"])
    if bp["schema_invalid_detail"]:
        print("  INVALID FILES:")
        for d in bp["schema_invalid_detail"]:
            print("    ", d["file"], d["schema_errors"])

    print("\n=== DETECTOR CONTROL ===")
    print(json.dumps(result["detector_control"], indent=1)[:2000])

    print("\n=== CHECK 2 FLAGSHIP ===")
    print(json.dumps({k: v for k, v in result["check2_flagship"].items() if k != "mapped"}, indent=1))

    print("\n=== CHECK 3 ARCHITECTURE ===")
    print(json.dumps(result["check3_architecture"], indent=1))

    print("\n=== CHECK 5 SUBSTRATE ===")
    print(json.dumps({k: v for k, v in result["check5_substrate"].items() if k != "unresolved_refs_sample"}, indent=1))
    print("  unresolved sample:", result["check5_substrate"].get("unresolved_refs_sample", [])[:10])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
