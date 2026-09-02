"""AUD-0044 shared detectors: required vs produced check-context comparator.

Does not author command-center/schema/audit-drift.schema.json (no ADV rebuild).
GitHub REST is used only when the unauthenticated quota still has remaining
calls; HTML + raw.githubusercontent.com are the live fallbacks that re-run
without that quota.
"""
from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

import yaml

OWNER = "Prekzursil"
REPO = "agent-skills-toolchain"
GH = f"https://github.com/{OWNER}/{REPO}"
RAW = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/main"
API = f"https://api.github.com/repos/{OWNER}/{REPO}"
UA = "AUD-0044-ast-integrate-probe (+https://github.com/Prekzursil/agent-skills-toolchain)"
SSL = ssl.create_default_context()

JOB_NAME_HTML = re.compile(
    r'data-target="streaming-graph-job\.name">\s*([^<]+?)\s*</span>',
    re.I,
)
PR_FROM_TITLE = re.compile(r"\(#(\d+)\)")
WORKFLOW_YML = re.compile(r'"name":"([^"]+\.ya?ml)"')


def fetch(url: str, accept: str = "*/*", limit: int = 4_000_000) -> dict[str, Any]:
    """GET url. Never logs Authorization headers or token values."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    host = urlparse(url).netloc
    try:
        with urllib.request.urlopen(req, timeout=40, context=SSL) as resp:
            raw = resp.read(limit)
            return {
                "ok": True,
                "status": int(resp.status),
                "url": resp.geturl(),
                "host": host,
                "content_type": resp.headers.get("Content-Type"),
                "rate_remaining": resp.headers.get("X-RateLimit-Remaining"),
                "body": raw,
            }
    except urllib.error.HTTPError as exc:
        blob = exc.read(800)
        return {
            "ok": False,
            "status": int(exc.code),
            "url": url,
            "host": host,
            "content_type": exc.headers.get("Content-Type") if exc.headers else None,
            "rate_remaining": exc.headers.get("X-RateLimit-Remaining")
            if exc.headers
            else None,
            "rate_reset": exc.headers.get("X-RateLimit-Reset") if exc.headers else None,
            "body": blob,
            "error": f"HTTP {exc.code}",
        }
    except Exception as exc:  # noqa: BLE001 — probe must record transport failure
        return {
            "ok": False,
            "status": 0,
            "url": url,
            "host": host,
            "body": b"",
            "error": f"{type(exc).__name__}",
        }


def text_of(result: dict[str, Any], encoding: str = "utf-8") -> str:
    body = result.get("body") or b""
    if isinstance(body, bytes):
        return body.decode(encoding, "replace")
    return str(body)


def load_yaml(text: str) -> Any:
    return yaml.safe_load(text)


def workflow_check_names(doc: Any) -> list[str]:
    """GitHub check context for a job is job.name if set, else the job id."""
    if not isinstance(doc, dict):
        return []
    jobs = doc.get("jobs")
    if not isinstance(jobs, dict):
        return []
    names: list[str] = []
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        label = job.get("name")
        if isinstance(label, str) and label.strip():
            names.append(label.strip())
        else:
            names.append(str(job_id))
    return names


def compare(required: set[str], produced: set[str]) -> dict[str, Any]:
    req = {s for s in required if s}
    prod = {s for s in produced if s}
    only_req = sorted(req - prod)
    only_prod = sorted(prod - req)
    both = sorted(req & prod)
    return {
        "required_count": len(req),
        "produced_count": len(prod),
        "both_count": len(both),
        "required_not_produced": only_req,
        "produced_not_required": only_prod,
        "intersection": both,
        "symmetric_difference": sorted(set(only_req) | set(only_prod)),
        "symmetric_difference_count": len(only_req) + len(only_prod),
        "disagree": bool(only_req or only_prod),
    }


def rename_control() -> dict[str, Any]:
    """Scratch workflow: renaming one required job must yield a nonempty symdiff."""
    good = """
name: scratch-good
on: [push]
jobs:
  alpha:
    name: gate-alpha
    runs-on: ubuntu-latest
    steps: [{run: echo good}]
  beta:
    name: gate-beta
    runs-on: ubuntu-latest
    steps: [{run: echo good}]
"""
    renamed = """
name: scratch-renamed
on: [push]
jobs:
  alpha:
    name: gate-alpha
    runs-on: ubuntu-latest
    steps: [{run: echo good}]
  beta:
    name: gate-beta-RENAMED
    runs-on: ubuntu-latest
    steps: [{run: echo mutated}]
"""
    required = {"gate-alpha", "gate-beta"}
    good_names = set(workflow_check_names(load_yaml(good)))
    bad_names = set(workflow_check_names(load_yaml(renamed)))
    silent = compare(required, good_names)
    fired = compare(required, bad_names)
    ok = (not silent["disagree"]) and fired["disagree"] and "gate-beta-RENAMED" in fired[
        "produced_not_required"
    ]
    return {
        "id": "AUD0044-C1-renamed-job",
        "kind": "known-broken-fixture",
        "description": (
            "Comparator must stay silent when scratch job names match the required "
            "set, and must report a nonempty symmetric difference after one required "
            "job is renamed. An always-empty comparator would hide a permanently "
            "pending required context."
        ),
        "fired_on_bad_state": fired["disagree"],
        "silent_on_good_state": not silent["disagree"],
        "discriminates": ok,
        "good": silent,
        "bad": fired,
        "good_names": sorted(good_names),
        "bad_names": sorted(bad_names),
        "required": sorted(required),
    }


def parse_required_from_rules_payload(payload: Any) -> list[str]:
    contexts: list[str] = []

    def add(ctx: str) -> None:
        ctx = (ctx or "").strip()
        if ctx and ctx not in contexts:
            contexts.append(ctx)

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            rsc = node.get("required_status_checks")
            if isinstance(rsc, dict):
                for ctx in rsc.get("contexts") or []:
                    if isinstance(ctx, str):
                        add(ctx)
                for chk in rsc.get("checks") or []:
                    if isinstance(chk, dict) and isinstance(chk.get("context"), str):
                        add(chk["context"])
            params = node.get("parameters")
            if isinstance(params, dict):
                checks = params.get("required_status_checks")
                if isinstance(checks, list):
                    for chk in checks:
                        if isinstance(chk, dict) and isinstance(chk.get("context"), str):
                            add(chk["context"])
                        elif isinstance(chk, str):
                            add(chk)
            ctx = node.get("context")
            if isinstance(ctx, str) and node.get("type") in (
                None,
                "required_status_checks",
            ):
                add(ctx)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return contexts


def api_rate_remaining() -> dict[str, Any]:
    r = fetch("https://api.github.com/rate_limit", accept="application/vnd.github+json")
    out: dict[str, Any] = {
        "ok": r["ok"],
        "status": r["status"],
        "remaining": None,
        "limit": None,
        "reset": None,
    }
    if not r["ok"]:
        out["error"] = r.get("error")
        return out
    try:
        data = json.loads(text_of(r))
        core = (data.get("resources") or {}).get("core") or data.get("rate") or {}
        out["remaining"] = core.get("remaining")
        out["limit"] = core.get("limit")
        out["reset"] = core.get("reset")
    except json.JSONDecodeError as exc:
        out["error"] = f"rate_limit-unparseable:{exc}"
    return out


def try_ruleset_api() -> dict[str, Any]:
    """Probe 1 primary: ruleset required_status_checks from the GitHub API."""
    quota = api_rate_remaining()
    remaining = quota.get("remaining")
    result: dict[str, Any] = {
        "quota": quota,
        "attempted": False,
        "contexts": [],
        "endpoints": [],
        "source": "api-not-attempted",
    }
    if remaining is None:
        result["source"] = "api-quota-unknown"
        return result
    if int(remaining) < 2:
        result["source"] = "api-rate-limited"
        result["skip_reason"] = f"unauthenticated remaining={remaining} need>=2"
        return result

    endpoints = [
        f"{API}/rules/branches/main",
        f"{API}/rulesets",
        f"{API}/branches/main/protection",
    ]
    result["attempted"] = True
    bodies: list[Any] = []
    for url in endpoints:
        r = fetch(url, accept="application/vnd.github+json")
        entry = {
            "url": url.replace("https://api.github.com", ""),
            "status": r["status"],
            "ok": r["ok"],
        }
        if r["ok"]:
            try:
                parsed = json.loads(text_of(r))
            except json.JSONDecodeError:
                parsed = None
                entry["parse"] = "fail"
            entry["parse"] = "ok" if parsed is not None else "fail"
            if parsed is not None:
                bodies.append(parsed)
                found = parse_required_from_rules_payload(parsed)
                entry["contexts"] = found
        else:
            entry["error"] = r.get("error")
        result["endpoints"].append(entry)
        if entry.get("contexts"):
            break

    merged: list[str] = []
    for body in bodies:
        for ctx in parse_required_from_rules_payload(body):
            if ctx not in merged:
                merged.append(ctx)
    result["contexts"] = merged
    result["source"] = "api" if merged else "api-empty-or-unreadable"
    return result


def fetch_automation_md() -> dict[str, Any]:
    r = fetch(f"{RAW}/.github/AUTOMATION.md", accept="text/plain")
    text = text_of(r) if r["ok"] else ""
    seven = bool(
        re.search(
            r"lists the 7 [`']quality[`'] jobs as\s+[`']?required_status_checks",
            text,
            re.I,
        )
    )
    return {
        "ok": r["ok"],
        "status": r["status"],
        "bytes": len(r.get("body") or b""),
        "documents_seven_quality_required": seven,
        "excerpt": (
            "the branch ruleset on main that lists the 7 quality jobs as "
            "required_status_checks"
            if seven
            else text[:400]
        ),
    }


def list_workflow_files() -> dict[str, Any]:
    r = fetch(f"{GH}/tree/main/.github/workflows", accept="text/html")
    names = sorted(set(WORKFLOW_YML.findall(text_of(r))))
    return {
        "ok": r["ok"],
        "status": r["status"],
        "files": names,
        "count": len(names),
    }


def fetch_workflow_yaml(filename: str) -> dict[str, Any]:
    r = fetch(f"{RAW}/.github/workflows/{filename}", accept="text/plain")
    names: list[str] = []
    parse_err = None
    if r["ok"]:
        try:
            names = workflow_check_names(load_yaml(text_of(r)))
        except Exception as exc:  # noqa: BLE001
            parse_err = f"{type(exc).__name__}"
    return {
        "file": f".github/workflows/{filename}",
        "ok": r["ok"],
        "status": r["status"],
        "bytes": len(r.get("body") or b""),
        "check_names": names,
        "parse_error": parse_err,
    }


def latest_commit_atom() -> dict[str, Any]:
    r = fetch(f"{GH}/commits/main.atom", accept="application/atom+xml")
    text = text_of(r)
    sha = None
    title = None
    pr = None
    m = re.search(r"commit/([0-9a-f]{40})", text)
    if m:
        sha = m.group(1)
    tm = re.search(r"<title>\s*([^<]+?)\s*</title>", text)
    # first <title> is the feed title; entries follow
    titles = re.findall(r"<title>\s*([^<]+?)\s*</title>", text)
    if len(titles) >= 2:
        title = re.sub(r"\s+", " ", titles[1]).strip()
        pm = PR_FROM_TITLE.search(title)
        if pm:
            pr = int(pm.group(1))
    return {
        "ok": r["ok"],
        "status": r["status"],
        "sha": sha,
        "title": title,
        "merged_pr": pr,
    }


def quality_workflow_runs() -> dict[str, Any]:
    r = fetch(f"{GH}/actions/workflows/quality.yml", accept="text/html")
    runs = re.findall(r"/actions/runs/(\d+)", text_of(r))
    # preserve order of first appearance (newest first on the page)
    seen: list[str] = []
    for rid in runs:
        if rid not in seen:
            seen.append(rid)
    return {"ok": r["ok"], "status": r["status"], "run_ids": seen[:8]}


def job_ids_for_run(run_id: str) -> dict[str, Any]:
    r = fetch(f"{GH}/actions/runs/{run_id}", accept="text/html")
    jobs = []
    for jid in re.findall(rf"/actions/runs/{run_id}/job/(\d+)", text_of(r)):
        if jid not in jobs:
            jobs.append(jid)
    title_m = re.search(r"<title>([^<]+)</title>", text_of(r))
    return {
        "ok": r["ok"],
        "status": r["status"],
        "run_id": run_id,
        "title": title_m.group(1).strip() if title_m else None,
        "job_ids": jobs,
    }


def job_display_name(run_id: str, job_id: str) -> dict[str, Any]:
    r = fetch(f"{GH}/actions/runs/{run_id}/job/{job_id}", accept="text/html")
    html = text_of(r)
    names = [n.strip() for n in JOB_NAME_HTML.findall(html) if n.strip()]
    name = names[0] if names else None
    return {
        "ok": r["ok"],
        "status": r["status"],
        "job_id": job_id,
        "name": name,
        "name_hits": names[:4],
    }


def produced_from_all_workflows() -> dict[str, Any]:
    listing = list_workflow_files()
    files = listing.get("files") or []
    rows = [fetch_workflow_yaml(name) for name in files]
    names: list[str] = []
    for row in rows:
        for n in row.get("check_names") or []:
            if n not in names:
                names.append(n)
    return {
        "listing": listing,
        "workflows": [
            {
                "file": row["file"],
                "ok": row["ok"],
                "status": row["status"],
                "check_names": row["check_names"],
                "parse_error": row["parse_error"],
            }
            for row in rows
        ],
        "check_names": names,
    }
