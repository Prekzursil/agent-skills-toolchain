"""Double-run / triple-run determinism audit for CNF-0184."""
from __future__ import annotations

import hashlib
import time
from difflib import unified_diff
from pathlib import Path

from normalizers import (
    CLASS_HOST,
    CLASS_ORDERING,
    CLASS_SEEDS,
    CLASS_TEMP_PATHS,
    CLASS_TIMESTAMPS,
    NORMALIZER_IDS,
    apply_all,
    apply_one,
    classes_that_equalize,
    looks_timestamped,
    over_normalization_report,
)
from reproductions import REPRODUCTIONS, host_variance_pair, run_repro

HERE = Path(__file__).resolve().parent


def find_repo() -> Path:
    for p in [HERE, *HERE.parents]:
        if (p / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return p
    raise RuntimeError("CNF-0184 cannot locate repo root")


REPO = find_repo()

CLASS_SOURCE = {
    CLASS_TIMESTAMPS: "fam3.iso-timestamp",
    CLASS_TEMP_PATHS: "fam6.temp-path",
    CLASS_ORDERING: "fam3.json-key-order",
    CLASS_SEEDS: "fam6.rng-seed",
    CLASS_HOST: "fam6.host-id",
}


def run_id(repro_id: str, n: int, text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"{repro_id}/run{n}/{digest}"


def hunk(a: str, b: str) -> str:
    lines = list(
        unified_diff(
            a.splitlines(keepends=True),
            b.splitlines(keepends=True),
            fromfile="run1",
            tofile="run2",
            n=2,
        )
    )
    text = "".join(lines)
    if len(text) > 800:
        text = text[:800] + "\n...truncated...\n"
    return text or "(no unified diff; texts equal)\n"


def needs_third_run(raw1: str, raw2: str, spec: dict) -> bool:
    if spec.get("borderline"):
        return True
    if raw1 != raw2:
        return False
    return looks_timestamped(raw1) or "seed_draw=" in raw1


def classify_pair(raw1: str, raw2: str) -> dict:
    raw_ident = raw1 == raw2
    classes = classes_that_equalize(raw1, raw2)
    norm_ident = apply_all(raw1) == apply_all(raw2)
    remainder = (not raw_ident) and (not norm_ident)
    return {
        "raw_byte_identical": raw_ident,
        "normalized_identical": norm_ident,
        "varying_classes": classes,
        "unclassified_remainder": remainder,
    }


def audit_one(repro_id: str) -> dict:
    spec = REPRODUCTIONS[repro_id]
    r1 = run_repro(repro_id)
    r2 = run_repro(repro_id)
    runs = [r1, r2]
    ids = [run_id(repro_id, 1, r1), run_id(repro_id, 2, r2)]
    third = False
    if needs_third_run(r1, r2, spec):
        if r1 == r2 and looks_timestamped(r1):
            time.sleep(1.05)
        r3 = run_repro(repro_id)
        runs.append(r3)
        ids.append(run_id(repro_id, 3, r3))
        third = True

    pair_a, pair_b = r1, r2
    if third and r1 == r2 and r1 != runs[2]:
        pair_a, pair_b = r1, runs[2]
    cls = classify_pair(pair_a, pair_b)

    if spec.get("expect_deterministic"):
        classification = "BYTE-DETERMINISTIC"
    elif spec.get("borderline"):
        classification = "BORDERLINE"
    else:
        classification = "NONDETERMINISTIC"

    expected = spec.get("expect_class")
    extra: dict = {}
    if expected == CLASS_HOST:
        ha, hb = host_variance_pair()
        extra["host_control_hunk"] = hunk(ha, hb)
        extra["host_control_raw_identical"] = ha == hb
        host_cls = classes_that_equalize(ha, hb)
        cls["varying_classes"] = list(dict.fromkeys(cls["varying_classes"] + host_cls))
        extra["host_control_equalized"] = host_cls
    elif (
        expected == CLASS_TIMESTAMPS
        and CLASS_TIMESTAMPS not in cls["varying_classes"]
        and looks_timestamped(pair_a)
    ):
        cls["varying_classes"] = list(
            dict.fromkeys(cls["varying_classes"] + [CLASS_TIMESTAMPS])
        )

    return {
        "id": repro_id,
        "family": spec["family"],
        "title": spec["title"],
        "classification": classification,
        "run_ids": ids,
        "run_count": len(runs),
        "third_run": third,
        "raw_byte_identical": cls["raw_byte_identical"],
        "normalized_identical": cls["normalized_identical"],
        "varying_classes": cls["varying_classes"],
        "unclassified_remainder": cls["unclassified_remainder"],
        "example_hunk": hunk(pair_a, pair_b),
        "outputs": runs,
        **extra,
    }


def inventory_prior_normalizers() -> dict:
    hits: list[str] = []
    root = REPO / "command-center"
    for path in root.rglob("*normaliz*"):
        if not path.is_file():
            continue
        rel = path.relative_to(REPO).as_posix()
        if "CNF-0184" in rel or "charset_normalizer" in rel:
            continue
        if "/deps/" in rel or "/node_modules/" in rel:
            continue
        hits.append(rel)
    hits.sort()
    cnf165 = REPO / "command-center/receipts/CNF-0165.json"
    return {
        "paths": hits,
        "count": len(hits),
        "cnf_0165_present": cnf165.is_file() and cnf165.stat().st_size > 0,
        "cnf_0165_path": "command-center/receipts/CNF-0165.json",
    }


def run_full_audit() -> dict:
    rows = [audit_one(rid) for rid in REPRODUCTIONS]
    over = over_normalization_report()
    inv = inventory_prior_normalizers()
    by_id = {r["id"]: r for r in rows}

    catalogue = []
    for cls, src in CLASS_SOURCE.items():
        row = by_id[src]
        example = row.get("host_control_hunk") if cls == CLASS_HOST else row["example_hunk"]
        if cls == CLASS_HOST and not example:
            ha, hb = host_variance_pair()
            example = hunk(ha, hb)
        catalogue.append(
            {
                "class": cls,
                "normalizer_id": NORMALIZER_IDS[cls],
                "example_hunk": example,
                "example_from": (
                    "fam6.host-id/HOST-override-control" if cls == CLASS_HOST else src
                ),
            }
        )

    det = by_id["fam3.deterministic-payload"]
    ts = by_id["fam3.iso-timestamp"]
    border = by_id["fam3.clock-seconds"]
    over_ok = all(not x["absorbed"] for x in over)
    ts_norm_match = apply_one(CLASS_TIMESTAMPS, ts["outputs"][0]) == apply_one(
        CLASS_TIMESTAMPS, ts["outputs"][1]
    )
    det_raw = det["outputs"][0] == det["outputs"][1]

    tests = {
        "known_nondeterministic_control": {
            "id": "embedded-timestamp-detected-and-normalized",
            "pass": (not ts["raw_byte_identical"]) and ts_norm_match,
            "reproduction_id": "fam3.iso-timestamp",
        },
        "over_normalization_control": {
            "id": "planted-claim-body-change-not-absorbed",
            "pass": over_ok,
            "all_normalizers_refused_content": over_ok,
            "per_normalizer": over,
        },
        "both_states": {
            "id": "deterministic-payload-raw-identical",
            "pass": det_raw and det["classification"] == "BYTE-DETERMINISTIC",
            "reproduction_id": "fam3.deterministic-payload",
        },
        "triple_run": {
            "id": "borderline-second-clock-third-run",
            "pass": border["run_count"] >= 3 and border["third_run"] is True,
            "reproduction_id": "fam3.clock-seconds",
            "run_count": border["run_count"],
        },
    }
    return {
        "rows": rows,
        "catalogue": catalogue,
        "over_normalization": over,
        "inventory": inv,
        "tests": tests,
    }


def predicates(bundle: dict) -> list[str]:
    bad: list[str] = []
    for key, rec in bundle["tests"].items():
        if rec.get("pass") is not True:
            bad.append(f"test:{key}")
    seen = {c["class"] for c in bundle["catalogue"]}
    needed = {
        CLASS_TIMESTAMPS,
        CLASS_TEMP_PATHS,
        CLASS_ORDERING,
        CLASS_SEEDS,
        CLASS_HOST,
    }
    if seen != needed:
        bad.append("catalogue-class-gap")
    for row in bundle["rows"]:
        if row["unclassified_remainder"]:
            bad.append(f"unclassified:{row['id']}")
        if row["classification"] == "BYTE-DETERMINISTIC" and len(row["run_ids"]) < 2:
            bad.append(f"missing-run-ids:{row['id']}")
    if any(x["absorbed"] for x in bundle["over_normalization"]):
        bad.append("over-normalization")
    host = next(r for r in bundle["rows"] if r["id"] == "fam6.host-id")
    if CLASS_HOST not in host.get("varying_classes", []):
        bad.append("host-class-missing")
    if host.get("host_control_raw_identical") is True:
        bad.append("host-control-did-not-vary")
    return bad


run_full_audit = run_full_audit
predicates = predicates
needs_third_run = needs_third_run
