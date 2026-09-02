#!/usr/bin/env python3
"""Maintenance-state extractor: measure, never trust discovery-time prose.

Signal A: GitHub-like API (last push, archived, latest release, issue
velocity) captured with the query date.
Signal B: default-branch HEAD commit date from the git ref itself.

A source with no reachable metadata is NOT-CHECKED. Prose is never copied
into measured fields. Archived + ADOPT-AS-IS is flagged for disposition.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from git_refs import normalize_iso

WINDOW_DAYS = 90
QUERY_DATE = "2026-08-24T18:00:00Z"

DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2}|20\d{2})\b")
NOT_ARCHIVED_RE = re.compile(r"\bnot[ -]archived\b", re.I)
ARCHIVED_RE = re.compile(r"\barchived\b", re.I)
ACTIVE_RE = re.compile(
    r"\b(actively maintained|healthy|weekly commits|adopt as-is)\b", re.I
)


def is_externally_sourced(candidate: dict) -> bool:
    if "externally_sourced" in candidate:
        return bool(candidate["externally_sourced"])
    origin = str(candidate.get("origin") or "")
    return bool(
        origin.startswith("github:")
        or origin.startswith("https://github.com/")
        or origin.startswith("gh:")
    )


def repo_id(candidate: dict) -> tuple[str, str] | None:
    repo = candidate.get("repo") or {}
    owner = str(repo.get("owner") or "")
    name = str(repo.get("name") or "")
    if owner and name:
        return owner, name
    origin = str(candidate.get("origin") or "")
    for prefix in ("github:", "gh:"):
        if origin.startswith(prefix):
            rest = origin[len(prefix) :].strip().rstrip("/")
            rest = rest.replace("https://github.com/", "")
            parts = rest.split("/")
            if len(parts) >= 2:
                return parts[0], parts[1]
    return None


def parse_prose(text: str) -> dict:
    raw = text or ""
    not_archived = bool(NOT_ARCHIVED_RE.search(raw))
    archived_word = bool(ARCHIVED_RE.search(raw))
    return {
        "raw": raw,
        "says_archived": archived_word and not not_archived,
        "says_not_archived": not_archived,
        "says_active": bool(ACTIVE_RE.search(raw)),
        "dates": DATE_RE.findall(raw),
    }


def infer_from_prose(prose: str) -> dict:
    """FORBIDDEN path. Default extract never calls this. Probe 1's mutant does."""
    parsed = parse_prose(prose)
    last = None
    for token in parsed["dates"]:
        if len(token) == 10:
            last = token + "T00:00:00Z"
            break
        if len(token) == 4:
            last = f"{token}-01-01T00:00:00Z"
    return {
        "last_commit_date": last,
        "archived": parsed["says_archived"],
        "inferred_from_prose": True,
    }


def prose_leaked_into_measured(row: dict) -> bool:
    """True when a NOT-CHECKED row copied discovery prose into measured fields."""
    if str(row.get("status") or "") != "NOT-CHECKED":
        return False
    if row.get("inferred_from_prose") is True:
        return True
    parsed = parse_prose(str(row.get("discovery_prose") or ""))
    measured = row.get("measured") or {}
    for key in ("last_commit_date", "archived", "open_issue_velocity", "latest_release"):
        val = measured.get(key)
        if val not in (None, {}, []):
            if key == "last_commit_date" and parsed["dates"]:
                text = str(val)
                if any(tok in text for tok in parsed["dates"]):
                    return True
            else:
                return True
        top = row.get(key)
        if top not in (None, {}, []) and key != "archived":
            return True
    top_date = row.get("last_commit_date")
    if top_date and parsed["dates"] and any(tok in str(top_date) for tok in parsed["dates"]):
        return True
    return False


def _day(iso: str | None) -> str | None:
    if not iso:
        return None
    try:
        return normalize_iso(iso)[:10]
    except ValueError:
        return str(iso)[:10]


def contradiction_list(prose: str, measured: dict) -> list[dict]:
    parsed = parse_prose(prose)
    out: list[dict] = []
    archived = measured.get("archived")
    last = measured.get("last_commit_date")
    if archived is True and (parsed["says_active"] or parsed["says_not_archived"]):
        out.append(
            {
                "kind": "archived-vs-active-prose",
                "prose": parsed["raw"],
                "measured_archived": True,
            }
        )
    if archived is False and parsed["says_archived"]:
        out.append(
            {
                "kind": "prose-archived-vs-measured-live",
                "prose": parsed["raw"],
                "measured_archived": False,
            }
        )
    if last and parsed["dates"]:
        last_day = _day(last) or ""
        for tok in parsed["dates"]:
            if len(tok) == 10 and tok != last_day:
                out.append(
                    {
                        "kind": "last-commit-date-mismatch",
                        "prose_date": tok,
                        "measured_date": last_day,
                    }
                )
            elif len(tok) == 4 and not last_day.startswith(tok):
                out.append(
                    {
                        "kind": "last-commit-year-mismatch",
                        "prose_year": tok,
                        "measured_date": last_day,
                    }
                )
    return out


def velocity_from_api(api: dict | None) -> dict | None:
    if not isinstance(api, dict):
        return None
    if "issues_opened_last_90d" not in api and "open_issues_count" not in api:
        return None
    opened = int(api.get("issues_opened_last_90d") or 0)
    closed = int(api.get("issues_closed_last_90d") or 0)
    open_count = int(api.get("open_issues_count") or 0)
    return {
        "window_days": WINDOW_DAYS,
        "opened_in_window": opened,
        "closed_in_window": closed,
        "open_count": open_count,
        "opened_per_day": round(opened / float(WINDOW_DAYS), 6),
    }


def extract_one(
    candidate: dict,
    *,
    api: dict | None,
    git_head: dict | None,
    query_date: str = QUERY_DATE,
    allow_prose_inference: bool = False,
) -> dict:
    prose = str(candidate.get("maintenance") or "")
    cid = str(candidate.get("id") or "")
    classification = str(candidate.get("classification") or "")
    base = {
        "candidate_id": cid,
        "name": candidate.get("name"),
        "origin": candidate.get("origin"),
        "classification": classification,
        "discovery_prose": prose,
        "query_date": query_date,
        "inferred_from_prose": False,
        "externally_sourced": is_externally_sourced(candidate),
    }
    if not is_externally_sourced(candidate):
        return {
            **base,
            "status": "SKIPPED-LOCAL",
            "last_commit_date": None,
            "archived": None,
            "open_issue_velocity": None,
            "latest_release": None,
            "measured": {},
            "contradictions": [],
            "disposition_flag": None,
            "freshness_finding": None,
            "evidence_a": None,
            "evidence_b": None,
        }

    if api is None and git_head is None:
        row = {
            **base,
            "status": "NOT-CHECKED",
            "last_commit_date": None,
            "archived": None,
            "open_issue_velocity": None,
            "latest_release": None,
            "measured": {
                "last_commit_date": None,
                "archived": None,
                "open_issue_velocity": None,
                "latest_release": None,
            },
            "contradictions": [],
            "disposition_flag": None,
            "freshness_finding": None,
            "evidence_a": {"reachable": False, "reason": "source-unreachable"},
            "evidence_b": {"reachable": False, "reason": "git-ref-unreachable"},
            "note": "no reachable metadata; discovery-time prose is inadmissible",
        }
        if allow_prose_inference:
            leaked = infer_from_prose(prose)
            row["inferred_from_prose"] = True
            row["last_commit_date"] = leaked["last_commit_date"]
            row["archived"] = leaked["archived"]
            row["measured"] = {
                "last_commit_date": leaked["last_commit_date"],
                "archived": leaked["archived"],
                "open_issue_velocity": None,
                "latest_release": None,
            }
        return row

    api_push = None
    archived = None
    release = None
    evidence_a: dict[str, Any] | None = None
    if isinstance(api, dict):
        raw_push = api.get("pushed_at")
        api_push = normalize_iso(str(raw_push)) if raw_push else None
        archived = bool(api.get("archived")) if "archived" in api else None
        rel = api.get("latest_release")
        if isinstance(rel, dict) and rel.get("published_at"):
            release = {
                "tag_name": rel.get("tag_name"),
                "published_at": normalize_iso(str(rel["published_at"])),
            }
        evidence_a = {
            "reachable": True,
            "last_push": api_push,
            "archived": archived,
            "latest_release": release,
            "query_date": query_date,
            "source": "github-repository-metadata-api",
        }
    else:
        evidence_a = {"reachable": False, "reason": "api-unreachable", "query_date": query_date}

    git_date = None
    evidence_b: dict[str, Any] | None = None
    if isinstance(git_head, dict) and git_head.get("committer_iso"):
        git_date = normalize_iso(str(git_head["committer_iso"]))
        evidence_b = {
            "reachable": True,
            "head_commit_date": git_date,
            "head_sha": git_head.get("sha"),
            "source": "git-ref-HEAD",
        }
    else:
        evidence_b = {"reachable": False, "reason": "git-ref-unreachable"}

    last_commit = git_date or api_push
    last_source = "git-ref-HEAD" if git_date else ("github-api-pushed_at" if api_push else None)
    vel = velocity_from_api(api)

    freshness = None
    if git_date and api_push and _day(git_date) != _day(api_push):
        freshness = {
            "kind": "api-stale-vs-git-head",
            "about": "api",
            "api_last_push": api_push,
            "git_head_date": git_date,
            "note": (
                "Divergence is a freshness finding about the API, "
                "not about the project."
            ),
        }

    measured = {
        "last_commit_date": last_commit,
        "last_commit_source": last_source,
        "archived": archived,
        "open_issue_velocity": vel,
        "latest_release": release,
        "api_last_push": api_push,
        "git_head_date": git_date,
    }
    contradictions = contradiction_list(prose, measured)

    disposition = None
    if archived is True:
        disposition = {
            "flag": "ARCHIVED-UPSTREAM",
            "lane": "disposition",
            "adopt_as_is_risk": classification == "ADOPT-AS-IS",
            "reason": (
                "ADOPT-AS-IS on an archived source is a distinct risk"
                if classification == "ADOPT-AS-IS"
                else "archived upstream flagged for the disposition lane"
            ),
        }

    return {
        **base,
        "status": "MEASURED",
        "last_commit_date": last_commit,
        "archived": archived,
        "open_issue_velocity": vel,
        "latest_release": release,
        "measured": measured,
        "contradictions": contradictions,
        "disposition_flag": disposition,
        "freshness_finding": freshness,
        "evidence_a": evidence_a,
        "evidence_b": evidence_b,
    }


def extract_all(candidates: list[dict], transport) -> dict:
    rows = []
    for cand in candidates:
        api = None
        git_head = None
        rid = repo_id(cand)
        if is_externally_sourced(cand) and rid:
            api = transport.github_repo(rid[0], rid[1])
            git_head = transport.git_head(rid[0], rid[1])
        rows.append(
            extract_one(
                cand,
                api=api,
                git_head=git_head,
                query_date=QUERY_DATE,
                allow_prose_inference=False,
            )
        )
    return summarize(rows, transport)


def summarize(rows: list[dict], transport) -> dict:
    measured = [r for r in rows if r.get("status") == "MEASURED"]
    not_checked = [r for r in rows if r.get("status") == "NOT-CHECKED"]
    skipped = [r for r in rows if r.get("status") == "SKIPPED-LOCAL"]
    contradictions = []
    for r in rows:
        for item in r.get("contradictions") or []:
            contradictions.append({"candidate_id": r["candidate_id"], **item})
    disposition = [
        {
            "candidate_id": r["candidate_id"],
            "classification": r.get("classification"),
            **(r.get("disposition_flag") or {}),
        }
        for r in rows
        if r.get("disposition_flag")
    ]
    freshness = [
        {"candidate_id": r["candidate_id"], **(r.get("freshness_finding") or {})}
        for r in rows
        if r.get("freshness_finding")
    ]
    leaked = [r["candidate_id"] for r in not_checked if prose_leaked_into_measured(r)]
    sched_log = list(getattr(getattr(transport, "scheduler", None), "log", []) or [])
    return {
        "query_date": QUERY_DATE,
        "rows": rows,
        "n_candidates": len(rows),
        "n_measured": len(measured),
        "n_not_checked": len(not_checked),
        "n_skipped_local": len(skipped),
        "not_checked_ids": [r["candidate_id"] for r in not_checked],
        "contradictions": contradictions,
        "disposition_flags": disposition,
        "freshness_findings": freshness,
        "prose_leak_ids": leaked,
        "scheduler_log": sched_log,
        "pass": (
            len(leaked) == 0
            and any(r["candidate_id"] == "wf-ext-unreachable" and r["status"] == "NOT-CHECKED" for r in rows)
            and any(
                (r.get("disposition_flag") or {}).get("adopt_as_is_risk") is True
                for r in rows
                if r["candidate_id"] == "wf-ext-archived-adopt"
            )
            and any(
                r["candidate_id"] == "wf-ext-live-active"
                and r.get("archived") is False
                and r.get("disposition_flag") is None
                for r in rows
            )
        ),
    }


def mutant_infer_unreachable(candidates: list[dict], transport) -> dict:
    """Negative control: copy prose into the unreachable row."""
    rows = []
    for cand in candidates:
        api = None
        git_head = None
        rid = repo_id(cand)
        if is_externally_sourced(cand) and rid:
            api = transport.github_repo(rid[0], rid[1])
            git_head = transport.git_head(rid[0], rid[1])
        rows.append(
            extract_one(
                cand,
                api=api,
                git_head=git_head,
                query_date=QUERY_DATE,
                allow_prose_inference=cand.get("id") == "wf-ext-unreachable",
            )
        )
    return summarize(rows, transport)


def mutant_drop_archived_flag(result: dict) -> dict:
    """Negative control: drop disposition on archived ADOPT-AS-IS."""
    import copy

    cloned = copy.deepcopy(result)
    for r in cloned["rows"]:
        if r.get("candidate_id") == "wf-ext-archived-adopt":
            r["disposition_flag"] = None
            r["archived"] = False
    cloned["disposition_flags"] = [
        d for d in cloned["disposition_flags"] if d.get("candidate_id") != "wf-ext-archived-adopt"
    ]
    cloned["pass"] = False
    return cloned


def archived_adopt_risk_present(result: dict) -> bool:
    for r in result.get("rows") or []:
        flag = r.get("disposition_flag") or {}
        if r.get("candidate_id") == "wf-ext-archived-adopt" and flag.get("adopt_as_is_risk") is True:
            return True
    return False


def live_active_not_flagged(result: dict) -> bool:
    for r in result.get("rows") or []:
        if r.get("candidate_id") == "wf-ext-live-active":
            return r.get("archived") is False and r.get("disposition_flag") is None
    return False
