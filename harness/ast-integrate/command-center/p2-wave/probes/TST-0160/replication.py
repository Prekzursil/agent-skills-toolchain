"""Label intentional cross-vendor replication; never double-count coverage.

A pair of vendor runs of the same catalog id is one logical unit with two
observations. Independence is claimed only when the runs share no input
artifact (path or content hash). Same vendor plus same inputs is DUPLICATION,
not independence. Coverage denominator is the catalog's unique unit-id set;
counting each run inflates it and must fail.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIVE_CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
FIXTURE_CATALOG = HERE / "fixtures" / "catalog.json"
INTER_A = HERE / "fixtures" / "intermediates" / "vendor-a" / "slice.json"
INTER_B = HERE / "fixtures" / "intermediates" / "vendor-b" / "slice.json"
CNF_MATRIX = (
    REPO / "command-center" / "confirmation" / "CNF-0007-crossvendor-matrix.json"
)

LABEL_INDEPENDENT = "INDEPENDENT-REPLICATION"
LABEL_DUPLICATION = "DUPLICATION"
LABEL_SHARED_INPUT = "NOT-INDEPENDENT-SHARED-INPUT"
REPL_ID = "TST-0160-REPL"
LIVE_UID = "TST-0160"


def repo_rel(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO).as_posix()
    except ValueError:
        return resolved.as_posix()


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> dict:
    raw = path.read_bytes()
    return {
        "bytes": len(raw.replace(b"\r\n", b"\n")),
        "path": repo_rel(path),
        "sha256": sha256_bytes(raw),
    }


@dataclass(frozen=True)
class Artifact:
    path: str
    sha256: str
    bytes: int

    def key(self) -> tuple[str, str]:
        return (self.path, self.sha256)


@dataclass(frozen=True)
class Observation:
    unit_id: str
    vendor: str
    model: str
    artifacts: tuple[Artifact, ...]

    def provenance(self) -> frozenset[tuple[str, str]]:
        return frozenset(a.key() for a in self.artifacts)

    def sha_set(self) -> frozenset[str]:
        return frozenset(a.sha256 for a in self.artifacts)

    def path_set(self) -> frozenset[str]:
        return frozenset(a.path for a in self.artifacts)

    def to_dict(self) -> dict:
        return {
            "artifacts": [
                {"bytes": a.bytes, "path": a.path, "sha256": a.sha256}
                for a in self.artifacts
            ],
            "model": self.model,
            "unit_id": self.unit_id,
            "vendor": self.vendor,
        }


def observe(unit_id: str, vendor: str, model: str, *paths: Path) -> Observation:
    arts = []
    for path in paths:
        rec = digest_file(path)
        arts.append(
            Artifact(path=rec["path"], sha256=rec["sha256"], bytes=rec["bytes"])
        )
    return Observation(
        unit_id=unit_id,
        vendor=vendor,
        model=model,
        artifacts=tuple(arts),
    )


def catalog_ids(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    units = data.get("work_units") or data.get("items") or []
    ids: list[str] = []
    for unit in units:
        if isinstance(unit, dict) and unit.get("id"):
            ids.append(str(unit["id"]))
    return ids


def catalog_denominator(ids: Iterable[str]) -> int:
    return len(set(ids))


def provenance_diff(left: Observation, right: Observation) -> dict:
    shared_sha = left.sha_set() & right.sha_set()
    shared_path = left.path_set() & right.path_set()
    return {
        "a_n": len(left.artifacts),
        "b_n": len(right.artifacts),
        "disjoint": not shared_sha and not shared_path,
        "left_sha256": sorted(left.sha_set()),
        "right_sha256": sorted(right.sha_set()),
        "shared_paths": sorted(shared_path),
        "shared_sha256": sorted(shared_sha),
    }


def classify_pair(left: Observation, right: Observation) -> dict:
    if left.unit_id != right.unit_id:
        raise ValueError("pair is not the same logical unit")
    diff = provenance_diff(left, right)
    same_vendor = left.vendor == right.vendor
    same_inputs = left.provenance() == right.provenance()
    if same_vendor and same_inputs:
        label = LABEL_DUPLICATION
        independence = False
        reason = "same vendor and same input artifacts"
    elif same_vendor:
        label = LABEL_DUPLICATION
        independence = False
        reason = "same vendor; independence requires two vendors"
    elif not diff["disjoint"]:
        label = LABEL_SHARED_INPUT
        independence = False
        reason = "vendors differ but shared input artifact"
    else:
        label = LABEL_INDEPENDENT
        independence = True
        reason = "distinct vendors and disjoint input provenance"
    return {
        "independence_claimed": independence,
        "label": label,
        "logical_unit_count": 1,
        "logical_unit_id": left.unit_id,
        "observation_count": 2,
        "provenance_diff": diff,
        "reason": reason,
        "same_inputs": same_inputs,
        "same_vendor": same_vendor,
        "vendors": [left.vendor, right.vendor],
    }


def mutant_independence_if_vendors_differ(left: Observation, right: Observation) -> bool:
    """Negative mutant: claims independence whenever vendors differ."""
    return left.vendor != right.vendor and left.unit_id == right.unit_id


def coverage(
    catalog_unit_ids: Sequence[str],
    observations: Sequence[Observation],
    *,
    count_each_run: bool = False,
) -> dict:
    denom_catalog = catalog_denominator(catalog_unit_ids)
    if count_each_run:
        denom = len(observations)
        mode = "count-each-run"
    else:
        denom = denom_catalog
        mode = "logical-unit-once"
    covered = {obs.unit_id for obs in observations}
    unknown = sorted(uid for uid in covered if uid not in set(catalog_unit_ids))
    return {
        "catalog_unique_ids": denom_catalog,
        "count_each_run": count_each_run,
        "covered_logical_units": len(covered),
        "denominator": denom,
        "inflated": denom != denom_catalog,
        "mode": mode,
        "observation_count": len(observations),
        "unknown_unit_ids": unknown,
    }


def reject_inflated_coverage(cov: Mapping[str, object]) -> list[str]:
    errors: list[str] = []
    if cov.get("inflated") is True:
        errors.append(
            "counting both runs toward coverage "
            f"(denominator={cov.get('denominator')} "
            f"catalog_unique={cov.get('catalog_unique_ids')})"
        )
    if cov.get("unknown_unit_ids"):
        errors.append(f"observations outside catalog: {cov.get('unknown_unit_ids')}")
    return errors


def fixture_catalog_ids() -> list[str]:
    return catalog_ids(FIXTURE_CATALOG)


def live_catalog_once(uid: str = LIVE_UID) -> dict:
    if not LIVE_CATALOG.is_file():
        return {
            "catalog": repo_rel(LIVE_CATALOG),
            "present": False,
            "uid": uid,
            "uid_occurrences": 0,
            "unique_ids": 0,
        }
    ids = catalog_ids(LIVE_CATALOG)
    return {
        "catalog": repo_rel(LIVE_CATALOG),
        "present": True,
        "uid": uid,
        "uid_occurrences": ids.count(uid),
        "unique_ids": catalog_denominator(ids),
    }


def cnf_vendor_frames(uid: str = LIVE_UID) -> dict:
    if not CNF_MATRIX.is_file():
        return {"present": False, "uid": uid, "rows": 0, "cross_vendor_rows": 0}
    data = json.loads(CNF_MATRIX.read_text(encoding="utf-8"))
    rows = data if isinstance(data, list) else data.get("rows") or data.get("items") or []
    matched = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("claim_id") or row.get("id") or "") != uid:
            continue
        matched.append(
            {
                "confirmer_vendor": row.get("confirmer_vendor"),
                "implementer_vendor": row.get("implementer_vendor"),
                "independence_class": row.get("independence_class"),
                "vendor_pair_cross": row.get("vendor_pair_cross"),
            }
        )
    return {
        "cross_vendor_rows": sum(
            1 for rec in matched if rec.get("vendor_pair_cross") is True
        ),
        "present": True,
        "rows": len(matched),
        "samples": matched[:3],
        "uid": uid,
    }


def write_ledger(
    dest: Path,
    observations: Sequence[Observation],
    extra: Mapping[str, object] | None = None,
) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "observations": [obs.to_dict() for obs in observations],
        **(dict(extra) if extra else {}),
    }
    dest.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return dest


def independent_pair() -> tuple[Observation, Observation]:
    left = observe(REPL_ID, "anthropic", "opus", INTER_A)
    right = observe(REPL_ID, "openai", "opus", INTER_B)
    return left, right


def duplicate_pair() -> tuple[Observation, Observation]:
    left = observe(REPL_ID, "anthropic", "opus", INTER_A)
    right = observe(REPL_ID, "anthropic", "opus", INTER_A)
    return left, right


def shared_input_pair() -> tuple[Observation, Observation]:
    left = observe(REPL_ID, "anthropic", "opus", INTER_A)
    right = observe(REPL_ID, "openai", "opus", INTER_A)
    return left, right


def coverage_cohort() -> list[Observation]:
    singles = [
        observe("TST-0160-L01", "anthropic", "opus", INTER_A),
        observe("TST-0160-L02", "anthropic", "opus", INTER_A),
        observe("TST-0160-L03", "anthropic", "opus", INTER_A),
        observe("TST-0160-L04", "anthropic", "opus", INTER_A),
    ]
    left, right = independent_pair()
    return singles + [left, right]
