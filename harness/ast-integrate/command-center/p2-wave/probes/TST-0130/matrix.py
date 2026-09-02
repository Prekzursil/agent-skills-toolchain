"""Live TLS-downgrade matrix against tools/lib/registry_fetch.py."""
from __future__ import annotations

import hashlib
import json
import ssl
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from tools.lib.net_allowlist import AllowlistError, inspect_config_keys  # noqa: E402
from tools.lib.registry_fetch import (  # noqa: E402
    CLASS_PARSE,
    CLASS_TLS,
    fetch_index,
    parse_config,
)
from capture import ConnectionCapture  # noqa: E402
from certs import mint  # noqa: E402
from servers import INDEX_BODY, FixtureCluster  # noqa: E402

CACHED_INDEX = b'{"registry":"cached-poison","nonce":"MUST-NOT-BE-SUBSTITUTED"}\n'
EXPECTED_NAME = "registry.test"


def _cfg(url: str, dest: Path, cache: Path, cafile: Path, **extra: Any) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "registry_url": url,
        "index_path": str(dest),
        "cache_path": str(cache),
        "cafile": str(cafile),
        "server_hostname": EXPECTED_NAME,
        "allowed_hosts": ["127.0.0.1"],
        "timeout": 4.0,
    }
    doc.update(extra)
    return doc


def _sha(data: bytes | None) -> str | None:
    if data is None:
        return None
    return hashlib.sha256(data).hexdigest()


def _assert_no_plaintext(capture: ConnectionCapture, tls_port: int, trap_port: int) -> list[str]:
    problems: list[str] = []
    if capture.has_port(80):
        problems.append("passive capture recorded a connect to port 80")
    if capture.has_port(trap_port) and trap_port != tls_port:
        problems.append(f"passive capture recorded a connect to HTTP trap port {trap_port}")
    httpish = [a for a in capture.attempts if int(a["port"]) != tls_port]
    if httpish:
        problems.append(f"connections besides the TLS fixture port: {httpish}")
    return problems


def run_tls_matrix(work: Path) -> dict[str, Any]:
    certs = mint(work / "certs")
    cluster = FixtureCluster(certs).start()
    out: dict[str, Any] = {
        "valid_port": cluster.valid.port,
        "wrong_port": cluster.wrong.port,
        "expired_port": cluster.expired.port,
        "trap_port": cluster.trap.port,
        "port80_bound": cluster.trap.port80_bound,
        "port80_error": cluster.trap.port80_error,
        "cases": {},
    }
    try:
        # --- wrong-CN ---
        dest = work / "wrong" / "index.json"
        cache = work / "wrong" / "cache.json"
        cache.parent.mkdir(parents=True)
        cache.write_bytes(CACHED_INDEX)
        cache_sha_before = _sha(CACHED_INDEX)
        url = f"https://127.0.0.1:{cluster.wrong.port}/index.json"
        cap = ConnectionCapture()
        with cap:
            result = fetch_index(_cfg(url, dest, cache, certs.ca_crt))
        problems = []
        if result.ok:
            problems.append("wrong-CN fetch reported ok")
        if result.classification != CLASS_TLS:
            problems.append(f"wrong-CN classification={result.classification!r} want {CLASS_TLS}")
        if result.exit_code == 0:
            problems.append("wrong-CN exit_code is 0")
        if dest.exists():
            problems.append("wrong-CN wrote dest index")
        cache_after = cache.read_bytes()
        if cache_after != CACHED_INDEX:
            problems.append("wrong-CN mutated the cached index")
        if result.cache_substituted:
            problems.append("wrong-CN marked cache_substituted")
        problems.extend(_assert_no_plaintext(cap, cluster.wrong.port, cluster.trap.port))
        if len(cap.attempts) != 1:
            problems.append(f"wrong-CN expected 1 connect, got {cap.attempts}")
        if cluster.trap.hits:
            problems.append(f"HTTP trap recorded hits {cluster.trap.hits}")
        out["cases"]["wrong_cn"] = {
            "pass": not problems,
            "problems": problems,
            "classification": result.classification,
            "exit_code": result.exit_code,
            "error": result.error,
            "capture": cap.attempts,
            "client_connections": result.connections,
            "cache_sha_before": cache_sha_before,
            "cache_sha_after": _sha(cache_after),
            "dest_exists": dest.exists(),
            "http_trap_hits": list(cluster.trap.hits),
        }

        # --- expired ---
        dest_e = work / "expired" / "index.json"
        cache_e = work / "expired" / "cache.json"
        cache_e.parent.mkdir(parents=True)
        cache_e.write_bytes(CACHED_INDEX)
        url_e = f"https://127.0.0.1:{cluster.expired.port}/index.json"
        cap_e = ConnectionCapture()
        with cap_e:
            result_e = fetch_index(_cfg(url_e, dest_e, cache_e, certs.ca_crt))
        problems_e = []
        if result_e.ok or result_e.classification != CLASS_TLS or result_e.exit_code == 0:
            problems_e.append(
                f"expired ok={result_e.ok} class={result_e.classification} exit={result_e.exit_code}"
            )
        if dest_e.exists():
            problems_e.append("expired wrote dest index")
        if cache_e.read_bytes() != CACHED_INDEX:
            problems_e.append("expired mutated cache")
        problems_e.extend(_assert_no_plaintext(cap_e, cluster.expired.port, cluster.trap.port))
        if cluster.trap.hits:
            problems_e.append(f"HTTP trap hits after expired: {cluster.trap.hits}")
        out["cases"]["expired"] = {
            "pass": not problems_e,
            "problems": problems_e,
            "classification": result_e.classification,
            "exit_code": result_e.exit_code,
            "error": result_e.error,
            "capture": cap_e.attempts,
            "client_connections": result_e.connections,
            "dest_exists": dest_e.exists(),
            "cache_unchanged": cache_e.read_bytes() == CACHED_INDEX,
        }

        # --- both-states: valid cert on the same kind of fixture endpoint ---
        dest_v = work / "valid" / "index.json"
        cache_v = work / "valid" / "cache.json"
        cache_v.parent.mkdir(parents=True)
        url_v = f"https://127.0.0.1:{cluster.valid.port}/index.json"
        cap_v = ConnectionCapture()
        with cap_v:
            result_v = fetch_index(_cfg(url_v, dest_v, cache_v, certs.ca_crt))
        problems_v = []
        if not result_v.ok or result_v.classification != "ok" or result_v.exit_code != 0:
            problems_v.append(
                f"valid-cert failed ok={result_v.ok} class={result_v.classification} "
                f"exit={result_v.exit_code} err={result_v.error}"
            )
        if not dest_v.is_file() or dest_v.read_bytes() != INDEX_BODY:
            problems_v.append("valid-cert dest bytes mismatch")
        if not cap_v.has_port(cluster.valid.port):
            problems_v.append("valid-cert capture missed the TLS port")
        if cap_v.has_port(80):
            problems_v.append("valid-cert captured port 80")
        out["cases"]["valid_both_states"] = {
            "pass": not problems_v,
            "problems": problems_v,
            "classification": result_v.classification,
            "exit_code": result_v.exit_code,
            "error": result_v.error,
            "capture": cap_v.attempts,
            "dest_sha256": _sha(dest_v.read_bytes()) if dest_v.is_file() else None,
            "bytes_written": result_v.bytes_written,
        }

        # --- detector control: unverified context WOULD accept wrong-CN ---
        unverified = ssl._create_unverified_context()
        unverified.check_hostname = False
        unverified.verify_mode = ssl.CERT_NONE
        mutant_ok = False
        mutant_err = None
        try:
            sock = __import__("socket").create_connection(
                ("127.0.0.1", cluster.wrong.port), timeout=4
            )
            tls = unverified.wrap_socket(sock, server_hostname=EXPECTED_NAME)
            tls.close()
            mutant_ok = True
        except Exception as exc:  # noqa: BLE001
            mutant_err = f"{type(exc).__name__}: {exc}"
        out["cases"]["unverified_mutant_would_pass"] = {
            "pass": mutant_ok,
            "problems": [] if mutant_ok else [f"unverified mutant did not connect: {mutant_err}"],
            "mutant_ok": mutant_ok,
            "error": mutant_err,
            "note": "Proves the wrong-CN fixture is reachable; refusal is verification, not a dead server.",
        }
    finally:
        cluster.stop()
    return out


def run_parse_controls() -> dict[str, Any]:
    cases: dict[str, Any] = {}

    def expect_parse_reject(name: str, doc: dict[str, Any]) -> None:
        problems: list[str] = []
        try:
            inspect_config_keys(doc)
            problems.append("inspect_config_keys accepted insecure config")
        except AllowlistError as exc:
            if exc.classification != CLASS_PARSE and "config-parse" not in exc.classification:
                problems.append(f"classification {exc.classification}")
        try:
            parse_config(doc)
            problems.append("parse_config accepted insecure config")
        except Exception as exc:  # noqa: BLE001
            text = str(exc)
            if "config-parse-rejected" not in text and "insecure" not in text.lower():
                # still a reject; ok as long as it did not return a config
                if getattr(exc, "classification", "") not in {CLASS_PARSE, "config-parse-rejected"}:
                    if "rejected" not in text.lower() and "insecure" not in text.lower():
                        problems.append(f"unexpected parse error {exc}")
        cases[name] = {"pass": not problems, "problems": problems, "doc": doc}

    expect_parse_reject("insecure_tls_true", {"insecure_tls": True, "registry_url": "https://127.0.0.1/i"})
    expect_parse_reject("insecure_flag", {"insecure": True, "registry_url": "https://127.0.0.1/i"})
    expect_parse_reject(
        "verify_false",
        {"tls_verify": False, "registry_url": "https://127.0.0.1/i"},
    )
    expect_parse_reject(
        "node_tls_reject_unauthorized",
        {"NODE_TLS_REJECT_UNAUTHORIZED": "0", "registry_url": "https://127.0.0.1/i"},
    )
    expect_parse_reject(
        "double_dash_insecure",
        {"--insecure": True, "registry_url": "https://127.0.0.1/i"},
    )

    # http scheme refused before connect
    problems_h: list[str] = []
    http_doc = {
        "registry_url": "http://127.0.0.1/index.json",
        "index_path": "/tmp/no-such-tst-0130-index.json",
        "allowed_hosts": ["127.0.0.1"],
        "server_hostname": "registry.test",
    }
    result_h = fetch_index(http_doc)
    if result_h.ok or result_h.classification not in {"scheme-refused"}:
        problems_h.append(f"http URL class={result_h.classification} ok={result_h.ok}")
    if result_h.connections:
        problems_h.append(f"http URL opened connections {result_h.connections}")
    cases["http_scheme_refused"] = {
        "pass": not problems_h,
        "problems": problems_h,
        "classification": result_h.classification,
        "connections": result_h.connections,
    }

    # clean config still parses
    problems_ok: list[str] = []
    try:
        parse_config(
            {
                "registry_url": "https://127.0.0.1:9443/index.json",
                "index_path": "/tmp/x",
                "allowed_hosts": ["127.0.0.1"],
                "server_hostname": "registry.test",
                "cafile": "/tmp/ca.crt",
            }
        )
    except Exception as exc:  # noqa: BLE001
        problems_ok.append(str(exc))
    cases["clean_config_parses"] = {"pass": not problems_ok, "problems": problems_ok}

    return {"cases": cases, "all_pass": all(c["pass"] for c in cases.values())}


def static_audit() -> dict[str, Any]:
    src = (REPO / "tools" / "lib" / "registry_fetch.py").read_text(encoding="utf-8")
    mjs = (REPO / "tools" / "lib" / "net-allowlist.mjs").read_text(encoding="utf-8")
    py_al = (REPO / "tools" / "lib" / "net_allowlist.py").read_text(encoding="utf-8")
    problems: list[str] = []
    live_forbidden = (
        "ssl._create_unverified_context(",
        "verify_mode = ssl.CERT_NONE",
        "check_hostname = False",
        "ctx.verify_mode = ssl.CERT_NONE",
    )
    for needle in live_forbidden:
        # Comments and the _FORBIDDEN_APIS documentation tuple are not calls.
        live_count = 0
        for line in src.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("_FORBIDDEN"):
                continue
            if stripped.startswith('"') or stripped.startswith("'"):
                continue
            if needle in line:
                live_count += 1
        if live_count:
            problems.append(f"live call {needle!r} count={live_count}")
    if "CERT_REQUIRED" not in src:
        problems.append("CERT_REQUIRED missing from client")
    if "check_hostname = True" not in src and "ctx.check_hostname = True" not in src:
        problems.append("check_hostname = True missing")
    if "insecure" not in mjs.lower() or "BANNED_INSECURE_KEYS" not in mjs:
        problems.append("net-allowlist.mjs missing banned insecure keys")
    if "BANNED_INSECURE_KEYS" not in py_al:
        problems.append("net_allowlist.py missing BANNED_INSECURE_KEYS")
    return {"pass": not problems, "problems": problems}


def run_all() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="tst-0130-") as tmp:
        tls = run_tls_matrix(Path(tmp))
    parse = run_parse_controls()
    audit = static_audit()
    tls_pass = all(c.get("pass") for c in tls["cases"].values())
    return {
        "tls": tls,
        "parse": parse,
        "audit": audit,
        "tls_pass": tls_pass,
        "parse_pass": parse["all_pass"],
        "audit_pass": audit["pass"],
        "all_pass": tls_pass and parse["all_pass"] and audit["pass"],
    }


if __name__ == "__main__":
    report = run_all()
    print(json.dumps({k: report[k] for k in ("tls_pass", "parse_pass", "audit_pass", "all_pass")}, sort_keys=True))
    if not report["all_pass"]:
        print(json.dumps(report, indent=2, default=str)[:4000])
        raise SystemExit(1)
    print("SUCCESS:TST-0130-matrix")
    raise SystemExit(0)
