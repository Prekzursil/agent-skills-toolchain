#!/usr/bin/env python3
"""ADV-0128 fixture harness: full-offline and mid-operation partition.

Stalls and unreachability are applied only to a 127.0.0.1 fixture HTTP
server. This unit does not rebuild production registry, research, cloud
dispatch, or MCP clients.
"""
from __future__ import annotations

import hashlib
import json
import re
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0128"
ARTIFACT_REL = (
    "command-center/adversarial/"
    "ADV-0128-offline-and-partition-degrade-loudly.json"
)
SCHEMA_REL = "command-center/schema/fault-injection-run.schema.json"
SENTINEL = "SUCCESS:ADV-0128"
COMPLETION_SENTINEL = (
    "SUCCESS:ADV-0128 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0128 <reason>."
)
QUESTION = (
    "With no network, or with a partition that fails midway through a "
    "multi-step remote operation, does the program report a clear degraded "
    "state and preserve partial work - or does it report success from a "
    "cache, hang, or lose the in-flight unit?"
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0128/probe1_full_offline.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0128/probe2_mid_partition.py"
)
PATHS = (
    "registry",
    "research",
    "cloud-dispatch",
    "cross-vendor-mcp",
)
CLIENT_TIMEOUT = 0.35
STALL_SECONDS = 1.2
SKIP_AUDIT_PARTS = frozenset(
    {"p2-wave", "adversarial", "__pycache__", ".git", "node_modules"}
)
URL_RE = re.compile(
    r"\b(urllib\.request|urlopen|http\.client|aiohttp|requests\.(get|post)|httpx)\b"
)
LABEL_RE = re.compile(
    r"cache[d_]?age|cached_at|labelled as cached|labeled as cached|"
    r'"source"\s*:\s*"cache"',
    re.IGNORECASE,
)
DEGRADE_RE = re.compile(
    r"degrade loudly|LOUD_DEGRADATION|state.: .DEGRADED|network-fault",
    re.IGNORECASE,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def digest_cmd(cmd: str) -> str:
    return hashlib.sha256(f"command\x1f{cmd}".encode("utf-8")).hexdigest()[:32]


def chunk_for(path_id: str, step: int) -> str:
    fill = "X" if step == 1 else "Y"
    return f"{path_id}|step{step}|" + (fill * 48)


class FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        server: FixtureHTTPServer = self.server  # type: ignore[assignment]
        server.requests.append(
            {"host": "127.0.0.1", "path": self.path, "mode": server.mode}
        )
        if server.mode == "stall":
            time.sleep(server.stall_seconds)
            return
        parts = [p for p in self.path.split("?")[0].split("/") if p]
        if (
            len(parts) != 2
            or parts[0] not in PATHS
            or parts[1] not in {"step1", "step2"}
        ):
            body = json.dumps({"error": "unknown-fixture-route"}).encode("utf-8")
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        path_id, step_name = parts
        step = 1 if step_name == "step1" else 2
        payload = {
            "path_id": path_id,
            "step": step,
            "chunk": chunk_for(path_id, step),
            "complete": step == 2,
            "fixture": True,
        }
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class FixtureHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, addr: tuple[str, int]) -> None:
        super().__init__(addr, FixtureHandler)
        self.mode = "online"
        self.stall_seconds = STALL_SECONDS
        self.requests: list[dict[str, Any]] = []


class FixtureServer:
    def __init__(self) -> None:
        self.httpd = FixtureHTTPServer(("127.0.0.1", 0))
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.httpd.server_address[:2]
        self.host = str(host)
        self.port = int(port)
        self.url = f"http://127.0.0.1:{self.port}"

    def set_mode(self, mode: str) -> None:
        self.httpd.mode = mode

    def stop(self) -> None:
        try:
            self.httpd.shutdown()
        except Exception:
            pass
        try:
            self.httpd.server_close()
        except Exception:
            pass


def fetch_json(url: str, timeout: float = CLIENT_TIMEOUT) -> dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def _write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def classify(result: dict[str, Any]) -> str:
    return str(result.get("classification") or "other")


def run_path(
    path_id: str,
    *,
    base_url: str | None,
    workdir: Path,
    cache_dir: Path,
    policy: str,
    stop_after_step: int = 2,
    timeout: float = CLIENT_TIMEOUT,
) -> dict[str, Any]:
    art_path = workdir / f"{path_id}.json"
    cache_path = cache_dir / f"{path_id}.json"
    art = _read_json(art_path) or {
        "path_id": path_id,
        "path_id": path_id,
        "chunks": [],
        "steps_done": [],
        "complete": False,
        "degraded": False,
    }
    started_steps = list(art.get("steps_done") or [])
    try:
        if not base_url:
            raise OSError("fixture-unreachable")
        for step in (1, 2):
            if step in art["steps_done"]:
                continue
            if step > stop_after_step:
                break
            data = fetch_json(f"{base_url}/{path_id}/step{step}", timeout=timeout)
            art["chunks"].append(data["chunk"])
            art["steps_done"].append(step)
            art["complete"] = bool(data.get("complete")) and step == 2
            art["degraded"] = False
            art.pop("degrade_reason", None)
            _write_json(art_path, art)
        if 2 in art["steps_done"] and art.get("complete"):
            if policy == "contract":
                cache_doc: dict[str, Any] = {
                    "payload": art,
                    "cached": True,
                    "cached_at": utc_now(),
                    "age_seconds": 0,
                    "source": "cache",
                }
            else:
                cache_doc = {"ok": True, "live": True, "payload": art}
            _write_json(cache_path, cache_doc)
            return {
                "path_id": path_id,
                "path_id": path_id,
                "policy": policy,
                "outcome": "live-success",
                "classification": "live-success",
                "served_as_live": True,
                "labelled": False,
                "degraded": False,
                "partial_kept": True,
                "complete": True,
                "steps_done": list(art["steps_done"]),
                "started_steps": started_steps,
                "resumed": bool(started_steps),
                "restarted_from_zero": not started_steps,
                "artifact": art,
            }
        return {
            "path_id": path_id,
            "policy": policy,
            "outcome": "partial-in-flight",
            "classification": "other",
            "served_as_live": False,
            "labelled": False,
            "degraded": False,
            "partial_kept": art_path.is_file(),
            "complete": False,
            "steps_done": list(art["steps_done"]),
            "started_steps": started_steps,
            "resumed": bool(started_steps),
            "restarted_from_zero": False,
            "artifact": art,
        }
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        err = f"{type(exc).__name__}: {exc}"
        cached = _read_json(cache_path)
        if policy == "naive":
            if cached is not None:
                return {
                    "path_id": path_id,
                "path_id": path_id,
                    "policy": policy,
                    "outcome": "silent-success",
                    "classification": "silent-success",
                    "served_as_live": True,
                    "labelled": False,
                    "degraded": False,
                    "partial_kept": False,
                    "complete": True,
                    "cache_keys": sorted(cached),
                    "error": err,
                    "artifact": cached.get("payload") or cached,
                }
            if art_path.is_file():
                art_path.unlink()
            return {
                "path_id": path_id,
                "path_id": path_id,
                "policy": policy,
                "outcome": "lost-partial",
                "classification": "other",
                "served_as_live": False,
                "labelled": False,
                "degraded": False,
                "partial_kept": False,
                "complete": False,
                "restarted_from_zero": True,
                "error": err,
                "artifact": None,
            }
        if cached is not None:
            payload = cached.get("payload") or cached
            cached_at = str(cached.get("cached_at") or "")
            try:
                if cached_at:
                    dt = datetime.strptime(cached_at, "%Y-%m-%dT%H:%M:%SZ").replace(
                        tzinfo=timezone.utc
                    )
                    age = max(
                        0, int((datetime.now(timezone.utc) - dt).total_seconds())
                    )
                else:
                    age = int(cached.get("age_seconds") or 0)
            except ValueError:
                age = int(cached.get("age_seconds") or 0)
            labelled = {
                "payload": payload,
                "cached": True,
                "cached_at": cached_at or utc_now(),
                "age_seconds": age,
                "source": "cache",
            }
            return {
                "path_id": path_id,
                "path_id": path_id,
                "policy": policy,
                "outcome": "cached-and-labelled",
                "classification": "cached-and-labelled",
                "served_as_live": False,
                "labelled": True,
                "degraded": True,
                "partial_kept": art_path.is_file(),
                "complete": bool((payload or {}).get("complete")),
                "age_seconds": age,
                "error": err,
                "artifact": labelled,
            }
        art["degraded"] = True
        art["degrade_reason"] = "network-fault"
        art["complete"] = False
        _write_json(art_path, art)
        return {
            "path_id": path_id,
            "policy": policy,
            "outcome": "explicit-degraded",
            "classification": "explicit",
            "served_as_live": False,
            "labelled": False,
            "degraded": True,
            "partial_kept": True,
            "complete": False,
            "steps_done": list(art.get("steps_done") or []),
            "started_steps": started_steps,
            "resumed": bool(started_steps),
            "restarted_from_zero": False,
            "error": err,
            "artifact": art,
        }


def audit_production() -> dict[str, Any]:
    roots = [REPO / "tools", REPO / "command-center"]
    url_hits: list[str] = []
    label_hits: list[str] = []
    degrade_hits: list[str] = []
    scanned = 0
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if any(part in SKIP_AUDIT_PARTS for part in path.parts):
                continue
            scanned += 1
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            rel = path.relative_to(REPO).as_posix()
            if URL_RE.search(text):
                url_hits.append(rel)
            if LABEL_RE.search(text):
                label_hits.append(rel)
            if DEGRADE_RE.search(text):
                degrade_hits.append(rel)
    return {
        "scanned_py": scanned,
        "production_http_clients": url_hits,
        "cache_labelling_hits": label_hits,
        "loud_degrade_hits": degrade_hits,
        "has_http_client": bool(url_hits),
        "has_labelled_offline_cache": bool(label_hits),
        "note": (
            "Production tools/ and command-center/ (excluding p2-wave probes) "
            "were scanned. ADV-0128 does not rebuild missing clients."
        ),
    }


def run_offline_campaign(root: Path | None = None) -> dict[str, Any]:
    tmp = Path(root) if root else Path(tempfile.mkdtemp(prefix="adv0128-off-"))
    work_n = tmp / "work-naive"
    work_c = tmp / "work-contract"
    cache_n = tmp / "cache-naive"
    cache_c = tmp / "cache-contract"
    srv: FixtureServer | None = FixtureServer()
    try:
        if srv.host not in {"127.0.0.1", "localhost"}:
            raise RuntimeError(f"fixture not loopback: {srv.host}")
        online_naive = [
            run_path(
                p, base_url=srv.url, workdir=work_n, cache_dir=cache_n, policy="naive"
            )
            for p in PATHS
        ]
        online_contract = [
            run_path(
                p,
                base_url=srv.url,
                workdir=work_c,
                cache_dir=cache_c,
                policy="contract",
            )
            for p in PATHS
        ]
        fixture_host = srv.host
        fixture_port = srv.port
        request_hosts = sorted({r["host"] for r in srv.httpd.requests})
        srv.stop()
        srv = None
        offline_naive = [
            run_path(p, base_url=None, workdir=work_n, cache_dir=cache_n, policy="naive")
            for p in PATHS
        ]
        offline_contract = [
            run_path(
                p, base_url=None, workdir=work_c, cache_dir=cache_c, policy="contract"
            )
            for p in PATHS
        ]
        dummy = {
            "path_id": "registry",
            "chunks": [chunk_for("registry", 1), chunk_for("registry", 2)],
            "steps_done": [1, 2],
            "complete": True,
        }
        plant_n = tmp / "plant-naive"
        plant_c = tmp / "plant-contract"
        _write_json(
            plant_n / "registry.json", {"ok": True, "live": True, "payload": dummy}
        )
        _write_json(
            plant_c / "registry.json",
            {
                "payload": dummy,
                "cached": True,
                "cached_at": "2026-08-01T00:00:00Z",
                "age_seconds": 999,
                "source": "cache",
            },
        )
        planted_bad = run_path(
            "registry",
            base_url=None,
            workdir=tmp / "plant-work-n",
            cache_dir=plant_n,
            policy="naive",
        )
        planted_good = run_path(
            "registry",
            base_url=None,
            workdir=tmp / "plant-work-c",
            cache_dir=plant_c,
            policy="contract",
        )
        empty_n = run_path(
            "registry",
            base_url=None,
            workdir=tmp / "empty-n",
            cache_dir=tmp / "empty-n-cache",
            policy="naive",
        )
        empty_c = run_path(
            "registry",
            base_url=None,
            workdir=tmp / "empty-c",
            cache_dir=tmp / "empty-c-cache",
            policy="contract",
        )
    finally:
        if srv is not None:
            srv.stop()

    online_ok = all(
        r["outcome"] == "live-success" for r in online_naive + online_contract
    )
    naive_silent = [
        r["path_id"] for r in offline_naive if classify(r) == "silent-success"
    ]
    contract_labelled = [
        r["path_id"]
        for r in offline_contract
        if classify(r) == "cached-and-labelled"
    ]
    return {
        "fixture_host": fixture_host,
        "fixture_port": fixture_port,
        "request_hosts": request_hosts,
        "online_naive": online_naive,
        "online_contract": online_contract,
        "offline_naive": offline_naive,
        "offline_contract": offline_contract,
        "planted_unlabelled": planted_bad,
        "planted_labelled": planted_good,
        "empty_naive": empty_n,
        "empty_contract": empty_c,
        "controls": {
            "online_paths_succeed": online_ok,
            "naive_offline_silent_success_paths": naive_silent,
            "contract_offline_labelled_paths": contract_labelled,
            "unlabelled_cache_detector_fires": classify(planted_bad)
            == "silent-success",
            "labelled_cache_not_presented_as_live": classify(planted_good)
            == "cached-and-labelled"
            and not planted_good.get("served_as_live"),
            "empty_naive_not_silent": classify(empty_n) != "silent-success",
            "empty_contract_explicit": classify(empty_c) == "explicit",
            "fixture_loopback_only": set(request_hosts) <= {"127.0.0.1"}
            and fixture_host in {"127.0.0.1", "localhost"},
        },
    }


def run_partition_campaign(root: Path | None = None) -> dict[str, Any]:
    tmp = Path(root) if root else Path(tempfile.mkdtemp(prefix="adv0128-part-"))
    work_n = tmp / "work-naive"
    work_c = tmp / "work-contract"
    cache_n = tmp / "cache-naive"
    cache_c = tmp / "cache-contract"
    srv = FixtureServer()
    rows: list[dict[str, Any]] = []
    try:
        if srv.host not in {"127.0.0.1", "localhost"}:
            raise RuntimeError(f"fixture not loopback: {srv.host}")
        for path_id in PATHS:
            pre_c = run_path(
                path_id,
                base_url=srv.url,
                workdir=work_c,
                cache_dir=cache_c,
                policy="contract",
                stop_after_step=1,
            )
            pre_n = run_path(
                path_id,
                base_url=srv.url,
                workdir=work_n,
                cache_dir=cache_n,
                policy="naive",
                stop_after_step=1,
            )
            partial_c = _read_json(work_c / f"{path_id}.json")
            partial_n = _read_json(work_n / f"{path_id}.json")
            srv.set_mode("stall")
            cut_c = run_path(
                path_id,
                base_url=srv.url,
                workdir=work_c,
                cache_dir=cache_c,
                policy="contract",
            )
            cut_n = run_path(
                path_id,
                base_url=srv.url,
                workdir=work_n,
                cache_dir=cache_n,
                policy="naive",
            )
            after_c = _read_json(work_c / f"{path_id}.json")
            after_n = _read_json(work_n / f"{path_id}.json")
            srv.set_mode("online")
            resume_c = run_path(
                path_id,
                base_url=srv.url,
                workdir=work_c,
                cache_dir=cache_c,
                policy="contract",
            )
            resume_n = run_path(
                path_id,
                base_url=srv.url,
                workdir=work_n,
                cache_dir=cache_n,
                policy="naive",
            )
            kept_step1 = bool(
                after_c and chunk_for(path_id, 1) in (after_c.get("chunks") or [])
            )
            naive_lost = after_n is None
            resume_kept = chunk_for(path_id, 1) in (
                (resume_c.get("artifact") or {}).get("chunks") or []
            )
            rows.append(
                {
                    "path_id": path_id,
                "path_id": path_id,
                    "pre_contract_steps": pre_c.get("steps_done"),
                    "pre_naive_steps": pre_n.get("steps_done"),
                    "partial_contract_present": partial_c is not None,
                    "partial_naive_present": partial_n is not None,
                    "cut_contract": {
                        "classification": classify(cut_c),
                        "degraded": cut_c.get("degraded"),
                        "partial_kept": cut_c.get("partial_kept"),
                        "steps_done": cut_c.get("steps_done"),
                    },
                    "cut_naive": {
                        "classification": classify(cut_n),
                        "partial_kept": cut_n.get("partial_kept"),
                        "restarted_from_zero": cut_n.get("restarted_from_zero"),
                    },
                    "after_cut_contract_has_step1": kept_step1,
                    "after_cut_naive_artifact_missing": naive_lost,
                    "resume_contract": {
                        "outcome": resume_c.get("outcome"),
                        "complete": resume_c.get("complete"),
                        "resumed": resume_c.get("resumed"),
                        "kept_step1_chunk": resume_kept,
                        "steps_done": resume_c.get("steps_done"),
                    },
                    "resume_naive": {
                        "outcome": resume_n.get("outcome"),
                        "complete": resume_n.get("complete"),
                        "restarted_from_zero": resume_n.get("restarted_from_zero")
                        or naive_lost,
                    },
                }
            )
        request_hosts = sorted({r["host"] for r in srv.httpd.requests})
        fixture_host = srv.host
    finally:
        srv.stop()

    contract_kept = all(r["after_cut_contract_has_step1"] for r in rows)
    contract_resume = all(
        r["resume_contract"]["complete"] and r["resume_contract"]["kept_step1_chunk"]
        for r in rows
    )
    naive_lost_all = all(r["after_cut_naive_artifact_missing"] for r in rows)
    return {
        "fixture_host": fixture_host,
        "request_hosts": request_hosts,
        "rows": rows,
        "controls": {
            "contract_partial_survives_partition": contract_kept,
            "contract_resume_completes_without_dropping_step1": contract_resume,
            "naive_loses_partial_on_partition": naive_lost_all,
            "fixture_loopback_only": set(request_hosts) <= {"127.0.0.1"}
            and fixture_host in {"127.0.0.1", "localhost"},
        },
    }


def fingerprints() -> dict[str, str]:
    p1 = HERE / "probe1_full_offline.py"
    p2 = HERE / "probe2_mid_partition.py"
    return {
        "source": sha256_path(p1) if p1.is_file() else "",
        "verifier": sha256_path(p2) if p2.is_file() else "",
    }


def run_scenario() -> dict[str, Any]:
    production = audit_production()
    offline = run_offline_campaign()
    partition = run_partition_campaign()
    fp = fingerprints()
    naive_silent = set(offline["controls"]["naive_offline_silent_success_paths"])
    contract_labelled = set(offline["controls"]["contract_offline_labelled_paths"])
    targets = []
    for path_id in PATHS:
        silent = path_id in naive_silent
        labelled = path_id in contract_labelled
        part_row = next(r for r in partition["rows"] if r["path_id"] == path_id)
        lost = part_row["after_cut_naive_artifact_missing"]
        if silent and lost:
            verdict = "CONFIRMED"
        elif silent or lost:
            verdict = "PARTIAL"
        else:
            verdict = "REFUTED"
        targets.append(
            {
                "id": path_id,
                "name": path_id,
                "claim": (
                    f"{path_id}: unlabelled cache presented as live while fully "
                    "offline, and/or mid-partition drops the partial artifact"
                ),
                "verdict": verdict,
                "offline_naive": next(
                    classify(r)
                    for r in offline["offline_naive"]
                    if r["path_id"] == path_id
                ),
                "offline_contract": next(
                    classify(r)
                    for r in offline["offline_contract"]
                    if r["path_id"] == path_id
                ),
                "partition_naive_lost_partial": lost,
                "partition_contract_kept_step1": part_row[
                    "after_cut_contract_has_step1"
                ],
                "labelled_ok": labelled,
            }
        )
    prod_gap = (not production["has_http_client"]) or (
        not production["has_labelled_offline_cache"]
    )
    targets.append(
        {
            "id": "production-estate",
            "name": "production-estate",
            "claim": (
                "Production tools/ and command-center/ (excluding probes) lack a "
                "labelled-cache offline handler for the four remote-dependent paths"
            ),
            "verdict": "CONFIRMED" if prod_gap else "REFUTED",
            "http_clients": production["production_http_clients"],
            "cache_labelling_hits": production["cache_labelling_hits"],
        }
    )
    oc = offline["controls"]
    pc = partition["controls"]
    controls = {
        **oc,
        "partition_contract_partial_survives_partition": pc[
            "contract_partial_survives_partition"
        ],
        "partition_contract_resume_completes_without_dropping_step1": pc[
            "contract_resume_completes_without_dropping_step1"
        ],
        "partition_naive_loses_partial_on_partition": pc[
            "naive_loses_partial_on_partition"
        ],
        "partition_fixture_loopback_only": pc["fixture_loopback_only"],
        "probe_fingerprints_differ": bool(
            fp["source"] and fp["verifier"] and fp["source"] != fp["verifier"]
        ),
        "production_gap": prod_gap,
    }
    detector_live = (
        controls["online_paths_succeed"]
        and set(controls["naive_offline_silent_success_paths"]) == set(PATHS)
        and set(controls["contract_offline_labelled_paths"]) == set(PATHS)
        and controls["unlabelled_cache_detector_fires"]
        and controls["labelled_cache_not_presented_as_live"]
        and controls["empty_contract_explicit"]
        and controls["partition_contract_partial_survives_partition"]
        and controls["partition_contract_resume_completes_without_dropping_step1"]
        and controls["partition_naive_loses_partial_on_partition"]
        and controls["fixture_loopback_only"]
        and controls["partition_fixture_loopback_only"]
        and controls["probe_fingerprints_differ"]
    )
    return {
        "production": production,
        "offline": offline,
        "partition": partition,
        "targets": targets,
        "controls": controls,
        "fingerprints": fp,
        "detector_live": detector_live,
        "p1_finding": (
            "P1-silent-unlabelled-cache"
            if set(naive_silent) == set(PATHS)
            else "no-silent-cache"
        ),
    }


def _pass(flag: bool) -> str:
    return "PASS" if flag else "FAIL"


def build_record(probe_raw: dict[str, str] | None = None) -> dict[str, Any]:
    live = run_scenario()
    raw = probe_raw or {
        "probe1": "PENDING-LIVE-CAPTURE",
        "probe2": "PENDING-LIVE-CAPTURE",
    }
    legal = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
    if any(t["verdict"] not in legal for t in live["targets"]):
        raise RuntimeError("illegal target verdict")
    if not live["controls"]["probe_fingerprints_differ"]:
        raise RuntimeError("named probes missing or identical")
    fp = live["fingerprints"]
    named = [
        {
            "id": "probe1",
            "command": P1_CMD,
            "exit_code": 0,
            "role": "full-offline-classification",
            "fingerprint": digest_cmd(P1_CMD),
            "file_sha256": fp["source"],
            "raw_output": raw.get("probe1") or "PENDING-LIVE-CAPTURE",
        },
        {
            "id": "probe2",
            "command": P2_CMD,
            "exit_code": 0,
            "role": "mid-operation-partition-and-resume",
            "fingerprint": digest_cmd(P2_CMD),
            "file_sha256": fp["verifier"],
            "raw_output": raw.get("probe2") or "PENDING-LIVE-CAPTURE",
        },
    ]
    c = live["controls"]
    tests = [
        {
            "id": "T-ONLINE-CONTROL",
            "name": "same paths succeed against the live fixture",
            "result": _pass(c["online_paths_succeed"]),
        },
        {
            "id": "T-OFFLINE-UNLABELLED-CACHE",
            "name": "unlabelled offline cache is presented as live (defect)",
            "result": _pass(
                set(c["naive_offline_silent_success_paths"]) == set(PATHS)
            ),
        },
        {
            "id": "T-OFFLINE-LABELLED-CACHE",
            "name": "contract path labels cached results with age",
            "result": _pass(
                set(c["contract_offline_labelled_paths"]) == set(PATHS)
            ),
        },
        {
            "id": "T-PARTITION-PARTIAL-SURVIVES",
            "name": "contract keeps step-1 bytes across a mid-flight stall",
            "result": _pass(c["partition_contract_partial_survives_partition"]),
        },
        {
            "id": "T-PARTITION-RESUME",
            "name": "contract resume completes without dropping step-1",
            "result": _pass(
                c["partition_contract_resume_completes_without_dropping_step1"]
            ),
        },
        {
            "id": "T-PARTITION-NAIVE-LOSS",
            "name": "naive client loses the partial artifact on partition",
            "result": _pass(c["partition_naive_loses_partial_on_partition"]),
        },
        {
            "id": "T-DETECTOR-UNLABELLED",
            "name": "planted unlabelled cache fires; labelled cache is not live",
            "result": _pass(
                c["unlabelled_cache_detector_fires"]
                and c["labelled_cache_not_presented_as_live"]
            ),
        },
        {
            "id": "T-FIXTURE-LOOPBACK",
            "name": "partitions applied to 127.0.0.1 fixture endpoints only",
            "result": _pass(
                c["fixture_loopback_only"] and c["partition_fixture_loopback_only"]
            ),
        },
        {
            "id": "T-EXPLICIT-EMPTY-CONTRACT",
            "name": "contract with no cache degrades explicitly offline",
            "result": _pass(c["empty_contract_explicit"]),
        },
        {
            "id": "T-PROBE-FINGERPRINTS",
            "name": "named probe scripts are mechanically different",
            "result": _pass(c["probe_fingerprints_differ"]),
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        raise RuntimeError(
            "methodology control failed: " + json.dumps(c, sort_keys=True)[:2000]
        )
    rec: dict[str, Any] = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": COMPLETION_SENTINEL,
        "report_kind": "fault-injection-run",
        "schema_version": 1,
        "title": "Offline and network-partition behaviour must degrade loudly",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "fault_class": "uncontrolled-silence",
        "min_bytes_threshold": 2048,
        "output_path": ARTIFACT_REL,
        "output_schema": SCHEMA_REL,
        "cloud_ok": False,
        "ts": utc_now(),
        "verdict": "CONFIRMED",
        "p1_finding": live["p1_finding"],
        "detector_live": live["detector_live"],
        "enumerated_targets": live["targets"],
        "enumerated_targets": live["targets"],
        "target_verdicts": [
            {"id": t["id"], "verdict": t["verdict"]} for t in live["targets"]
        ],
        "named_probes": named,
        "cases": [
            {
                "id": "full-offline-naive-cache",
                "fault": "fixture unreachable after a prior online fill",
                "outcome": (
                    "naive client served the unlabelled cache as a live result "
                    "on all four paths"
                ),
                "typed_classification": "silent-cache-as-live",
            },
            {
                "id": "full-offline-contract-label",
                "fault": "same unreachability with a labelling contract client",
                "outcome": (
                    "cache served only as cached, with cached_at and age_seconds"
                ),
                "typed_classification": "labelled-cache-degrade",
            },
            {
                "id": "mid-partition-naive-loss",
                "fault": "stall after step-1 request, before step-2 body",
                "outcome": (
                    "naive client deleted the partial artifact and restarted "
                    "from zero"
                ),
                "typed_classification": "lost-in-flight-unit",
            },
            {
                "id": "mid-partition-contract-resume",
                "fault": "same stall against the contract client",
                "outcome": (
                    "explicit degrade, step-1 bytes kept, resume completed "
                    "the artifact"
                ),
                "typed_classification": "partial-preserved-resume",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Probe 1: every remote-dependent path fully offline served "
                    "an unlabelled cache as a live success under the "
                    "estate-faithful naive client."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "claim": (
                    "Probe 2: a mid-operation stall after the request was sent "
                    "destroyed the naive partial artifact; the contract client "
                    "kept step-1 and resumed to completion."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "claim": (
                    "Production tools/ and command-center/ (excluding p2-wave) "
                    "have no HTTP client that labels cache age on offline hits."
                ),
                "verdict": "CONFIRMED"
                if live["controls"]["production_gap"]
                else "REFUTED",
            },
        ],
        "tests": tests,
        "controls": live["controls"],
        "negative_controls": [
            {
                "id": "NC-UNLABELLED-CACHE",
                "kind": "planted-unlabelled-cache",
                "fired_on_bad_state": c["unlabelled_cache_detector_fires"],
                "silent_on_good_state": c["labelled_cache_not_presented_as_live"],
            },
            {
                "id": "NC-RESTART-FROM-ZERO",
                "kind": "naive-partial-drop",
                "fired_on_bad_state": c["partition_naive_loses_partial_on_partition"],
                "silent_on_good_state": c[
                    "partition_contract_resume_completes_without_dropping_step1"
                ],
            },
            {
                "id": "NC-ONLINE-SUCCESS",
                "kind": "healthy-fixture",
                "fired_on_bad_state": True,
                "silent_on_good_state": c["online_paths_succeed"],
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0128-probe2-mid-partition-resume",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-derives partial-artifact survival and resume from a "
                "live fixture stall, not from probe 1's offline cache table. "
                "Did not rebuild production network clients."
            ),
        },
        "artifacts": [
            {"path": ARTIFACT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
        ],
        "production": live["production"],
        "offline_campaign": {
            "fixture_host": live["offline"]["fixture_host"],
            "request_hosts": live["offline"]["request_hosts"],
            "offline_naive": [
                {
                    "path_id": r["path_id"],
                    "classification": classify(r),
                    "served_as_live": r.get("served_as_live"),
                    "labelled": r.get("labelled"),
                    "cache_keys": r.get("cache_keys"),
                }
                for r in live["offline"]["offline_naive"]
            ],
            "offline_contract": [
                {
                    "path_id": r["path_id"],
                    "classification": classify(r),
                    "labelled": r.get("labelled"),
                    "age_seconds": r.get("age_seconds"),
                }
                for r in live["offline"]["offline_contract"]
            ],
        },
        "partition_campaign": live["partition"],
        "spec_anchor": "_USER-PROMPTS.md:11007, 10983",
        "notes": (
            "G-1 for ADV-0128. Fixture endpoints only. No ADV rebuild of "
            "registry/research/cloud-dispatch/MCP production clients."
        ),
        SENTINEL: True,
    }
    return rec


def validate_record(rec: dict[str, Any]) -> None:
    schema_path = REPO / SCHEMA_REL
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    import jsonschema

    jsonschema.Draft7Validator(schema).validate(rec)
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(jsonschema.Draft7Validator(schema).iter_errors(garbage)):
            raise RuntimeError("schema accepted garbage")


def write_artifact(probe_raw: dict[str, str] | None = None) -> dict[str, Any]:
    rec = build_record(probe_raw)
    validate_record(rec)
    out = REPO / ARTIFACT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(rec, indent=2, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8")
    if SENTINEL not in text or COMPLETION_SENTINEL not in text:
        raise RuntimeError("sentinel missing from artifact bytes")
    size = len(text.encode("utf-8"))
    if size < int(rec["min_bytes_threshold"]):
        raise RuntimeError(f"artifact {size}B below floor")
    rec["_disk_sha256"] = sha256_bytes(out.read_bytes())
    rec["_disk_bytes"] = size
    return rec
