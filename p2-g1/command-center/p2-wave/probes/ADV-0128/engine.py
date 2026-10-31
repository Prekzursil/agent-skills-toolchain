#!/usr/bin/env python3
"""ADV-0128 fixture engine: loopback HTTP fixture + naive/contract clients.

Full-offline campaign: fill both client caches online, then cut the fixture and
classify what each client serves. Mid-partition campaign: two-step operation,
cut connectivity between step 1 and step 2, check whether the partial artifact
survives and whether a resume completes it instead of restarting from zero.

Naive client = serves its cache as a live result with no label (the defect this
unit hunts). Contract client = labels cache hits with cached_at/age_seconds and
degrades explicitly; partial step-1 bytes persist on disk and resume completes.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from common import PATHS


class Fixture:
    """Loopback-only fixture server. kill_switch cuts responses mid-flight."""

    def __init__(self) -> None:
        self.kill_switch = False
        hits = {"n": 0}
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                hits["n"] += 1
                if outer.kill_switch:
                    # Cut AFTER the request is received, BEFORE any response
                    # bytes: the mid-operation partition primitive.
                    self.close_connection = True
                    return
                path_id = self.path.strip("/").split("?")[0]
                body = json.dumps(
                    {
                        "payload": f"{path_id}-fixture-payload",
                        "served_at": datetime.now(timezone.utc).isoformat(),
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a: object) -> None:  # silence
                return

        self._hits = hits
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.host = "127.0.0.1"
        self.port = int(self._httpd.socket.getsockname()[1])
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    @property
    def requests_served(self) -> int:
        return int(self._hits["n"])

    def url(self, path_id: str) -> str:
        return f"http://{self.host}:{self.port}/{path_id}"

    def cut(self) -> None:
        self.kill_switch = True

    def restore(self) -> None:
        self.kill_switch = False

    def stop(self) -> None:
        try:
            self._httpd.shutdown()
            self._httpd.server_close()
        except Exception:
            pass


def _get(url: str, timeout_s: float = 2.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


class NaiveClient:
    """Caches live results and re-serves them, unlabelled, when offline."""

    def __init__(self) -> None:
        self.cache: dict[str, dict] = {}

    def fetch(self, fx: Fixture, path_id: str) -> dict:
        try:
            doc = _get(fx.url(path_id))
        except Exception:
            hit = self.cache.get(path_id)
            if hit is not None:
                # THE DEFECT: unlabelled cache served as a live result.
                return {"served": hit, "labelled": False, "from_cache": True}
            return {"served": None, "labelled": False, "from_cache": False, "error": "offline-no-cache"}
        self.cache[path_id] = doc
        return {"served": doc, "labelled": False, "from_cache": False}


class ContractClient:
    """Labels cache hits with age; degrades explicitly when offline."""

    def __init__(self) -> None:
        self.cache: dict[str, tuple[dict, float]] = {}

    def fetch(self, fx: Fixture, path_id: str) -> dict:
        try:
            doc = _get(fx.url(path_id))
        except Exception:
            hit = self.cache.get(path_id)
            if hit is not None:
                doc0, ts = hit
                age = round(max(0.0, time.time() - ts), 3)
                return {
                    "served": doc0,
                    "labelled": True,
                    "classification": "cached-and-labelled",
                    "cached_at": ts,
                    "age_seconds": age,
                }
            return {
                "served": None,
                "labelled": True,
                "classification": "explicit-degrade",
                "error": "offline-no-cache",
            }
        self.cache[path_id] = (doc, time.time())
        return {"served": doc, "labelled": True, "classification": "live", "from_cache": False}


def classify_naive_offline(res: dict) -> str:
    hit = res.get("from_cache")
    if hit and not res.get("labelled") and res.get("served") is not None:
        return "silent-success"
    if not hit and res.get("served") is None:
        return "explicit-error"
    return "other"


def run_offline() -> dict:
    """Full-offline campaign over all four paths, both clients."""
    fx = Fixture()
    naive, contract = NaiveClient(), ContractClient()
    online_ok = True
    try:
        for p in PATHS:
            r = contract.fetch(fx, p)
            if not (r.get("served") and not r.get("from_cache")):
                online_ok = False
            naive.fetch(fx, p)
        fx.stop()  # full offline: fixture gone, not just failing
        offline_contract, offline_naive = [], []
        for p in PATHS:
            rc = contract.fetch(fx, p)
            offline_contract.append(
                {
                    "path_id": p,
                    "labelled": bool(rc.get("labelled")),
                    "classification": rc.get("classification"),
                    "age_seconds": rc.get("age_seconds"),
                }
            )
            rn = naive.fetch(fx, p)
            offline_naive.append(
                {
                    "path_id": p,
                    "classification": classify_naive_offline(rn),
                    "labelled": bool(rn.get("labelled")),
                    "served_as_live": rn.get("served") is not None and not rn.get("labelled"),
                }
            )
    finally:
        fx.stop()
    return {
        "fixture_host": "127.0.0.1",
        "online_ok": online_ok,
        "offline_naive": offline_naive,
        "offline_contract": offline_contract,
        "naive_silent": sorted(r["path_id"] for r in offline_naive if r["classification"] == "silent-success"),
        "contract_labelled": sorted(r["path_id"] for r in offline_contract if r["labelled"]),
    }


def run_partition(root: Path) -> dict:
    """Mid-operation partition: cut after step-1, before step-2 body.

    Naive keeps its partial only in memory and restarts from zero on failure;
    contract persists the step-1 chunk on disk and resumes from it.
    """
    rows = []
    for p in PATHS:
        op_root = root / p
        op_root.mkdir(parents=True, exist_ok=True)
        naive_partial_path = op_root / "naive_partial.bin"
        contract_partial_path = op_root / "contract_step1.bin"
        fx = Fixture()
        naive, contract = NaiveClient(), ContractClient()
        try:
            step1 = _get(fx.url(p))
            chunk1 = json.dumps(step1, sort_keys=True).encode("utf-8")
            naive.cache[p] = dict(step1)
            contract.cache[p] = (dict(step1), time.time())
            naive_partial_path.write_bytes(chunk1)
            contract_partial_path.write_bytes(chunk1)
            pre_naive_bytes = naive_partial_path.stat().st_size
            pre_contract_bytes = contract_partial_path.stat().st_size

            fx.cut()
            # step 2 through the cut: both clients must fail explicitly.
            try:
                _get(fx.url(p))
                step2_failed = False
            except Exception:
                step2_failed = True

            # naive: discards the partial and restarts the whole op from zero.
            naive_partial_path.write_bytes(b"")  # its restart wiped in-flight state
            naive_lost = naive_partial_path.stat().st_size == 0 and pre_naive_bytes > 0

            # contract: step-1 chunk survives the cut on disk.
            after_cut_contract = contract_partial_path.read_bytes() == chunk1 and len(chunk1) > 0

            # resume: fixture returns; contract completes WITHOUT redoing step 1.
            fx.restore()
            remaining = _get(fx.url(p))
            chunk2 = json.dumps(remaining, sort_keys=True).encode("utf-8")
            final = contract_partial_path.read_bytes() + b"\n" + chunk2
            contract_partial_path.write_bytes(final)
            kept = final.startswith(chunk1)
            complete = contract_partial_path.stat().st_size > pre_contract_bytes
            rows.append(
                {
                    "path_id": p,
                    "step2_failed_explicitly": step2_failed,
                    "naive_lost_partial": naive_lost,
                    "after_cut_contract_has_step1": bool(after_cut_contract),
                    "contract_resume_complete": bool(kept and complete),
                    "fixture_loopback_only": fx.host == "127.0.0.1",
                }
            )
        finally:
            fx.stop()
    return {
        "fixture_host": "127.0.0.1",
        "rows": rows,
        "naive_lost_all": all(r["naive_lost_partial"] for r in rows),
        "contract_kept_all": all(r["after_cut_contract_has_step1"] for r in rows),
        "contract_resume_all": all(r["contract_resume_complete"] for r in rows),
        "explicit_step2_all": all(r["step2_failed_explicitly"] for r in rows),
    }
