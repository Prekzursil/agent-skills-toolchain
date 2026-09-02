#!/usr/bin/env python3
"""Probe 2: live tag dereference vs git rev-list -n 1, plus caret both-states.

Signal (b): peeled commit == rev-list. Bad state: cmd/pwsh mangle yields a
WRONG object or git error. Good state: quoted peel and rev-list agree.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import live as L  # noqa: E402

ART = REPO / "command-center/receipts/TST-0188.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0188-probe2 {msg}")
    return 1


def main() -> int:
    result = L.run_live()
    if not result.get("parent_differs_from_head"):
        return fail("HEAD and HEAD^ fixture collapsed; control is unfalsifiable")
    if not result.get("annotated_tag_differs_from_commit"):
        return fail("annotated tag object equals commit; peel control is unfalsifiable")
    if not result.get("head_caret_wrong_object"):
        return fail("cmd caret-escape of HEAD^ did not resolve to the wrong object")
    if not result.get("cmd_peel_errored"):
        return fail("cmd caret-escape of tag^{commit} did not error")
    if not result.get("pwsh_peel_wrong_or_errored"):
        return fail("pwsh script-block eat of tag^{commit} was not wrong/errored")
    if not result.get("sanctioned_match"):
        return fail("quoted peel != git rev-list -n 1 <tag>")
    if not result.get("pass"):
        return fail("live bundle did not pass")

    objs = result["objects"]
    if objs["via_list"] != objs["peeled"]:
        return fail("rev-list and peeled commit disagree")
    if objs["via_list"] == objs["tag_obj"]:
        return fail("rev-list returned the tag object, not the commit")
    pwsh_seen = (result["results"].get("pwsh_peel_sha") or "")
    if result["results"].get("pwsh_peel_rc") == 0 and pwsh_seen == objs["peeled"]:
        return fail("pwsh-mangled peel still returned the commit")
    if result["results"].get("pwsh_peel_rc") == 0 and pwsh_seen != objs["tag_obj"]:
        return fail("pwsh-mangled peel did not resolve to the annotated tag object")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        pub = ((doc.get("evidence") or {}).get("live_deref") or {})
        if pub.get("sanctioned_match") is not True:
            return fail("receipt sanctioned_match is not true")
        if pub.get("head_caret_wrong_object") is not True:
            return fail("receipt missing HEAD^ wrong-object control")
        if pub.get("cmd_peel_errored") is not True:
            return fail("receipt missing cmd peel error control")
        if pub.get("pwsh_peel_wrong_or_errored") is not True:
            return fail("receipt missing pwsh peel wrong-object control")
        if pub.get("rev_list_sha") and pub.get("rev_list_sha") == pub.get("tag_obj_sha"):
            return fail("receipt recorded rev-list == tag object")
        if pub.get("peeled_sha") and pub.get("peeled_sha") != pub.get("rev_list_sha"):
            return fail("receipt peeled_sha != rev_list_sha")

    summary = {
        "probe": "probe2-live-deref",
        "unit_id": "TST-0188",
        "rev_list_sha": objs["via_list"],
        "peeled_sha": objs["peeled"],
        "tag_obj_sha": objs["tag_obj"],
        "head_sha": objs["head"],
        "parent_sha": objs["parent"],
        "pwsh_binary": result["pwsh_binary"],
        "head_caret_wrong_object": True,
        "cmd_peel_errored": True,
        "pwsh_peel_wrong_or_errored": True,
        "sanctioned_match": True,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"rev-list={objs['via_list'][:12]} peeled={objs['peeled'][:12]} "
        f"tag_obj={objs['tag_obj'][:12]} pwsh={result['pwsh_binary']!r} "
        f"HEAD^_wrong=True peel_cmd_error=True"
    )
    print("SUCCESS:TST-0188-probe2 live deref matches rev-list; caret form is wrong")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
