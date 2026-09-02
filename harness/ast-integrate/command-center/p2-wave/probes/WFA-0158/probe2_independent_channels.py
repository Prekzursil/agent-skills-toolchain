#!/usr/bin/env python3
"""Probe 2: independent channel parse plus fence-off / drop controls.

Does not use split_channels (### headings). Uses split_channels_independent
(first <<<UNTRUSTED-DATA fence). Re-renders live. If the foundry artifact
exists, re-parses each recorded prompt_verbatim with the same independent
splitter. Fence-off must fire canaries (test has teeth). Drop mutant must
fail content survival.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import payloads as P  # noqa: E402
import quarantine as Q  # noqa: E402

OUT = (
    REPO
    / "command-center/foundry/WFA-0158-prompt-injection-quarantine-for-ingested-third-party.json"
)


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0158-probe2 {msg}")
    return 1


def main() -> int:
    live_ok = []
    for payload in P.hostile():
        trial = Q.run_trial(
            payload, fence=True, drop=False, splitter=Q.split_channels_independent
        )
        print(
            f"independent id={trial['payload_id']} neutralized={trial['neutralized']} "
            f"survived={trial['content_survived']} inst_canary={trial['canary_in_instruction']} "
            f"data_canary={trial['canary_in_data']} fired={trial['fired_canaries']}"
        )
        if not Q.verdict_ok(trial):
            return fail(f"independent splitter rejected {payload['id']}")
        author = Q.run_trial(payload, fence=True, drop=False, splitter=Q.split_channels)
        if author["canary_in_instruction"] != trial["canary_in_instruction"]:
            return fail(f"splitter disagreement on instruction canary {payload['id']}")
        if author["content_survived"] != trial["content_survived"]:
            return fail(f"splitter disagreement on survival {payload['id']}")
        live_ok.append(payload["id"])

    clean = Q.run_trial(
        P.by_id("clean"), fence=True, drop=False, splitter=Q.split_channels_independent
    )
    if clean["fired_canaries"] or not clean["content_survived"]:
        return fail("independent splitter failed clean control")

    off_fired = []
    for payload in P.hostile():
        off = Q.run_trial(
            payload, fence=False, drop=False, splitter=Q.split_channels_independent
        )
        if payload["canary"] in off["fired_canaries"] or off["canary_in_instruction"]:
            off_fired.append(payload["id"])
        print(
            f"fence_off id={payload['id']} fired={off['fired_canaries']} "
            f"in_inst={off['canary_in_instruction']}"
        )
    if len(off_fired) < 5:
        return fail(f"fence-off did not fire enough canaries: {off_fired}")

    drop = Q.run_trial(
        P.by_id("direct-override"),
        fence=True,
        drop=True,
        splitter=Q.split_channels_independent,
    )
    if drop["content_survived"] or not drop["dropped"]:
        return fail("drop mutant passed independent survival check")

    artifact_checked = False
    if OUT.is_file():
        doc = json.loads(OUT.read_text(encoding="utf-8"))
        recorded = {
            t["payload_id"]: t
            for t in (doc.get("trials") or [])
            if isinstance(t, dict) and t.get("payload_id")
        }
        for pid in live_ok:
            rec = recorded.get(pid)
            if not isinstance(rec, dict):
                return fail(f"artifact missing trial {pid}")
            prompt = rec.get("prompt_verbatim") or ""
            if not prompt:
                return fail(f"artifact trial {pid} prompt_verbatim empty")
            ch = Q.split_channels_independent(prompt)
            canary = P.by_id(pid)["canary"]
            if canary in Q.canaries_in(ch["instruction"]):
                return fail(f"artifact prompt {pid} still has canary in instruction")
            if canary not in Q.canaries_in(ch["data"]):
                return fail(f"artifact prompt {pid} lost canary reachability in data")
            if not Q.content_survived(ch["data"]):
                return fail(f"artifact prompt {pid} lost legitimate content")
        artifact_checked = True

    print(
        json.dumps(
            {
                "probe": "probe2-independent-channels",
                "unit_id": "WFA-0158",
                "independent_ok": live_ok,
                "fence_off_fired": off_fired,
                "drop_mutant_rejected": True,
                "artifact_reparsed": artifact_checked,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"reviewer_independent=True disagreements=0 fence_off_fired={len(off_fired)} "
        f"artifact_reparsed={artifact_checked}"
    )
    print("SUCCESS:WFA-0158-probe2 independent channel parse agrees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
