r"""Which ADV units did wf_9cb1a66a-36f actually DISPATCH? Settles the ADV-0002 question.

The spawn prompt of every agent in this wave ends with the literal line

    YOUR WORK UNIT: <UNIT-ID>

so the dispatched set is directly readable from the transcripts -- no inference. This is
mechanically different from "is there a file in the adversarial directory", which is what the
census measures, so the two together separate NOT-DISPATCHED from DISPATCHED-BUT-NO-ARTIFACT.

Also reads the harvest file for its own view, and cross-tabulates all three.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
SESSION = "30bd50d4-5a72-4c19-8fd5-85b6430c7b7d"
WF_ROOT = (
    Path("C:/Users/Prekzursil/.claude/projects/C--Users-Prekzursil")
    / SESSION
    / "subagents"
    / "workflows"
)
ADV = REPO / "command-center" / "adversarial"
OUT = REPO / "command-center" / "casualty"
UNIT_LINE = re.compile(r"YOUR WORK UNIT:\s*([A-Z]+-\d+)")


def load_jsonl(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def first_user_text(recs: list[dict]) -> str:
    for r in recs:
        m = r.get("message")
        role = m.get("role") if isinstance(m, dict) else r.get("role")
        if role != "user":
            continue
        content = m.get("content") if isinstance(m, dict) else None
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(
                b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
            )
    return ""


def main(argv: list[str]) -> int:
    runs = argv or ["wf_9cb1a66a-36f", "wf_18aa91e4-3c1"]
    dispatched: dict[str, list[str]] = {}
    scanned = 0
    for run in runs:
        root = WF_ROOT / run
        if not root.is_dir():
            print(f"  [run missing] {run}")
            continue
        for t in sorted(root.glob("agent-*.jsonl")):
            scanned += 1
            m = UNIT_LINE.search(first_user_text(load_jsonl(t)))
            if m:
                dispatched.setdefault(m.group(1).upper(), []).append(f"{run}/{t.name}")

    # DETECTOR CONTROL: the regex must find the two units we already proved were dispatched,
    # and must NOT invent a unit that has no transcript.
    ctrl_pos = "ADV-0021" in dispatched and "ADV-0022" in dispatched
    ctrl_neg = "ADV-9999" not in dispatched
    print(
        f"CONTROL: positive(finds known-dispatched ADV-0021+ADV-0022)={ctrl_pos} "
        f"negative(does not invent ADV-9999)={ctrl_neg}"
    )
    print(f"transcripts scanned: {scanned}; distinct units dispatched: {len(dispatched)}")

    on_disk = {}
    for f in ADV.glob("*.json"):
        m = re.match(r"(ADV-\d+)", f.name)
        if m:
            on_disk[m.group(1)] = f.stat().st_size

    adv_dispatched = {k: v for k, v in dispatched.items() if k.startswith("ADV-")}
    print(f"\nADV units DISPATCHED in these runs: {len(adv_dispatched)}")
    print(f"ADV artifacts ON DISK now:          {len(on_disk)}")

    only_disk = sorted(set(on_disk) - set(adv_dispatched))
    only_disp = sorted(set(adv_dispatched) - set(on_disk))
    print(f"\nDISPATCHED but NO artifact on disk: {only_disp or '(none)'}")
    print(f"artifact on disk but NOT dispatched in these runs: {only_disk or '(none)'}")

    # the specific question
    for uid in ("ADV-0002", "ADV-0038", "ADV-0041"):
        print(
            f"\n{uid}: dispatched={uid in adv_dispatched} "
            f"({adv_dispatched.get(uid, 'no transcript')}) artifact_on_disk={uid in on_disk}"
        )

    payload = {
        "runs_scanned": runs,
        "transcripts_scanned": scanned,
        "control": {"positive": ctrl_pos, "negative": ctrl_neg},
        "adv_dispatched": {k: adv_dispatched[k] for k in sorted(adv_dispatched)},
        "adv_on_disk_bytes": {k: on_disk[k] for k in sorted(on_disk)},
        "dispatched_no_artifact": only_disp,
        "artifact_not_dispatched_here": only_disk,
    }
    (OUT / "ADV-DISPATCH-CENSUS.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if not (ctrl_pos and ctrl_neg):
        print("FAILED:dispatch detector control failed -- numbers above may not be cited")
        return 1
    print("\nSUCCESS:dispatch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
