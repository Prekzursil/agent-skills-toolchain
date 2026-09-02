r"""ADV-0002 RE-CHECK. A ripgrep sweep over ALL 1,064 transcripts in this session found the
literal string 'YOUR WORK UNIT: ADV-0002' in 4 files, while the round-1 python census
(2 runs, 100 transcripts) reported dispatched=False. Two probes disagree -> resolve from the
raw source, never by picking one.

The census reads the spawn prompt of the transcript's OWN first user message. ripgrep matches
the token ANYWHERE in the file, including inside a tool_result where one agent was READING
another agent's prompt, or inside an agent's own analysis text. That is the use-vs-mention
distinction; this script classifies every hit by WHERE it sits.
"""

from __future__ import annotations

import json
from pathlib import Path

SESSION = Path(
    "C:/Users/Prekzursil/.claude/projects/C--Users-Prekzursil"
    "/30bd50d4-5a72-4c19-8fd5-85b6430c7b7d/subagents"
)
NEEDLE = "YOUR WORK UNIT: ADV-0002"

PROJECTS = Path("C:/Users/Prekzursil/.claude/projects")


def rg_files(pattern: str, root: Path) -> list[str]:
    """Mechanically different from the python census: ripgrep over EVERY transcript of EVERY
    project on this machine, not the census's two named runs."""
    import subprocess

    r = subprocess.run(
        ["rg", "-l", "--no-messages", pattern, str(root)],
        capture_output=True,
        text=True,
    )
    return sorted(x.strip() for x in r.stdout.splitlines() if x.strip())


def rg_count(pattern: str, root: Path) -> int:
    import subprocess

    r = subprocess.run(
        ["rg", "-o", "--no-filename", "--no-messages", pattern, str(root)],
        capture_output=True,
        text=True,
    )
    return len([x for x in r.stdout.splitlines() if x.strip()])


HITS = [
    str(Path(p).resolve()) for p in rg_files(r"YOUR WORK UNIT:\s*ADV-0002\b", PROJECTS)
]


def classify(rel: str) -> dict:
    p = Path(rel) if Path(rel).is_absolute() else SESSION / rel
    out = {
        "file": str(p),
        "records_with_needle": [],
        "first_user_message_is_a_dispatch": None,
        "own_unit_from_first_user_message": None,
    }
    first_user_text = None
    with open(p, "r", encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh, 1):
            try:
                rec = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            msg = rec.get("message") or {}
            role = msg.get("role") or rec.get("type")
            content = msg.get("content")
            text = ""
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                parts = []
                for c in content:
                    if isinstance(c, dict):
                        if isinstance(c.get("text"), str):
                            parts.append(c["text"])
                        if isinstance(c.get("content"), str):
                            parts.append(c["content"])
                        elif isinstance(c.get("content"), list):
                            for cc in c["content"]:
                                if isinstance(cc, dict) and isinstance(
                                    cc.get("text"), str
                                ):
                                    parts.append(cc["text"])
                text = "\n".join(parts)
            if first_user_text is None and role == "user" and text.strip():
                first_user_text = text
            if NEEDLE in text:
                idx = text.index(NEEDLE)
                is_tool_result = any(
                    isinstance(c, dict) and c.get("type") == "tool_result"
                    for c in (content if isinstance(content, list) else [])
                )
                out["records_with_needle"].append(
                    {
                        "line": i,
                        "role": role,
                        "inside_tool_result": is_tool_result,
                        "excerpt": text[max(0, idx - 160) : idx + 90].replace(
                            "\n", " | "
                        )[-260:],
                    }
                )
    if first_user_text:
        marker = "YOUR WORK UNIT:"
        if marker in first_user_text:
            j = first_user_text.index(marker)
            own = (
                first_user_text[j + len(marker) : j + len(marker) + 12]
                .strip()
                .split()[0]
            )
            out["own_unit_from_first_user_message"] = own
            out["first_user_message_is_a_dispatch"] = True
        else:
            out["first_user_message_is_a_dispatch"] = False
    return out


def main() -> int:
    results = [classify(h) for h in HITS]
    dispatched_as_own = [
        r
        for r in results
        if (r["own_unit_from_first_user_message"] or "").startswith("ADV-0002")
        and (r["own_unit_from_first_user_message"] or "") == "ADV-0002"
    ]
    for r in results:
        print(f"\n=== {r['file']}")
        print(
            f"  first user message is a dispatch: {r['first_user_message_is_a_dispatch']}  "
            f"OWN unit = {r['own_unit_from_first_user_message']}"
        )
        for h in r["records_with_needle"]:
            print(
                f"  line {h['line']:>5} role={h['role']} inside_tool_result={h['inside_tool_result']}"
            )
            print(f"        ...{h['excerpt']}...")

    # DETECTOR CONTROL (both states). The same pattern with the wildcard id must FIND the
    # known-dispatched units, otherwise a zero for ADV-0002 measures nothing.
    ctrl_any = rg_count(r"YOUR WORK UNIT:\s*ADV-\d{4}\b", PROJECTS)
    ctrl_files = len(rg_files(r"YOUR WORK UNIT:\s*ADV-\d{4}\b", PROJECTS))
    ctrl_0021 = rg_count(r"YOUR WORK UNIT:\s*ADV-0021\b", PROJECTS)
    n_0038 = rg_count(r"YOUR WORK UNIT:\s*ADV-0038\b", PROJECTS)

    print("\n----------------------------------------------------------------------")
    print(
        f"DETECTOR CONTROL: 'YOUR WORK UNIT: ADV-<any>' -> {ctrl_any} occurrences in "
        f"{ctrl_files} files; ADV-0021 alone -> {ctrl_0021}. The matcher finds known-present "
        f"dispatch markers, so a zero is a real absence."
    )
    print(f"ADV-0038 occurrences anywhere under {PROJECTS}: {n_0038}")
    print(f"files whose OWN spawn prompt dispatches ADV-0002: {len(dispatched_as_own)}")
    ok_ctrl = ctrl_any > 0 and ctrl_0021 > 0
    verdict = (
        "DETECTOR BROKEN - control found no known dispatch"
        if not ok_ctrl
        else "REFUTED - ADV-0002 WAS dispatched"
        if dispatched_as_own
        else "UPHELD (and WIDENED) - every occurrence anywhere in ~/.claude/projects is a "
        "MENTION; no transcript carries ADV-0002 as its own dispatched unit"
    )
    print(f"VERDICT: {verdict}")

    out = Path(
        "C:/Users/Prekzursil/source/ast-integrate/command-center/casualty"
        "/R2-ADV0002-RECHECK.json"
    )
    out.write_text(
        json.dumps(
            {
                "generated_at_utc": __import__("datetime")
                .datetime.now(__import__("datetime").timezone.utc)
                .isoformat(),
                "needle": NEEDLE,
                "ripgrep_scope": f"EVERY *.jsonl under {PROJECTS} -- every session of every project on "
                f"this machine, not only the wave's two runs",
                "python_census_scope": "2 runs (wf_9cb1a66a-36f, wf_18aa91e4-3c1), 100 transcripts",
                "results": results,
                "files_dispatching_ADV-0002_as_their_own_unit": len(dispatched_as_own),
                "detector_control": {
                    "any_adv_dispatch_marker_occurrences": ctrl_any,
                    "any_adv_dispatch_marker_files": ctrl_files,
                    "adv_0021_occurrences": ctrl_0021,
                    "control_passes": ok_ctrl,
                },
                "adv_0038_occurrences_anywhere": n_0038,
                "residual_inline": (
                    "this widening assumes a dispatch always carries the literal "
                    "'YOUR WORK UNIT:' marker. It held 40/40 for this wave (perfect "
                    "1:1 dispatch-to-artifact), but a launcher using a different "
                    "template would be invisible to BOTH probes. Settling experiment: "
                    "read the workflow launcher that composes the spawn prompt and "
                    "confirm the marker is unconditional."
                ),
                "verdict": verdict,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
