"""Walk cited greens and CI gates; keep only verdicts that depend on live inputs."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from classify import MAX_AGE_SECONDS, classify_stored_green

HERE = Path(__file__).resolve().parent
AUD = HERE.parent / "AUD-0041"
YAML_INV = AUD / "probe1-yaml-inventory.json"
ACTIONS = AUD / "probe2-actions-api.json"

LIVE_RULES: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(r"osv-scanner|osv\.dev|npm audit|trivy|dependabot", re.I),
        "advisory-database",
        "https://api.osv.dev/v1/query",
    ),
    (
        re.compile(r"ai-inference|models\.github\.ai|github models", re.I),
        "model-vendor-availability",
        "https://models.github.ai",
    ),
    (
        re.compile(r"ollama pull|SEMROUTER_EMBED_MODEL", re.I),
        "model-vendor-availability",
        "ollama-pull://SEMROUTER_EMBED_MODEL",
    ),
    (
        re.compile(r"@openai/codex|codex exec", re.I),
        "model-vendor-availability",
        "codex-cli-vendor-api",
    ),
]

LOCAL_MARKERS = re.compile(
    r"ruff|basedpyright|pytest|opengrep|gitleaks|runtime-junk|"
    r"skill-dual-write|charter consistency",
    re.I,
)
LIVE_OVERRIDE = re.compile(
    r"osv-scanner|ollama pull|ai-inference|@openai/codex|codex exec|dependabot",
    re.I,
)
LOCAL_CONTROL_GATE = "quality/lint"


def _blob(job: dict[str, Any]) -> str:
    return json.dumps(job, default=str)


def live_descriptor(job: dict[str, Any]) -> dict[str, str] | None:
    text = _blob(job)
    if LOCAL_MARKERS.search(text) and not LIVE_OVERRIDE.search(text):
        return None
    for pat, cls, endpoint in LIVE_RULES:
        if pat.search(text):
            return {"live_input_class": cls, "endpoint": endpoint}
    return None


def load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def ci_jobs() -> list[dict[str, Any]]:
    raw = load_json(YAML_INV) or {}
    rows: list[dict[str, Any]] = []
    for wf in raw.get("workflows") or []:
        for job in wf.get("jobs") or []:
            rows.append(
                {
                    "workflow_file": wf.get("file") or "",
                    "workflow_name": wf.get("name") or "",
                    "job_id": job.get("job_id"),
                    "job_name": job.get("name") or job.get("job_id"),
                    "job": job,
                }
            )
    return rows


def cited_successes() -> list[dict[str, Any]]:
    raw = load_json(ACTIONS) or {}
    rows: list[dict[str, Any]] = []
    for run in raw.get("runs") or []:
        for job in run.get("jobs") or []:
            if str(job.get("conclusion") or "").lower() != "success":
                continue
            rows.append(
                {
                    "workflow": run.get("workflow"),
                    "run_id": run.get("run_id"),
                    "job_name": job.get("name"),
                    "conclusion": job.get("conclusion"),
                    "citation_path": (
                        "command-center/p2-wave/probes/AUD-0041/probe2-actions-api.json"
                    ),
                }
            )
    return rows


def _norm(value: Any) -> str:
    return str(value or "").lower().replace("_", "-")


def _match_success(
    job_row: dict[str, Any], successes: list[dict[str, Any]]
) -> dict[str, Any] | None:
    jid = _norm(job_row.get("job_id"))
    jname = _norm(job_row.get("job_name"))
    wfile = _norm(job_row.get("workflow_file"))
    wname = _norm(job_row.get("workflow_name"))
    stem = _norm(Path(str(job_row.get("workflow_file") or "")).stem)
    for item in successes:
        wn = _norm(item.get("workflow"))
        sn = _norm(item.get("job_name"))
        wf_ok = (not wn) or wn in wfile or wn in wname or wn in stem or stem in wn
        if not wf_ok:
            continue
        if jid and jid in sn:
            return item
        if jname and (jname in sn or sn in jname):
            return item
        if "deps" in jid and "deps" in sn:
            return item
        if "routing" in jid and "routing" in sn:
            return item
    return None


def fixture_entries() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name in ("undated-cited-green.json", "invalidated-cited-green.json"):
        doc = load_json(HERE / "fixtures" / name) or {}
        ts = doc.get("query_timestamp")
        cls, treated = classify_stored_green(
            query_timestamp=ts,
            input_changed_after_query=bool(doc.get("input_changed_after_query")),
        )
        row = {
            "gate_id": doc["gate_id"],
            "live_input_class": doc["live_input_class"],
            "endpoint": doc["endpoint"],
            "query_timestamp": ts,
            "max_age_seconds": MAX_AGE_SECONDS,
            "classification": cls,
            "treated_as": treated,
            "cited_as_green": True,
            "citation_path": (
                f"command-center/p2-wave/probes/BLD-0046/fixtures/{name}"
            ),
            "rationale": str(doc.get("note") or cls),
        }
        if isinstance(doc.get("stored_verdict"), str):
            row["stored_verdict"] = doc["stored_verdict"]
        out.append(row)
    return out


def build_inventory(
    run_timestamps: dict[int, str | None] | None = None,
) -> dict[str, Any]:
    run_timestamps = run_timestamps or {}
    successes = cited_successes()
    entries: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    seen: set[str] = set()

    for row in ci_jobs():
        gate_id = f"{Path(str(row['workflow_file'])).stem}/{row['job_id']}"
        desc = live_descriptor(row["job"])
        cited = _match_success(row, successes)
        if desc is None:
            if cited or gate_id.endswith("/lint"):
                excluded.append(
                    {
                        "gate_id": gate_id,
                        "citation_path": (
                            cited["citation_path"]
                            if cited
                            else (
                                "command-center/p2-wave/probes/AUD-0041/"
                                "probe1-yaml-inventory.json"
                            )
                        ),
                        "why_excluded": (
                            "Verdict depends on repo bytes and a pinned local "
                            "tool, not a live advisory, registry, marketplace, "
                            "model, quota, or reachability source."
                        ),
                    }
                )
            continue

        rid = cited.get("run_id") if cited else None
        ts = run_timestamps.get(int(rid)) if isinstance(rid, int) else None
        if cited:
            cls, treated = classify_stored_green(query_timestamp=ts)
            if ts is None:
                rationale = (
                    "Cited CI success for a live-source gate; producing-query "
                    "timestamp missing after GitHub lookup — UNDATED-GREEN, "
                    "unknown, not a pass."
                )
            else:
                rationale = (
                    "Cited CI success for a live-source gate; timestamp compared "
                    "to TST-0235/AUD-0023 24h max-age. Stale stored green is "
                    "NOT-CHECKED, never a pass."
                )
        else:
            cls, treated = "LIVE-NO-STORED-GREEN", "NOT-APPLICABLE"
            rationale = (
                "Live-source gate is present in CI YAML; the Actions sample "
                "does not cite a stored green for this job."
            )
        if gate_id in seen:
            continue
        seen.add(gate_id)
        entry = {
            "gate_id": gate_id,
            "live_input_class": desc["live_input_class"],
            "endpoint": desc["endpoint"],
            "query_timestamp": ts,
            "max_age_seconds": MAX_AGE_SECONDS,
            "classification": cls,
            "treated_as": treated,
            "cited_as_green": bool(cited),
            "citation_path": (
                cited["citation_path"]
                if cited
                else (
                    "command-center/p2-wave/probes/AUD-0041/"
                    "probe1-yaml-inventory.json"
                )
            ),
            "rationale": rationale,
        }
        verdict = (cited or {}).get("conclusion")
        if isinstance(verdict, str):
            entry["stored_verdict"] = verdict
        if isinstance(rid, int):
            entry["run_id"] = rid
        entries.append(entry)

    for fx in fixture_entries():
        if fx["gate_id"] not in seen:
            seen.add(fx["gate_id"])
            entries.append(fx)

    if not any(x["gate_id"] == LOCAL_CONTROL_GATE for x in excluded):
        excluded.append(
            {
                "gate_id": LOCAL_CONTROL_GATE,
                "citation_path": (
                    "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
                ),
                "why_excluded": (
                    "ruff lint/format is a deterministic-input gate; the catalog "
                    "control requires it not appear in the decaying-green inventory."
                ),
            }
        )
    return {"entries": entries, "excluded_local_gates": excluded}
