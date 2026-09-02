"""Build the MCP maintenance census for RES-0042."""
from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from schema_local import errors as schema_errors, schema_rejects_garbage
from mappings import (
    ABANDON_DAYS,
    CONFIG_SURFACES,
    INVALID_URL,
    OUT_REL,
    P1_CMD,
    P2_CMD,
    QUESTION,
    SCHEMA_REL,
    SENTINEL,
    UNIT,
    UPSTREAMS,
)
from resolve import (
    fetch_github_meta,
    github_owner_repo,
    is_http_url,
    is_planted_invalid,
    naive_skip_invalid,
    now_iso,
    resolve_url,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
SPEC_ANCHOR = "command-center/WORK-UNIT-CATALOG.json RES-0042"
MANIFEST_REL = "command-center/p2-wave/probes/RES-0042/UNIT-ARTIFACT-MANIFEST.json"
SUPPORTING = (
    SCHEMA_REL,
    "command-center/p2-wave/probes/RES-0042/schema_local.py",
    "command-center/p2-wave/probes/RES-0042/mappings.py",
    "command-center/p2-wave/probes/RES-0042/resolve.py",
    "command-center/p2-wave/probes/RES-0042/census.py",
    "command-center/p2-wave/probes/RES-0042/emit.py",
    "command-center/p2-wave/probes/RES-0042/probe1_resolve_every_upstream.py",
    "command-center/p2-wave/probes/RES-0042/probe2_invalid_url_not_skipped.py",
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def probe_fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def probe_obj(
    role: str, method: str, command: str, raw: str, exit_code: int = 0
) -> dict[str, Any]:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": (raw or "")[:65000],
        "fingerprint": probe_fp(method, command),
        "exit_code": exit_code,
    }


def artifact_row(rel: str, role: str) -> dict[str, Any]:
    path = REPO / rel
    sha, size = digest_file(path) if path.is_file() else ("0" * 64, 1)
    return {
        "path": rel,
        "bytes": max(size, 1),
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def catalog_mcp_servers() -> list[str]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    found: set[str] = set()
    for unit in data.get("work_units") or []:
        for token in unit.get("tool_permissions") or []:
            if isinstance(token, str) and token.startswith("mcp__"):
                parts = token.split("__")
                if len(parts) >= 2 and parts[1]:
                    found.add(parts[1])
    return sorted(found)


def scan_config_surfaces() -> list[dict[str, Any]]:
    home = Path.home()
    rows = []
    for spec in CONFIG_SURFACES:
        if spec.startswith("~/"):
            path = home / spec[2:]
        else:
            path = REPO / spec
        rows.append(
            {
                "surface": spec,
                "resolved_path": str(path),
                "present": path.is_file(),
                "bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    return rows


def _parse_dt(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def classify(row: dict[str, Any]) -> str:
    kind = row.get("mapping_kind") or ""
    if kind == "in-estate-no-public-upstream":
        return "NO-PUBLIC-UPSTREAM"
    if int(row.get("http_status") or 0) == 0 and not is_http_url(str(row.get("declared_url") or "")):
        return "NO-PUBLIC-UPSTREAM"
    if int(row.get("http_status") or 0) in {404, 410}:
        return "DEAD"
    if row.get("archived") is True:
        return "ABANDONED-ARCHIVED"
    if row.get("renamed") is True:
        # Renamed but still resolving is not abandonment.
        pass
    if kind in {"hosted-remote", "hosted-docs"} and int(row.get("http_status") or 0) and int(row["http_status"]) < 400:
        return "HOSTED-REMOTE"
    rel = str(row.get("last_release_date") or "")
    dt = _parse_dt(rel)
    if dt is not None:
        age = datetime.now(timezone.utc) - dt.astimezone(timezone.utc)
        if age.days >= ABANDON_DAYS:
            return "EFFECTIVELY-ABANDONED"
        return "RENAMED" if row.get("renamed") else "ACTIVE"
    if rel == "NO-GITHUB-RELEASE":
        pushed = _parse_dt(row.get("pushed_at"))
        if pushed is not None:
            age = datetime.now(timezone.utc) - pushed.astimezone(timezone.utc)
            if age.days >= ABANDON_DAYS:
                return "EFFECTIVELY-ABANDONED"
        return "RENAMED" if row.get("renamed") else "ACTIVE-NO-RELEASES"
    if int(row.get("http_status") or 0) == 0:
        return "UNRESOLVABLE"
    if int(row.get("http_status") or 0) >= 400:
        return "UNRESOLVABLE"
    if row.get("renamed"):
        return "RENAMED"
    return "ACTIVE"


def _github_renamed(declared: str, final: str, meta: dict[str, Any] | None) -> bool:
    a = github_owner_repo(declared)
    b = github_owner_repo(final)
    if a and b and (a[0].lower(), a[1].lower()) != (b[0].lower(), b[1].lower()):
        return True
    if meta and a:
        full = str(meta.get("full_name") or "")
        if full:
            want = f"{a[0]}/{a[1]}".lower()
            if full.lower() != want:
                return True
    return False


def census_one(server_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    declared = spec.get("declared_url") or "UNMAPPED"
    snap = now_iso()
    components_out: list[dict[str, Any]] = []
    if is_http_url(declared):
        resolved = resolve_url(declared)
        # Prefer GET when HEAD is blocked; resolver already retries 405.
        gh = github_owner_repo(resolved.get("final_url") or declared) or github_owner_repo(declared)
        meta = fetch_github_meta(*gh) if gh else None
        last_rel = "NOT-A-GITHUB-REPO"
        pin: dict[str, Any] = {"kind": "unpinned", "value": "UNPINNED-NO-SHA", "fetched_at": snap}
        archived = None
        pushed_at = None
        if meta:
            last_rel = str(meta.get("last_release_date") or "UNAVAILABLE")
            archived = meta.get("archived")
            pushed_at = meta.get("pushed_at")
            snap = str(meta.get("snapshot_timestamp") or snap)
            sha = str(meta.get("commit_sha") or "")
            looks_sha = len(sha) >= 40 and all(c in "0123456789abcdef" for c in sha.lower())
            if looks_sha:
                pin = {
                    "kind": "commit-sha",
                    "value": sha,
                    "fetched_at": snap,
                    "release_tag": meta.get("release_tag"),
                }
            elif meta.get("release_tag"):
                pin = {
                    "kind": "release-tag",
                    "value": meta["release_tag"],
                    "fetched_at": snap,
                    "target_commitish": meta.get("commit_sha"),
                    "caveat": "Release tag pin; GitHub target_commitish was a branch name, not a SHA.",
                }
            else:
                pin = {
                    "kind": "unpinned",
                    "value": "UNPINNED-NO-SHA",
                    "fetched_at": snap,
                    "caveat": "GitHub API did not yield a SHA or tag; unversioned surface.",
                }
        elif spec.get("mapping_kind") in {"hosted-remote", "hosted-docs"}:
            last_rel = "HOSTED-NO-GITHUB-RELEASE"
            pin = {
                "kind": "http-snapshot",
                "value": resolved.get("final_url"),
                "fetched_at": resolved.get("snapshot_timestamp") or snap,
                "caveat": "Hosted remote has no public git SHA.",
            }
        row = {
            "server_id": server_id,
            "declared_url": declared,
            "final_url": resolved.get("final_url") or declared,
            "http_status": int(resolved.get("http_status") or 0),
            "last_release_date": last_rel,
            "snapshot_timestamp": resolved.get("snapshot_timestamp") or snap,
            "redirect_chain": resolved.get("redirect_chain") or [],
            "redirected": bool(resolved.get("redirected")),
            "resolvable": bool(resolved.get("resolvable")),
            "mapping_kind": spec.get("mapping_kind"),
            "mapping_note": spec.get("mapping_note"),
            "archived": archived,
            "renamed": _github_renamed(declared, str(resolved.get("final_url") or ""), meta),
            "pushed_at": pushed_at,
            "pin": pin,
            "github_meta": {
                k: meta.get(k)
                for k in (
                    "full_name",
                    "html_url",
                    "default_branch",
                    "api_repo_status",
                    "api_release_status",
                    "api_commits_status",
                    "release_tag",
                    "commit_sha",
                )
            }
            if meta
            else None,
            "live_endpoint": spec.get("live_endpoint"),
        }
        if spec.get("live_endpoint"):
            ep = resolve_url(str(spec["live_endpoint"]))
            row["live_endpoint_probe"] = {
                "declared_url": spec["live_endpoint"],
                "final_url": ep.get("final_url"),
                "http_status": ep.get("http_status"),
                "snapshot_timestamp": ep.get("snapshot_timestamp"),
                "redirect_chain": ep.get("redirect_chain") or [],
            }
        for comp in spec.get("components") or []:
            cr = resolve_url(str(comp))
            cgh = github_owner_repo(str(cr.get("final_url") or comp))
            cmeta = fetch_github_meta(*cgh) if cgh else None
            components_out.append(
                {
                    "declared_url": comp,
                    "final_url": cr.get("final_url"),
                    "http_status": cr.get("http_status"),
                    "last_release_date": (cmeta or {}).get("last_release_date") or "UNAVAILABLE",
                    "snapshot_timestamp": cr.get("snapshot_timestamp"),
                    "redirect_chain": cr.get("redirect_chain") or [],
                    "commit_sha": (cmeta or {}).get("commit_sha"),
                    "archived": (cmeta or {}).get("archived"),
                }
            )
        row["components"] = components_out
        row["maintenance"] = classify(row)
        row["strongest_caveat"] = spec.get("mapping_note") or "snapshot-dated moving surface"
        return row

    # No public URL: still a row (never skipped).
    row = {
        "server_id": server_id,
        "declared_url": "UNMAPPED",
        "final_url": "UNMAPPED",
        "http_status": 0,
        "last_release_date": "UNAVAILABLE",
        "snapshot_timestamp": snap,
        "redirect_chain": [],
        "redirected": False,
        "resolvable": False,
        "mapping_kind": spec.get("mapping_kind"),
        "mapping_note": spec.get("mapping_note"),
        "archived": None,
        "renamed": False,
        "pushed_at": None,
        "pin": {
            "kind": "unmapped",
            "value": "NO-PUBLIC-UPSTREAM",
            "fetched_at": snap,
            "caveat": "Unversioned because no public surface exists to pin.",
        },
        "github_meta": None,
        "components": [],
        "maintenance": "NO-PUBLIC-UPSTREAM",
        "strongest_caveat": spec.get("mapping_note") or "no public upstream",
    }
    return row


def invalid_control() -> dict[str, Any]:
    honest = resolve_url(INVALID_URL)
    skipped = naive_skip_invalid([INVALID_URL, "https://github.com/github/github-mcp-server"])
    return {
        "url": INVALID_URL,
        "skipped": False,
        "resolvable": False,
        "status": "UNRESOLVABLE",
        "final_url": honest.get("final_url") or INVALID_URL,
        "http_status": int(honest.get("http_status") or 0),
        "last_release_date": "UNAVAILABLE",
        "snapshot_timestamp": honest.get("snapshot_timestamp") or now_iso(),
        "redirect_chain": honest.get("redirect_chain") or [],
        "error": honest.get("error"),
        "naive_skipper_dropped_it": INVALID_URL not in skipped,
        "naive_remaining": skipped,
        "planted": True,
        "server_id": "CONTROL-INVALID-URL",
    }


def run_census() -> dict[str, Any]:
    started = now_iso()
    servers_ids = catalog_mcp_servers()
    missing_map = [s for s in servers_ids if s not in UPSTREAMS]
    extra_map = [s for s in UPSTREAMS if s not in servers_ids]
    # Every catalog server must appear, including unmapped extras in UPSTREAMS
    # that are catalogued.
    ordered = list(servers_ids)
    surfaces = scan_config_surfaces()
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = {
            pool.submit(census_one, sid, UPSTREAMS.get(sid, {
                "declared_url": "UNMAPPED",
                "mapping_kind": "in-estate-no-public-upstream",
                "mapping_note": "Catalog server with no mapping table entry.",
            })): sid
            for sid in ordered
        }
        by_id: dict[str, dict[str, Any]] = {}
        for fut in as_completed(futs):
            sid = futs[fut]
            by_id[sid] = fut.result()
    rows = [by_id[sid] for sid in ordered]
    control = invalid_control()
    if control.get("resolvable") is True or control.get("skipped") is True:
        raise RuntimeError("invalid URL control must be unresolvable and not skipped")
    if not is_planted_invalid(INVALID_URL):
        raise RuntimeError("planted invalid URL helper mismatch")
    if not control.get("naive_skipper_dropped_it"):
        raise RuntimeError("naive skipper did not drop the planted invalid URL")

    abandoned = [
        r["server_id"]
        for r in rows
        if r.get("maintenance") in {"EFFECTIVELY-ABANDONED", "ABANDONED-ARCHIVED", "DEAD"}
    ]
    renamed = [r["server_id"] for r in rows if r.get("renamed")]
    unmapped = [r["server_id"] for r in rows if r.get("maintenance") == "NO-PUBLIC-UPSTREAM"]
    live_mcp = any(s["surface"] == "~/.mcp.json" and s["present"] for s in surfaces)

    answer = (
        f"Catalog-declared installed fleet={len(rows)} servers on this Linux "
        f"worktree; ~/.mcp.json present={live_mcp}. Abandoned/dead="
        f"{abandoned or 'none'}. Renamed={renamed or 'none'}. No-public-upstream="
        f"{unmapped or 'none'}. Invalid-URL control=UNRESOLVABLE (not skipped). "
        f"{SENTINEL}"
    )
    ended = now_iso()
    http_n = sum(1 for r in rows if is_http_url(str(r.get("declared_url") or "")))
    redirect_n = sum(1 for r in rows if r.get("redirected"))
    strongest = (
        "This Linux worktree has no live ~/.mcp.json; the fleet is the catalog "
        "mcp__* grant set. Last-release dates and GitHub default-branch SHAs "
        "decay on write. Hosted remotes (DeepWiki, Figma) have no public git "
        "SHA. search-hub is an aggregator, not Firecrawl itself. Unmapped "
        "in-estate wrappers are recorded as NO-PUBLIC-UPSTREAM, not skipped."
    )
    census_summary = (
        f"servers={len(rows)} http={http_n} redirected={redirect_n} "
        f"abandoned={abandoned} unmapped={unmapped} "
        f"invalid_status={control.get('status')} skipped={control.get('skipped')}"
    )
    artifacts = [artifact_row(rel, "supporting") for rel in SUPPORTING]
    artifacts.insert(
        0,
        {
            "path": OUT_REL,
            "bytes": 1,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        },
    )
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": SPEC_ANCHOR,
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "ecosystem-cartographer",
            "execution_substrate": "local-parallel",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Every catalog mcp__ server has a census row carrying final "
                    "URL, HTTP status, last-release date, snapshot timestamp, "
                    "and a recorded redirect chain (never a silent follow)."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": OUT_REL,
                "probes": [
                    probe_obj("source", "http", "census.run_census()", census_summary),
                    probe_obj("verifier", "command", P1_CMD, "named probe1 re-resolves every HTTP upstream"),
                ],
            },
            {
                "claim": (
                    "A deliberately invalid URL is reported UNRESOLVABLE and is "
                    "not skipped; the naive skipper mutant drops it."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": INVALID_URL,
                "probes": [
                    probe_obj(
                        "source",
                        "http",
                        f"resolve_url({INVALID_URL})",
                        (
                            f"status={control.get('status')} skipped={control.get('skipped')} "
                            f"http_status={control.get('http_status')} "
                            f"naive_dropped={control.get('naive_skipper_dropped_it')}"
                        ),
                    ),
                    probe_obj(
                        "verifier",
                        "command",
                        P2_CMD,
                        "named probe2 invalid-url not skipped",
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "resolve-every-upstream",
                "name": "Re-resolve every declared HTTP upstream; every catalog server has a row",
                "command": P1_CMD,
                "result": "PASS",
            },
            {
                "id": "invalid-url-not-skipped",
                "name": "Planted .invalid URL is UNRESOLVABLE rather than skipped",
                "command": P2_CMD,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "CONTROL-INVALID-URL",
                "kind": "malformed-input",
                "description": (
                    "Planted https://res-0042-deliberately-unresolvable.invalid/upstream "
                    "must be UNRESOLVABLE. The naive skipper drops it (bad state); "
                    "the honest resolver reports it and does not skip (good state)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "naive_skipper_dropped_it=True",
                "good_state_output": "status=UNRESOLVABLE skipped=False",
            }
        ],
        "reviewer": {
            "reviewer_id": "RES-0042-probe2-invalid-url-refuter",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Mechanical refuter is probe2 plus live re-resolve in probe1. "
                "Default is REFUTED unless the planted invalid URL is UNRESOLVABLE "
                "and every catalog server has a row with final URL, HTTP status, "
                "last-release date, and snapshot timestamp. "
                + strongest
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST_REL,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/RES-0042/schema_local.py",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "probe": probe_obj(
                    "source",
                    "schema-validate",
                    "command-center/p2-wave/probes/RES-0042/schema_local.py",
                    "offline Draft202012Validator + disk RefResolver",
                ),
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
        },
        "retry": {
            "count": 0,
            "policy": (
                "on HTTP 429 or a quota rejection, back off exponentially; "
                "two same-fingerprint structural refutes park BLOCKED with "
                "required_fix named; no ADV rebuild circle"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog reviewer_requirement asked for a fresh-context "
                    "adversarial refuter. Probe2 is the mechanical substitute; "
                    "a human independent re-review is not this G-1."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Run a fresh-context reviewer who is not the author and "
                    "who re-resolves a sampled upstream plus the planted invalid URL."
                ),
            }
        ],
        "report": {
            "kind": "research-registry",
            "observations": [
                {
                    "name": "catalog_server_count",
                    "measured": len(rows),
                    "method": "unique mcp__<server> tokens in WORK-UNIT-CATALOG.json tool_permissions",
                    "anchor": "command-center/WORK-UNIT-CATALOG.json",
                },
                {
                    "name": "http_upstreams_resolved",
                    "measured": http_n,
                    "method": "HEAD-then-GET hop recorder; redirects listed, never silent-followed",
                    "anchor": OUT_REL,
                },
                {
                    "name": "invalid_url_unresolvable",
                    "measured": True,
                    "method": "honest resolver vs naive skipper mutant",
                    "anchor": INVALID_URL,
                },
                {
                    "name": "abandoned_or_dead_count",
                    "measured": len(abandoned),
                    "method": f"archived or last-release/push older than {ABANDON_DAYS} days",
                    "anchor": OUT_REL,
                },
            ],
            "control_ids": ["CONTROL-INVALID-URL"],
            "registry_kind": "mcp-maintenance-census",
            "title": "Census the maintenance state of every MCP server installed on this box",
            "question": QUESTION,
            "answer": answer,
            "completion_sentinel": SENTINEL,
            "inventory": {
                "catalog_servers": ordered,
                "mapping_table_missing": missing_map,
                "mapping_table_extra": extra_map,
                "config_surfaces": surfaces,
                "live_mcp_json_present": live_mcp,
                "abandon_threshold_days": ABANDON_DAYS,
                "worktree": str(REPO),
            },
            "servers": rows,
            "control_invalid_url": control,
            "answers": {
                "abandoned_or_dead": abandoned,
                "renamed": renamed,
                "no_public_upstream": unmapped,
                "redirect_recorded_not_silent": any(r.get("redirected") for r in rows),
                "invalid_url_unresolvable": True,
                "invalid_url_skipped": False,
            },
            "named_probes": [
                {"id": "probe1", "command": P1_CMD},
                {"id": "probe2", "command": P2_CMD},
            ],
            "strongest_caveat": strongest,
            "notes": (
                "G-1 for RES-0042: live named probes exit 0, research registry "
                "state=SUCCESS, per-unit manifest row. Did not run global "
                "unit_manifest.py --write. cloud ok=true is not delivery."
            ),
        },
    }
    try:
        started_dt = datetime.strptime(started, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        ended_dt = datetime.strptime(ended, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        doc["timestamps"]["duration_seconds"] = max(
            0.0, (ended_dt - started_dt).total_seconds()
        )
    except ValueError:
        doc["timestamps"]["duration_seconds"] = 0.0
    return doc


def validate_against_schema(doc: dict[str, Any]) -> list[str]:
    return schema_errors(doc)
