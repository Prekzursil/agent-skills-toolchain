#!/usr/bin/env python3
"""Named probe 2: public read API must not leak embargoed detail.

Independent of pytest. Greps the serialized public GET/list bodies and the
event-log dump for a unique canary. Negative control: after owner-gated
disclosure the same GET returns the canary.

Also records side-channel observations (existence of a known id, operator log
lifecycle names) without treating those as public-text leaks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.disclosure import DisclosureRegistry, State  # noqa: E402
from marketplace.public_api import get_json, list_json  # noqa: E402

CANARY = "EMBARGO-CANARY-IMP-0100-PROBE2-UNIQUE-7f3c91aa-DO-NOT-LEAK"


def embargo(reg: DisclosureRegistry, package_id: str, detail: str) -> str:
    rec = reg.create(package_id, detail, actor="reporter")
    reg.transition(rec.id, State.TRIAGED, actor="triager")
    reg.transition(rec.id, State.EMBARGOED, actor="triager")
    return rec.id


def hits(hay: str, needle: str) -> int:
    return hay.count(needle)


def main() -> int:
    reg = DisclosureRegistry()
    aid = embargo(reg, "pkg.probe2", CANARY)
    get_before = get_json(reg, aid)
    list_before = list_json(reg)
    log_before = reg.log.dump_text()
    get_hits = hits(get_before, CANARY)
    list_hits = hits(list_before, CANARY)
    log_hits = hits(log_before, CANARY)
    withheld = json.loads(get_before)
    leak_free = get_hits == 0 and list_hits == 0 and log_hits == 0
    withheld_shape = (
        withheld.get("disclosed") is False
        and "detail" not in withheld
        and "state" not in withheld
    )
    listed_empty = json.loads(list_before).get("advisories") == []

    # Negative control: disclose, same GET must contain the canary.
    try:
        reg.transition(aid, State.DISCLOSED, actor="owner", owner_approved=True)
        disclose_ok = True
        disclose_err = None
    except Exception as exc:  # noqa: BLE001
        disclose_ok = False
        disclose_err = f"{type(exc).__name__}:{exc}"
    get_after = get_json(reg, aid) if disclose_ok else ""
    list_after = list_json(reg) if disclose_ok else ""
    after_hits = hits(get_after, CANARY)
    list_after_hits = hits(list_after, CANARY)
    negative_ok = disclose_ok and after_hits >= 1 and list_after_hits >= 1

    # Body-size independence (withheld schema is fixed keys).
    reg2 = DisclosureRegistry()
    short = "CANARY-SHORT-probe2"
    long = "CANARY-LONG-probe2-" + ("Z" * 400)
    a = embargo(reg2, "pkg.a", short)
    b = embargo(reg2, "pkg.b", long)
    ja = json.loads(get_json(reg2, a))
    jb = json.loads(get_json(reg2, b))
    size_ok = set(ja) == {"id", "package_id", "disclosed"} and set(jb) == set(ja)
    size_ok = size_ok and short not in json.dumps(ja) and long not in json.dumps(jb)

    side_channels = {
        "public_get_of_known_id_returns_withheld_stub": True,
        "unpublished_omitted_from_public_list": listed_empty,
        "internal_state_omitted_from_withheld_view": "state" not in withheld,
        "event_log_names_lifecycle_not_detail": log_hits == 0,
        "uuid4_id_not_practically_guessable": True,
        "operator_memory_vault_is_storage_not_public_api": True,
    }

    report = {
        "canary": CANARY,
        "get_hits_before": get_hits,
        "list_hits_before": list_hits,
        "log_hits_before": log_hits,
        "leak_free": leak_free,
        "withheld_shape": withheld_shape,
        "listed_empty_before": listed_empty,
        "disclose_ok": disclose_ok,
        "disclose_err": disclose_err,
        "get_hits_after": after_hits,
        "list_hits_after": list_after_hits,
        "negative_control_ok": negative_ok,
        "size_independent_ok": size_ok,
        "side_channels": side_channels,
        "get_before": get_before,
        "get_after_has_canary": after_hits >= 1,
    }
    print(json.dumps({k: v for k, v in report.items() if k != "canary"}, sort_keys=True))
    # canary printed only as a count, never required in stdout for the leak check
    if not leak_free:
        print("FAILED:IMP-0100-probe2 embargo text leaked before disclose")
        return 1
    if not withheld_shape or not listed_empty:
        print("FAILED:IMP-0100-probe2 withheld shape")
        return 1
    if not negative_ok:
        print("FAILED:IMP-0100-probe2 negative control (post-disclose detail absent)")
        return 1
    if not size_ok:
        print("FAILED:IMP-0100-probe2 withheld body scaled with secret")
        return 1
    print("SUCCESS:IMP-0100-probe2 embargo leak + negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
