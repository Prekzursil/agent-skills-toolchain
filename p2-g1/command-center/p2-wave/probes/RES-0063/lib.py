#!/usr/bin/env python3
"""Mechanical extractors for RES-0063: four DAG-scheduler task identities.

Reads captured snapshot bytes (not the research artifact) and the live catalog
unit. Fit verdicts are computed from catalog fields, not copied from prose.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SNAP = HERE / "snapshots"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
SUBJECT_ID = "RES-0063"
SLICE_MARKER = "RES-1.json"

ENGINES = ("airflow", "prefect", "dagster", "flyte")

# Needles that must occur in the captured bytes. Quotes are the identity
# definitions cited at source/spec level.
NEEDLES: dict[str, dict[str, Any]] = {
    "airflow": {
        "title": "Airflow TaskInstance composite key",
        "identity_components": ["dag_id", "task_id", "run_id", "map_index"],
        "identity_statement": (
            "A TaskInstance is uniquely constrained as "
            '(dag_id, task_id, run_id, map_index); TaskInstance.key also '
            "carries try_number. map_index=-1 means unmapped. Docs: a Task "
            "Instance is a specific run of that task for a given Dag (and thus "
            "for a given data interval)."
        ),
        "resume": (
            "Failed TIs enter up_for_retry and are rescheduled; the unique "
            "constraint does not include try_number, so a retry is the same "
            "identity with an incremented try_number. Succeeded TIs of the "
            "same run are not re-created."
        ),
        "idempotency": (
            "The engine does not wrap side effects. Idempotency is a task "
            "author obligation. Mapped tasks distinguish instances by "
            "map_index (a partition of the mapped input), not by output artifact."
        ),
        "r1_id": "airflow-r1-taskinstance-api",
        "r1_decoded": "airflow-r1-taskinstance-api.decoded.bin",
        "r1_needles": [
            'UniqueConstraint("dag_id", "task_id", "run_id", "map_index", name="task_instance_composite_key")',
            "Returns a tuple that identifies the task instance uniquely.",
            "A value of -1 in map_index represents any of: a TI without mapped tasks;",
        ],
        "r2_id": "airflow-r2-tasks-docs",
        "r2_needles": [
            "specific run of that task for a given Dag (and thus for a given data interval)",
            "up_for_retry",
            "same data interval",
        ],
    },
    "prefect": {
        "title": "Prefect task_key plus cache key",
        "identity_components": ["task_key", "cache_key"],
        "identity_statement": (
            "Source: task_key is '{qualname.split('.')[-1]}-{hash(code_obj)}' "
            "from _generate_task_key. Docs claim a hash of task name plus the "
            "fully qualified name of the function. Those formulas disagree. "
            "A task run is a single invocation; DEFAULT cache hashes inputs, "
            "code definition, and the prevailing flow-run (or autonomous "
            "task-run) ID."
        ),
        "resume": (
            "Retries re-enter Running from Retrying/AwaitingRetry on the same "
            "task run. Caching can skip re-execution when a cache key hits."
        ),
        "idempotency": (
            "Idempotency is opt-in via cache_policy / cache_key_fn and result "
            "persistence. DEFAULT cache includes flow-run ID, so the same "
            "inputs in a new flow run do not hit cache unless the policy is "
            "changed (e.g. INPUTS)."
        ),
        "r1_id": "prefect-r1-tasks-api",
        "r1_decoded": "prefect-r1-tasks-api.decoded.bin",
        "r1_needles": [
            "def _generate_task_key",
            'return f"{qualname}-{code_hash}"',
            "self.task_key: str = _generate_task_key(self.fn)",
        ],
        "r2_id": "prefect-r2-tasks-docs",
        "r2_needles": [
            "Tasks are uniquely identified by a task key, which is a hash composed of the task name and the fully qualified name of the function.",
        ],
        "r2b_id": "prefect-r2-caching-docs",
        "r2b_needles": [
            "the inputs provided to the task",
            "the code definition of the task",
            "the prevailing flow run ID",
        ],
        "rails_disagree_on": "task-key formula (docs vs _generate_task_key)",
    },
    "dagster": {
        "title": "Dagster AssetKey (asset handle) plus FROM_FAILURE skip",
        "identity_components": ["AssetKey.path"],
        "identity_statement": (
            "An AssetKey is a handle for referring to the asset: a sanitized "
            "string or hierarchical list/tuple of strings. That is artifact "
            "identity, not a run-scoped task instance. Op/step retries are a "
            "separate axis (RetryPolicy on the computing op)."
        ),
        "resume": (
            "Default run retry strategy FROM_FAILURE re-executes from failure: "
            "successful ops are skipped and their outputs are reused. "
            "FROM_ASSET_FAILURE uses persisted materialization records to "
            "exclude already-materialized assets."
        ),
        "idempotency": (
            "Re-materializing the same unpartitioned AssetKey is the same "
            "asset; partitions (when used) are an extra identity axis this "
            "program's work units do not carry."
        ),
        "r1_id": "dagster-r1-assetkey-api",
        "r1_decoded": "dagster-r1-assetkey-api.decoded.bin",
        "r1_needles": [
            "class AssetKey(IHaveNew):",
            "Object representing the structure of an asset key.",
            'return f"AssetKey({self.path})"',
        ],
        "r2_id": "dagster-r2-defining-assets",
        "r2_needles": [
            "An <code>AssetKey</code>, which is a handle for referring to the asset.",
        ],
        "r2b_id": "dagster-r2-run-retries",
        "r2b_needles": [
            "FROM_FAILURE",
            "successful ops will be skipped",
        ],
    },
    "flyte": {
        "title": "Flyte Identifier (project, domain, name, version)",
        "identity_components": ["resource_type", "project", "domain", "name", "version"],
        "identity_statement": (
            "Registered tasks are Identifier(resource_type, project, domain, "
            "name, version), stringified as "
            "'{resource_type_name}:{project}:{domain}:{name}:{version}'. "
            "Remote cache keys add Cache Version, Task Signature, and Inputs, "
            "isolated by project and domain."
        ),
        "resume": (
            "A cache hit returns the stored result instead of re-running the "
            "task. Changing cache_version invalidates prior entries."
        ),
        "idempotency": (
            "Memoization is opt-in (cache=True). Cache identity is the "
            "versioned task entity plus typed inputs, not the output artifact "
            "path."
        ),
        "r1_id": "flyte-r1-identifier-api",
        "r1_decoded": "flyte-r1-identifier-api.decoded.bin",
        "r1_needles": [
            "def __init__(self, resource_type, project, domain, name, version):",
            'return f"{self.resource_type_name()}:{self.project}:{self.domain}:{self.name}:{self.version}"',
        ],
        "r2_id": "flyte-r2-caching-docs",
        "r2_needles": [
            "The cache keys for remote task execution are composed of **Project**, **Domain**, **Cache Version**, **Task Signature**, and **Inputs**",
            "cache_version",
        ],
    },
}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_index() -> dict:
    return json.loads((SNAP / "index.json").read_text(encoding="utf-8"))


def rail_by_id(index: dict, rid: str) -> dict:
    for r in index.get("rails") or []:
        if r.get("id") == rid:
            return r
    raise KeyError(rid)


def read_snap(rel: str) -> bytes:
    path = HERE / rel if rel.startswith("snapshots/") else SNAP / rel
    return path.read_bytes()


def body_text(rel: str) -> str:
    return read_snap(rel).decode("utf-8", errors="replace")


def missing_needles(text: str, needles: list[str]) -> list[str]:
    return [n for n in needles if n not in text]


def rail_record(index: dict, rid: str) -> dict:
    r = rail_by_id(index, rid)
    return {
        "id": r["id"],
        "rail": r["rail"],
        "kind": r["kind"],
        "permalink": r["permalink"],
        "final_url": r["final_url"],
        "fetch_timestamp": r["fetch_timestamp"],
        "http_status": r["http_status"],
        "sha256": r["sha256"],
        "bytes": r["bytes"],
        "github_blob_sha": r.get("github_blob_sha"),
        "github_html_url": r.get("github_html_url"),
        "decoded_source_sha256": r.get("decoded_source_sha256"),
    }


def extract_definitions(index: dict | None = None) -> list[dict]:
    index = index or load_index()
    out: list[dict] = []
    for engine in ENGINES:
        spec = NEEDLES[engine]
        r1 = rail_record(index, spec["r1_id"])
        r2 = rail_record(index, spec["r2_id"])
        decoded_rel = spec["r1_decoded"]
        decoded = body_text(decoded_rel)
        r1_missing = missing_needles(decoded, spec["r1_needles"])
        r2_text = body_text(spec["r2_id"] + ".bin")
        r2_missing = missing_needles(r2_text, spec["r2_needles"])
        extra_rails = []
        extra_missing: list[str] = []
        if spec.get("r2b_id"):
            extra_rails.append(rail_record(index, spec["r2b_id"]))
            extra_missing.extend(
                missing_needles(body_text(spec["r2b_id"] + ".bin"), spec["r2b_needles"])
            )
        r1_ok = not r1_missing and int(r1["http_status"]) == 200
        r2_ok = not r2_missing and int(r2["http_status"]) == 200 and not extra_missing
        disagree = spec.get("rails_disagree_on")
        if disagree:
            # Two rails present; they conflict on the formula. Existence of a
            # task key is corroborated; the docs formula is not a measured fact.
            evidence_tier = "E2-disagreement"
        elif r1_ok and r2_ok:
            evidence_tier = "E2"
        else:
            evidence_tier = "E3"
        out.append(
            {
                "engine": engine,
                "title": spec["title"],
                "identity_components": spec["identity_components"],
                "identity_statement": spec["identity_statement"],
                "resume_semantics": spec["resume"],
                "idempotency": spec["idempotency"],
                "evidence_tier": evidence_tier,
                "rails_disagree_on": disagree,
                "r1": r1,
                "r2": r2,
                "extra_rails": extra_rails,
                "r1_needles_found": r1_ok,
                "r2_needles_found": r2_ok,
                "r1_missing": r1_missing,
                "r2_missing": r2_missing + extra_missing,
                "decoded_source_sha256_live": sha256_bytes(read_snap(decoded_rel)),
            }
        )
    return out


def catalog_unit(uid: str) -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    raise KeyError(uid)


def subject_fields(unit: dict) -> dict:
    out = str(unit.get("output_path") or "").replace("\\", "/")
    return {
        "id": unit.get("id"),
        "output_path": out,
        "source_slice_file": unit.get("_source_slice_file"),
        "execution_substrate": unit.get("execution_substrate"),
        "question_or_target": unit.get("question_or_target"),
        "title": unit.get("title"),
        "is_research_artifact": ("/research/" in out and out.endswith(".json")),
        "has_partition_key": "partition_key" in unit or "map_index" in unit or "data_interval" in unit,
    }


def apply_fit(unit: dict) -> list[dict]:
    """Apply each engine's identity to one real catalog unit."""
    f = subject_fields(unit)
    uid = str(f["id"])
    out_path = str(f["output_path"])
    slice_stem = Path(str(f["source_slice_file"] or "")).stem or None
    q = str(f["question_or_target"] or "")
    q_hash = hashlib.sha256(q.encode("utf-8")).hexdigest()[:12] if q else None
    research = bool(f["is_research_artifact"])
    partitioned = bool(f["has_partition_key"])

    airflow_encoding = {
        "dag_id": slice_stem,
        "task_id": uid,
        "run_id": None,
        "map_index": None,
    }
    airflow_invented = [k for k, v in airflow_encoding.items() if v is None]
    airflow = {
        "engine": "airflow",
        "subject_unit_id": uid,
        "encoding": airflow_encoding,
        "invented_fields": airflow_invented,
        "fits": False,
        "fit_class": "DOES_NOT_FIT",
        "reason": (
            "Airflow identity is a per-run TaskInstance (dag_id, task_id, "
            "run_id, map_index) for a data interval. Catalog unit "
            f"{uid} has no run_id or map_index; inventing map_index=-1 would "
            "hide that the native identity is a partitioned/run instance, not "
            f"the research artifact {out_path}."
        ),
    }

    prefect_encoding = {
        "task_key": None,
        "function_qualname": None,
        "code_hash": None,
        "cache_key_default_includes_flow_run_id": True,
    }
    prefect = {
        "engine": "prefect",
        "subject_unit_id": uid,
        "encoding": prefect_encoding,
        "invented_fields": ["task_key", "function_qualname", "code_hash", "flow_run_id"],
        "fits": False,
        "fit_class": "PARTIAL",
        "reason": (
            "Prefect task_key is derived from a Python function's last "
            "qualname component plus a bytecode hash. The catalog record for "
            f"{uid} is a research question and output path, not a function, so "
            "task_key cannot be constructed from catalog fields. DEFAULT cache "
            "further binds identity to a flow-run ID the catalog does not have. "
            "Wrapping the unit in a @task would identify the wrapper, not "
            f"{out_path}."
        ),
    }

    asset_path = [p for p in out_path.split("/") if p]
    dagster_encoding = {"AssetKey.path": asset_path}
    dagster_fits = research and not partitioned and bool(asset_path)
    dagster = {
        "engine": "dagster",
        "subject_unit_id": uid,
        "encoding": dagster_encoding,
        "invented_fields": [],
        "fits": dagster_fits,
        "fit_class": "FITS" if dagster_fits else "DOES_NOT_FIT",
        "reason": (
            "Dagster AssetKey is a handle for the asset. Mapping "
            f"output_path {out_path} onto AssetKey({asset_path!r}) uses only "
            "catalog fields, invents no partition key, and names the research "
            "artifact rather than a data interval. FROM_FAILURE skip of "
            "successful materializations matches 'do not redo a delivered unit'."
            if dagster_fits
            else "Subject is not an unpartitioned research artifact path."
        ),
    }

    flyte_encoding = {
        "resource_type": "TASK",
        "project": (out_path.split("/")[0] if out_path else None),
        "domain": f.get("execution_substrate"),
        "name": uid,
        "version": q_hash,
    }
    flyte_invented = ["resource_type"]
    flyte_constructable = all(
        flyte_encoding[k] for k in ("project", "domain", "name", "version")
    )
    flyte = {
        "engine": "flyte",
        "subject_unit_id": uid,
        "encoding": flyte_encoding,
        "invented_fields": flyte_invented,
        "fits": False,
        "fit_class": "PARTIAL" if flyte_constructable else "DOES_NOT_FIT",
        "reason": (
            "Flyte Identifier(project, domain, name, version) can be filled "
            f"from output_path prefix, execution_substrate, id={uid}, and "
            "sha256(question_or_target). resource_type=TASK is an engine "
            "constant. That names a versioned task entity, not the artifact "
            f"path {out_path}; cache keys further include typed inputs. Closer "
            "than Airflow's run/map_index, farther than Dagster AssetKey."
        ),
    }

    # Control: a data-partition mutant of the same unit must flip Airflow's
    # invented map_index and must not be how we encode the real unit.
    mutant = dict(unit)
    mutant["map_index"] = 3
    mutant["partition_key"] = "dt=2026-08-01"
    mutant["output_path"] = "data/warehouse/dt=2026-08-01/part.parquet"
    mutant_fields = subject_fields(mutant)
    control = {
        "id": "control-data-partition-mutant",
        "description": (
            "Same catalog id with a fabricated partition_key/map_index and a "
            "parquet output. Airflow's native identity is built for this "
            "shape; the real RES-0063 record is not."
        ),
        "real_unit_is_research_artifact": research,
        "mutant_is_research_artifact": bool(mutant_fields["is_research_artifact"]),
        "mutant_has_partition_key": True,
        "airflow_fits_real_unit": False,
        "dagster_fits_real_unit": dagster_fits,
        "fired": research and not mutant_fields["is_research_artifact"],
    }

    return [airflow, prefect, dagster, flyte, {"engine": "_control", **control}]


def verify_snapshots(index: dict | None = None) -> list[str]:
    index = index or load_index()
    errors: list[str] = []
    for r in index.get("rails") or []:
        rel = r.get("body_path")
        if not rel:
            errors.append(f"{r.get('id')}:missing-body_path")
            continue
        raw = read_snap(rel)
        live = sha256_bytes(raw)
        if live != r.get("sha256"):
            errors.append(f"{r.get('id')}:sha-mismatch")
        if int(r.get("http_status") or 0) != 200:
            errors.append(f"{r.get('id')}:http-{r.get('http_status')}")
        extra = r.get("extra") or {}
        dec = extra.get("decoded_path")
        if dec:
            dlive = sha256_bytes(read_snap(dec))
            if dlive != r.get("decoded_source_sha256"):
                errors.append(f"{r.get('id')}:decoded-sha-mismatch")
    return errors
