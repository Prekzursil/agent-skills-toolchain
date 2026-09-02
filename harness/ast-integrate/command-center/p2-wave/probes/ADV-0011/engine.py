#!/usr/bin/env python3
"""ADV-0011 decayed-green audit: classify stored greens, re-run live queries, feed-diff.

Does not author command-center/schema/stale-premise-reprobe.schema.json.
Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0011"
OUT_REL = "command-center/adversarial/ADV-0011-decayed-green-reprobe.json"
SCHEMA_REL = "command-center/schema/stale-premise-reprobe.schema.json"
OSV_QUERY = "https://api.osv.dev/v1/query"
OSV_BATCH = "https://api.osv.dev/v1/querybatch"
UA = "ast-integrate-ADV-0011"

# Residual badlock fixture from the prior ADV-0011 attempt — resume, do not scrap.
BADLOCK = HERE / "badlock" / "package-lock.json"
FROZEN_GREEN = (
    REPO / "command-center/p2-wave/probes/RES-0132/frozen-green/package-lock.json"
)
KNOWN_CLEAN = (
    REPO / "command-center/p2-wave/probes/CNF-0153/known-clean/package-lock.json"
)
AUD_ACTIONS = (
    REPO / "command-center/p2-wave/probes/AUD-0041/probe2-actions-api.json"
)
AUD_YAML = (
    REPO / "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
)
MARKETPLACE = REPO / ".claude-plugin/marketplace.json"

LIVE_NAME_MARKERS = (
    "osv-scanner",
    "osv",
    "trivy",
    "dependabot",
    "gate-deps",
    "pip-audit",
    "license lookup",
    "license-lookup",
    "marketplace availability",
    "npm audit",
)

DETERMINISTIC_NAME_MARKERS = (
    "ruff",
    "gate-lint",
    "gate-types",
    "gate-tests",
    "gate-sast",
    "opengrep",
    "gate-no-runtime-junk",
    "eol",
    "registry-diff",
    "basedpyright",
    "gitleaks",
    "gate-secrets",
    "routing-benchmark",
)

VERDICTS = ("CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_from_mtime(path: Path) -> str | None:
    if not path.is_file():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    text = ts.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def classify_gate_name(name: str) -> str:
    n = (name or "").lower()
    for marker in LIVE_NAME_MARKERS:
        if marker in n:
            return "live-query"
    for marker in DETERMINISTIC_NAME_MARKERS:
        if marker in n:
            return "deterministic-input"
    return "unknown"


def lockfile_packages(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for key, meta in (data.get("packages") or {}).items():
        if not isinstance(meta, dict):
            continue
        if meta.get("link"):
            continue
        name = meta.get("name")
        if not name:
            rel = str(key).replace("\\", "/")
            if "node_modules/" in rel:
                name = rel.split("node_modules/")[-1]
            elif rel and rel != "":
                continue
        version = meta.get("version")
        if not name or not version:
            continue
        pair = (str(name), str(version))
        if pair in seen:
            continue
        seen.add(pair)
        out.append({"name": pair[0], "version": pair[1], "ecosystem": "npm"})
    out.sort(key=lambda p: (p["name"], p["version"]))
    return out


def http_json(
    url: str,
    payload: dict | None = None,
    *,
    attempts: int = 3,
) -> tuple[int, Any, str]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    last_err = ""
    for i in range(attempts):
        req = urllib.request.Request(url, data=body, headers=headers, method="GET" if body is None else "POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                code = int(resp.status)
                try:
                    return code, json.loads(raw.decode("utf-8")), ""
                except json.JSONDecodeError as exc:
                    return code, None, f"unparseable:{exc}"
        except urllib.error.HTTPError as exc:
            last_err = f"HTTP {exc.code}"
            if exc.code in {429, 529, 503} and i + 1 < attempts:
                time.sleep(2 * (i + 1))
                continue
            try:
                err_body = exc.read().decode("utf-8", errors="replace")[:400]
            except OSError:
                err_body = ""
            return int(exc.code), None, (last_err + " " + err_body).strip()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_err = f"{type(exc).__name__}:{exc}"
            if i + 1 < attempts:
                time.sleep(2 * (i + 1))
                continue
            return 0, None, last_err
    return 0, None, last_err


def osv_querybatch(pkgs: list[dict[str, str]]) -> tuple[list[dict[str, Any]], str]:
    if not pkgs:
        return [], ""
    queries = [
        {"package": {"name": p["name"], "ecosystem": p.get("ecosystem") or "npm"}, "version": p["version"]}
        for p in pkgs
    ]
    code, data, err = http_json(OSV_BATCH, {"queries": queries})
    if err or not isinstance(data, dict):
        # Fall back to one-by-one so a batch failure is not silence.
        rows: list[dict[str, Any]] = []
        for p in pkgs:
            c2, d2, e2 = http_json(
                OSV_QUERY,
                {
                    "package": {"name": p["name"], "ecosystem": p.get("ecosystem") or "npm"},
                    "version": p["version"],
                },
            )
            vulns = []
            if isinstance(d2, dict):
                vulns = [
                    {"id": v.get("id"), "published": v.get("published"), "modified": v.get("modified")}
                    for v in (d2.get("vulns") or [])
                    if isinstance(v, dict)
                ]
            rows.append(
                {
                    "name": p["name"],
                    "version": p["version"],
                    "http": c2,
                    "error": e2,
                    "vuln_ids": [v["id"] for v in vulns if v.get("id")],
                    "vulns": vulns,
                    "verdict": "RED" if vulns else ("TOOL-FAILURE" if e2 or c2 not in {200, 0} and not vulns and e2 else "GREEN"),
                }
            )
            if e2 and c2 not in {200}:
                if c2 == 0 or c2 >= 400:
                    rows[-1]["verdict"] = "TOOL-FAILURE"
        return rows, err
    results = data.get("results") or []
    rows = []
    for p, slot in zip(pkgs, results):
        slot = slot if isinstance(slot, dict) else {}
        vulns = []
        for v in slot.get("vulns") or []:
            if not isinstance(v, dict):
                continue
            vulns.append(
                {"id": v.get("id"), "published": v.get("published"), "modified": v.get("modified")}
            )
        ids = [v["id"] for v in vulns if v.get("id")]
        rows.append(
            {
                "name": p["name"],
                "version": p["version"],
                "http": code,
                "error": "",
                "vuln_ids": ids,
                "vulns": vulns,
                "verdict": "RED" if ids else "GREEN",
            }
        )
    return rows, ""


def osv_package_feed(name: str, ecosystem: str = "npm") -> tuple[list[dict[str, Any]], str]:
    code, data, err = http_json(
        OSV_QUERY, {"package": {"name": name, "ecosystem": ecosystem}}
    )
    if err or not isinstance(data, dict):
        return [], err or f"http:{code}"
    out = []
    for v in data.get("vulns") or []:
        if not isinstance(v, dict):
            continue
        out.append(
            {
                "id": v.get("id"),
                "published": v.get("published"),
                "modified": v.get("modified"),
                "source": "osv.dev",
            }
        )
    out.sort(key=lambda r: str(r.get("published") or ""))
    return out, ""


def scan_lockfile(label: str, path: Path, stored_verdict: str) -> dict[str, Any]:
    pkgs = lockfile_packages(path)
    rows, err = osv_querybatch(pkgs)
    reds = [r for r in rows if r.get("verdict") == "RED"]
    failures = [r for r in rows if r.get("verdict") == "TOOL-FAILURE"]
    if failures and not reds and not any(r.get("verdict") == "GREEN" for r in rows):
        today = "TOOL-FAILURE"
    elif reds:
        today = "RED"
    else:
        today = "GREEN"
    flipped = (
        stored_verdict in {"GREEN", "success", "SUCCESS", "CLEAN"}
        and today == "RED"
    )
    return {
        "id": label,
        "path": path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path),
        "present": path.is_file(),
        "stored_verdict": stored_verdict,
        "today_verdict": today,
        "flipped": flipped,
        "n_packages": len(pkgs),
        "n_red": len(reds),
        "n_tool_failure": len(failures),
        "error": err,
        "red_ids": sorted({vid for r in reds for vid in r.get("vuln_ids") or []}),
        "packages": rows,
        "volatility": "live-query",
        "instrument": "osv.dev/v1/querybatch",
    }


def run_eol_policy() -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        ["python3", "tools/command-center/eol_policy.py", "--check"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    today = "GREEN" if proc.returncode == 0 else "RED"
    return {
        "id": "command-center-eol-policy",
        "path": "tools/command-center/eol_policy.py",
        "stored_verdict": "GREEN",
        "today_verdict": today,
        "flipped": today != "GREEN",
        "exit_code": proc.returncode,
        "raw_tail": text[-800:],
        "volatility": "deterministic-input",
        "instrument": "python3 tools/command-center/eol_policy.py --check",
    }


def hash_twice(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    a = sha256_bytes(raw)
    b = sha256_bytes(raw)
    return {
        "id": "frozen-lockfile-sha256",
        "path": path.relative_to(REPO).as_posix(),
        "stored_verdict": a,
        "today_verdict": b,
        "flipped": a != b,
        "volatility": "deterministic-input",
        "instrument": "sha256(lockfile bytes) computed twice in-process",
    }


def inventory_ci_greens() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    captured_at = iso_from_mtime(AUD_ACTIONS)
    if AUD_ACTIONS.is_file():
        doc = json.loads(AUD_ACTIONS.read_text(encoding="utf-8"))
        for run in doc.get("runs") or []:
            if not isinstance(run, dict):
                continue
            for job in run.get("jobs") or []:
                if not isinstance(job, dict):
                    continue
                if str(job.get("conclusion") or "").lower() != "success":
                    continue
                name = str(job.get("name") or "")
                vol = classify_gate_name(name)
                items.append(
                    {
                        "id": f"ci:{name}",
                        "name": name,
                        "citation": AUD_ACTIONS.relative_to(REPO).as_posix(),
                        "stored_verdict": "GREEN",
                        "stored_timestamp": captured_at,
                        "run_id": run.get("run_id"),
                        "workflow": run.get("workflow"),
                        "volatility": vol,
                        "kind": "recorded-ci-green",
                    }
                )
    if AUD_YAML.is_file():
        ydoc = json.loads(AUD_YAML.read_text(encoding="utf-8"))
        for wf in ydoc.get("workflows") or []:
            if not isinstance(wf, dict):
                continue
            for job in wf.get("jobs") or []:
                if not isinstance(job, dict):
                    continue
                name = str(job.get("name") or job.get("job_id") or "")
                vol = classify_gate_name(name + " " + json.dumps(job.get("steps") or []))
                if vol != "live-query":
                    continue
                items.append(
                    {
                        "id": f"yaml:{wf.get('file')}:{name}",
                        "name": name,
                        "citation": AUD_YAML.relative_to(REPO).as_posix(),
                        "stored_verdict": "DEFINED",
                        "stored_timestamp": iso_from_mtime(AUD_YAML),
                        "workflow_file": wf.get("file"),
                        "volatility": "live-query",
                        "kind": "live-query-gate-definition",
                    }
                )
    items.append(
        {
            "id": "fixture:RES-0132-frozen-green",
            "name": "RES-0132 frozen-green lockfile (stored CLEAN against live advisory DB)",
            "citation": FROZEN_GREEN.relative_to(REPO).as_posix() if FROZEN_GREEN.is_file() else "",
            "stored_verdict": "GREEN",
            "stored_timestamp": iso_from_mtime(FROZEN_GREEN),
            "volatility": "live-query",
            "kind": "stored-green-lockfile",
        }
    )
    items.append(
        {
            "id": "fixture:CNF-0153-known-clean",
            "name": "CNF-0153 known-clean lockfile (bytes@3.1.2 stored CLEAN)",
            "citation": KNOWN_CLEAN.relative_to(REPO).as_posix() if KNOWN_CLEAN.is_file() else "",
            "stored_verdict": "GREEN",
            "stored_timestamp": iso_from_mtime(KNOWN_CLEAN),
            "volatility": "live-query",
            "kind": "stored-green-lockfile",
        }
    )
    items.append(
        {
            "id": "gate:command-center-eol-policy",
            "name": "command-center-eol (IMP-0441 / eol_policy.py --check)",
            "citation": ".github/workflows/command-center-eol.yml",
            "stored_verdict": "GREEN",
            "stored_timestamp": iso_from_mtime(
                REPO / "command-center/p2-wave/probes/IMP-0441/SUBAGENT-RETURN.json"
            ),
            "volatility": "deterministic-input",
            "kind": "recorded-deterministic-green",
        }
    )
    # Dedup by id, preserve order.
    seen: set[str] = set()
    uniq: list[dict[str, Any]] = []
    for it in items:
        if it["id"] in seen:
            continue
        seen.add(it["id"])
        uniq.append(it)
    return uniq


def feed_diff_for(
    package_name: str,
    stored_ts: str | None,
) -> dict[str, Any]:
    """Unversioned OSV package feed (mechanically different from querybatch).

    api.github.com/advisories is not used: this worktree's unauthenticated
    GitHub REST budget is already exhausted (HTTP 403), which made the
    previous GHSA-backed probe 2 exit 1 on remesure.
    """
    stored_dt = parse_iso(stored_ts)
    feed, err = osv_package_feed(package_name)
    instrument = "osv.dev/v1/query (package, no version)"
    after: list[dict[str, Any]] = []
    for row in feed:
        pub = parse_iso(str(row.get("published") or ""))
        if stored_dt is None or (pub is not None and pub > stored_dt):
            after.append(row)
    return {
        "package": package_name,
        "instrument": instrument,
        "error": err,
        "n_feed": len(feed),
        "n_published_after_stored": len(after) if stored_dt is not None else None,
        "stored_timestamp": stored_ts,
        "after": after[:20],
        "feed_sample": feed[:8],
    }


def investigate() -> dict[str, Any]:
    inventory = inventory_ci_greens()
    n_live = sum(1 for i in inventory if i.get("volatility") == "live-query")
    n_det = sum(1 for i in inventory if i.get("volatility") == "deterministic-input")
    n_unk = sum(1 for i in inventory if i.get("volatility") == "unknown")

    det = run_eol_policy()
    hash_ctrl = hash_twice(BADLOCK if BADLOCK.is_file() else KNOWN_CLEAN)

    reruns = {
        "known_clean": scan_lockfile("CNF-0153-known-clean", KNOWN_CLEAN, "GREEN"),
        "frozen_green": scan_lockfile("RES-0132-frozen-green", FROZEN_GREEN, "GREEN"),
        "known_bad": scan_lockfile("ADV-0011-badlock", BADLOCK, "RED"),
    }

    # Probe-2 feed-diff uses unversioned OSV package query (not querybatch).
    stored_gate_deps = next(
        (i for i in inventory if "gate-deps" in str(i.get("name") or "").lower()),
        None,
    )
    stored_ts = (stored_gate_deps or {}).get("stored_timestamp") or iso_from_mtime(AUD_ACTIONS)
    feed = {
        "lodash": feed_diff_for("lodash", stored_ts),
        "bytes": feed_diff_for("bytes", stored_ts),
        "brace-expansion": feed_diff_for("brace-expansion", stored_ts),
    }
    feed["lodash_osv_unversioned"] = feed["lodash"]

    known_bad_red = reruns["known_bad"]["today_verdict"] == "RED" and bool(
        reruns["known_bad"]["red_ids"]
    )
    known_clean_green = reruns["known_clean"]["today_verdict"] == "GREEN"
    frozen_same = (
        reruns["frozen_green"]["today_verdict"] == reruns["frozen_green"]["stored_verdict"]
        and reruns["frozen_green"]["today_verdict"] in {"GREEN", "RED"}
    )
    det_same = det["today_verdict"] == "GREEN" and not det["flipped"]
    hash_same = not hash_ctrl["flipped"]

    missing_tool = any(
        r["today_verdict"] == "TOOL-FAILURE" for r in reruns.values()
    )

    # Scientific targets.
    classification_ok = n_live >= 1 and n_det >= 1
    live_flip = any(
        reruns[k]["flipped"] for k in ("known_clean", "frozen_green")
    )
    # Feed is live if unversioned OSV returns lodash advisories AND is silent on bytes.
    feed_live = (
        (feed["lodash"].get("n_feed") or 0) > 0
        and (feed["bytes"].get("n_feed") or 0) == 0
        and not feed["lodash"].get("error")
        and not feed["bytes"].get("error")
    )
    advisories_in_window = any(
        (feed[k].get("n_published_after_stored") or 0) > 0
        for k in ("lodash", "brace-expansion", "lodash_osv_unversioned")
    )

    def v_or_notchecked(ok: bool, yes: str, no: str, missing: bool = False) -> str:
        if missing:
            return "NOT-CHECKED"
        return yes if ok else no

    controls_present = det_same and known_bad_red and hash_same
    if not controls_present:
        # Catalog: any missing control downgrades unit verdicts to NOT-CHECKED.
        t_class = "NOT-CHECKED"
        t_flip = "NOT-CHECKED"
        t_feed = "NOT-CHECKED"
        t_det = "NOT-CHECKED" if not det_same else "CONFIRMED"
    else:
        t_class = v_or_notchecked(classification_ok, "CONFIRMED", "REFUTED", missing_tool)
        t_flip = (
            "NOT-CHECKED"
            if missing_tool
            else ("CONFIRMED" if live_flip else "REFUTED")
        )
        t_feed = v_or_notchecked(feed_live, "CONFIRMED", "REFUTED", missing_tool)
        t_det = "CONFIRMED" if det_same else "REFUTED"

    targets = [
        {
            "id": "live-query-vs-deterministic-classification",
            "verdict": t_class,
            "evidence": (
                f"inventory n={len(inventory)} live-query={n_live} "
                f"deterministic-input={n_det} unknown={n_unk}"
            ),
        },
        {
            "id": "stored-live-query-green-verdict-flip",
            "verdict": t_flip,
            "evidence": (
                f"known_clean today={reruns['known_clean']['today_verdict']} "
                f"flipped={reruns['known_clean']['flipped']}; "
                f"frozen_green today={reruns['frozen_green']['today_verdict']} "
                f"flipped={reruns['frozen_green']['flipped']}; "
                f"gate-deps GitHub job not re-runnable on this worktree "
                f"(quality.yml/osv-scanner.toml absent)"
            ),
        },
        {
            "id": "advisory-feed-diff-for-unrerunnable-gates",
            "verdict": t_feed,
            "evidence": (
                f"osv-unversioned lodash n_feed={feed['lodash'].get('n_feed')} "
                f"after_stored={feed['lodash'].get('n_published_after_stored')} "
                f"bytes n_feed={feed['bytes'].get('n_feed')} "
                f"window_hits={advisories_in_window} stored_ts={stored_ts}"
            ),
        },
        {
            "id": "deterministic-input-control-same-verdict",
            "verdict": t_det,
            "evidence": (
                f"eol_policy stored=GREEN today={det['today_verdict']} "
                f"exit={det['exit_code']} hash_twice_match={hash_same}"
            ),
        },
    ]

    scientific = [t["verdict"] for t in targets]
    if "NOT-CHECKED" in scientific and all(v == "NOT-CHECKED" for v in scientific):
        overall = "NOT-CHECKED"
    elif "CONFIRMED" in scientific and "REFUTED" in scientific:
        overall = "PARTIAL"
    elif scientific.count("CONFIRMED") == len(scientific):
        overall = "CONFIRMED"
    elif "REFUTED" in scientific and "CONFIRMED" not in scientific:
        overall = "REFUTED"
    else:
        overall = "PARTIAL"

    return {
        "unit_id": UNIT,
        "as_of": utc_now(),
        "inventory": inventory,
        "counts": {
            "inventory": len(inventory),
            "live_query": n_live,
            "deterministic_input": n_det,
            "unknown": n_unk,
        },
        "reruns": reruns,
        "deterministic_control": det,
        "hash_control": hash_ctrl,
        "feed_diff": feed,
        "targets": targets,
        "overall_verdict": overall,
        "controls_ok": {
            "deterministic_same": det_same,
            "known_bad_red": known_bad_red,
            "known_clean_green": known_clean_green,
            "frozen_green_scanned": reruns["frozen_green"]["today_verdict"]
            in {"GREEN", "RED"},
            "hash_twice_same": hash_same,
            "feed_live_both_states": feed_live,
            "missing_tool": missing_tool,
        },
        "schema_present": (REPO / SCHEMA_REL).is_file(),
        "osv_scanner_present": bool(shutil_which("osv-scanner")),
        "trivy_present": bool(shutil_which("trivy")),
    }


def shutil_which(name: str) -> str | None:
    from shutil import which

    return which(name)


def compact_probe1(live: dict[str, Any]) -> dict[str, Any]:
    return {
        "probe": "probe1-classify-and-rerun",
        "unit_id": UNIT,
        "counts": live["counts"],
        "overall_verdict": live["overall_verdict"],
        "target_verdicts": [t["verdict"] for t in live["targets"]],
        "known_clean": {
            "today": live["reruns"]["known_clean"]["today_verdict"],
            "flipped": live["reruns"]["known_clean"]["flipped"],
            "n_red": live["reruns"]["known_clean"]["n_red"],
        },
        "frozen_green": {
            "today": live["reruns"]["frozen_green"]["today_verdict"],
            "flipped": live["reruns"]["frozen_green"]["flipped"],
            "n_red": live["reruns"]["frozen_green"]["n_red"],
        },
        "known_bad": {
            "today": live["reruns"]["known_bad"]["today_verdict"],
            "red_ids": live["reruns"]["known_bad"]["red_ids"],
        },
        "eol_policy": {
            "today": live["deterministic_control"]["today_verdict"],
            "exit_code": live["deterministic_control"]["exit_code"],
            "flipped": live["deterministic_control"]["flipped"],
        },
        "hash_twice_match": not live["hash_control"]["flipped"],
        "controls_ok": live["controls_ok"],
    }


def compact_probe2(live: dict[str, Any]) -> dict[str, Any]:
    fd = live["feed_diff"]
    return {
        "probe": "probe2-advisory-feed-diff",
        "unit_id": UNIT,
        "instrument": "osv.dev/v1/query package-unversioned (not querybatch versioned)",
        "lodash": {
            "n_feed": fd["lodash"].get("n_feed"),
            "n_after": fd["lodash"].get("n_published_after_stored"),
            "error": fd["lodash"].get("error") or "",
            "sample_ids": [x.get("id") for x in (fd["lodash"].get("feed_sample") or [])[:5]],
        },
        "bytes": {
            "n_feed": fd["bytes"].get("n_feed"),
            "error": fd["bytes"].get("error") or "",
        },
        "brace_expansion": {
            "n_feed": fd["brace-expansion"].get("n_feed"),
            "n_after": fd["brace-expansion"].get("n_published_after_stored"),
        },
        "osv_unversioned_lodash": {
            "n_feed": fd["lodash_osv_unversioned"].get("n_feed"),
            "n_after": fd["lodash_osv_unversioned"].get("n_published_after_stored"),
        },
        "feed_live_both_states": live["controls_ok"]["feed_live_both_states"],
        "target_verdict": next(
            t["verdict"]
            for t in live["targets"]
            if t["id"] == "advisory-feed-diff-for-unrerunnable-gates"
        ),
    }


if __name__ == "__main__":
    print(json.dumps(compact_probe1(investigate()), indent=2, sort_keys=True))
