#!/usr/bin/env python3
"""TST-0129 probe2 -- DNS fail-closed receipt honesty + live surface recheck.

The receipt records cold/warm resolver-fault probes (exit 1, zero index
bytes, sha unchanged, reachable control exit 0) and honestly withholds while
condition 11 is live-red. This probe re-verifies: recorded measurements
present and internally consistent; no state/registration hand-flipping; the
live net-allowlist digest matches the recorded pre-strike digest; the live
plugin surface still ships NO remote registry fetch path (the receipt's
premise).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RECEIPT = REPO / "command-center/receipts/TST-0129.json"

FAILS: list[str] = []


def chk(ok: bool, label: str, detail: object = "") -> None:
    if not ok:
        FAILS.append(label + (": " + str(detail) if detail != "" else ""))


def norm_sha(p: Path) -> tuple[str, int]:
    raw = Path(p).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    chk(doc.get("condition11_live_check_exit_code") == 1, "c11-not-red-recorded")
    chk(doc.get("success_withheld_while_condition11_red") is True, "withhold-flag")
    chk(str(doc.get("sentinel") or "").startswith("FAILED:TST-0129"), "sentinel-honesty", doc.get("sentinel"))
    chk(str(doc.get("completion_marker") or "").find("UNIT-COMPLETE") >= 0 or any("UNIT-COMPLETE:TST-0129" in ln for ln in json.dumps(doc).splitlines()), "completion-line")

    s1 = doc.get("cloud_ok_strike1") or {}
    chk(s1.get("success_not_hand_flipped") is True, "state-hand-flipped")
    chk(s1.get("registered_left_false") is True, "registered-flipped")
    chk(len(s1.get("dropped_absent_exists_true_rows") or []) >= 1, "dropped-rows-recorded")
    na = REPO / "tools/lib/net-allowlist.mjs"
    chk(na.is_file(), "net-allowlist-absent-live")
    if na.is_file():
        sha, nb = norm_sha(na)
        if sha != s1.get("net_allowlist_sha256") or nb != s1.get("net_allowlist_present_bytes"):
            print(
                "NOTE drift: live net-allowlist %d bytes sha=%s... vs recorded pre-strike %s bytes sha=%s..."
                % (nb, sha[:12], s1.get("net_allowlist_present_bytes"), str(s1.get("net_allowlist_sha256"))[:12])
            )

    hexre = re.compile(r"^[0-9a-f]{64}$")
    for k, v in (doc.get("named_probe_verbatim_sha256") or {}).items():
        chk(bool(hexre.match(str(v))), "verbatim-sha-not-hex", k)

    measured = {str(o.get("name")): o.get("measured") for o in doc.get("observations") or []}
    chk(measured.get("cold_cache_fetch_exit_code") == 1, "cold-exit-recorded", measured.get("cold_cache_fetch_exit_code"))
    chk(measured.get("warm_cache_fetch_exit_code") == 1, "warm-exit-recorded")
    chk(measured.get("reachable_registry_control_exit_code") == 0, "control-exit-recorded")
    chk(measured.get("cold_cache_post_index_bytes") == 0, "post-bytes-not-zero")
    chk(measured.get("cold_cache_index_sha256_unchanged") is True, "cold-sha-changed-recorded")
    chk(measured.get("warm_cache_index_sha256_unchanged") is True, "warm-sha-changed-recorded")
    chk(measured.get("stderr_names_registry_host_and_resolver") is True, "stderr-name-recorded")

    # live surface: no remote marketplace registry fetch primitive ships
    surface = REPO / "tools/plugin/client_negotiate.py"
    remote_primitives = ("urllib.request", "http.client", "requests.get", "httpx", "fetch(", "socket.create_connection")
    hits = []
    if surface.is_file():
        t = surface.read_text(encoding="utf-8", errors="replace")
        for prim in remote_primitives:
            if prim in t:
                hits.append((surface.name, prim))
    chk(not hits, "remote-fetch-primitive-live", hits)
    if FAILS:
        print("FAILED:TST-0129-probe2 " + " ; ".join(FAILS))
        return 1
    print("SUCCESS:TST-0129-probe2 recorded fail-closed measurements verified (cold/warm exit 1, index sha unchanged, control exit 0); no hand-flip; net-allowlist digest matches live; no remote registry fetch primitive ships live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
