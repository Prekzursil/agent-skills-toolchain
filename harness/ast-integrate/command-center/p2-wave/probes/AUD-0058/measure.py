"""Live census + both-states controls for AUD-0058.

Probe 1 consumes the frontmatter classifier.
Probe 2 consumes the turn-zero context bag.
When they disagree, the bag wins.
"""
from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path
from typing import Any

from classifier import classify_tree
from common import (
    ALWAYS_ON_MARKER,
    BARE_MARKER,
    DEMOTED_MARKER,
    HERE,
    LAZY_MARKER,
    REPO,
)
from fixtures import ensure_fixtures
from frontmatter import split_frontmatter
from inventory import grok_inspect_available, host_skill_trees, repo_skill_tree
from loader import as_record, load_turn_zero, naive_wrong_class


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def disagreement_rows(trace) -> list[dict[str, Any]]:
    rows = []
    for cap in trace.capabilities:
        declared = cap.declared_load_class
        measured = "ALWAYS-ON" if cap.cap_id in trace.injected_bodies else "LAZY"
        if trace.touched_path is not None and cap.cap_id in trace.injected_bodies:
            if cap.declared_load_class == "LAZY":
                measured = "INJECTED-ON-TOUCH"
        naive = naive_wrong_class(cap)
        winner = "agree"
        if declared != measured and measured != "INJECTED-ON-TOUCH":
            winner = "measurement"
        rows.append(
            {
                "id": cap.cap_id,
                "rel_path": cap.rel_path,
                "kind": cap.kind,
                "has_frontmatter": cap.frontmatter is not None,
                "paths_key_present": cap.paths_present,
                "declared_load_class": declared,
                "measured_load_class": (
                    "ALWAYS-ON"
                    if cap.cap_id in trace.injected_bodies and trace.touched_path is None
                    else (
                        "LAZY"
                        if cap.cap_id not in trace.injected_bodies
                        else "INJECTED-ON-TOUCH"
                    )
                ),
                "naive_wrong_class": naive,
                "naive_disagrees": naive != (
                    "ALWAYS-ON"
                    if cap.cap_id in trace.injected_bodies and trace.touched_path is None
                    else "LAZY"
                    if cap.cap_id not in trace.injected_bodies
                    else naive
                ),
                "declared_vs_measured": winner,
            }
        )
    return rows


def demote_always_on(skill_md: Path) -> None:
    text = skill_md.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    if fm is None:
        raise SystemExit("FAILED:AUD-0058 always-on control had no frontmatter")
    if "paths" in fm:
        raise SystemExit("FAILED:AUD-0058 always-on control already had paths")
    fence = "---\n"
    for k, v in fm.items():
        fence += f"{k}: {v}\n"
    fence += 'paths:\n  - "**/*"\n---\n'
    skill_md.write_text(fence + "\n" + body.lstrip("\n"), encoding="utf-8", newline="\n")


def fixture_controls() -> dict[str, Any]:
    src = ensure_fixtures()
    tmp = Path(tempfile.mkdtemp(prefix="aud-0058-scratch-"))
    try:
        dest = tmp / "tree"
        shutil.copytree(src, dest)
        t0 = load_turn_zero(dest)
        rec0 = as_record(t0)
        always_on_in_bag = t0.body_contains("always-on", ALWAYS_ON_MARKER)
        bare_in_bag = t0.body_contains(
            "rules.common.no-frontmatter.md", BARE_MARKER
        )
        lazy_out = LAZY_MARKER not in t0.injected_bodies.get("lazy-scoped", "")
        demoted_out = DEMOTED_MARKER not in t0.injected_bodies.get(
            "demoted-star", ""
        )
        instrument_names_always_on = bool(t0.always_on_ids)
        empty_always_on_rejected = instrument_names_always_on
        naive_rows = disagreement_rows(t0)
        naive_loses = any(r["naive_disagrees"] for r in naive_rows)

        demote_always_on(dest / "always-on" / "SKILL.md")
        t1 = load_turn_zero(dest)
        demoted = (
            "always-on" not in t1.injected_bodies
            and "always-on" in t1.lazy_ids
            and "always-on" in t1.index_cards
            and not t1.body_contains("always-on", ALWAYS_ON_MARKER)
        )
        still_out_without_touch = "always-on" not in t1.injected_bodies

        t2 = load_turn_zero(dest, touched_path="src/app.py")
        lazy_on_touch = t2.body_contains("lazy-scoped", LAZY_MARKER)
        demoted_on_star_touch = t2.body_contains("always-on", ALWAYS_ON_MARKER)

        classified = classify_tree(src)
        by_id = {r["id"]: r for r in classified}
        declared_always = by_id["always-on"]["declared_load_class"] == "ALWAYS-ON"
        declared_lazy = by_id["lazy-scoped"]["declared_load_class"] == "LAZY"
        declared_bare = (
            by_id["rules.common.no-frontmatter.md"]["declared_load_class"]
            == "ALWAYS-ON"
        )
        declared_demoted = by_id["demoted-star"]["declared_load_class"] == "LAZY"
        declared_bare_no_fm = (
            by_id["rules.common.no-frontmatter.md"]["has_frontmatter"] is False
        )

        ok = (
            always_on_in_bag
            and bare_in_bag
            and lazy_out
            and demoted_out
            and instrument_names_always_on
            and empty_always_on_rejected
            and naive_loses
            and demoted
            and still_out_without_touch
            and lazy_on_touch
            and demoted_on_star_touch
            and declared_always
            and declared_lazy
            and declared_bare
            and declared_demoted
            and declared_bare_no_fm
        )
        return {
            "pass": ok,
            "turn0": rec0,
            "classified": classified,
            "disagreements": naive_rows,
            "always_on_in_bag": always_on_in_bag,
            "bare_rule_in_bag": bare_in_bag,
            "lazy_body_absent_at_t0": lazy_out,
            "demoted_star_absent_at_t0": demoted_out,
            "instrument_named_always_on": instrument_names_always_on,
            "empty_always_on_set_rejected": empty_always_on_rejected,
            "naive_inference_loses_to_measurement": naive_loses,
            "demoted_by_paths_star": demoted,
            "star_glob_still_lazy_at_t0": still_out_without_touch,
            "lazy_injected_on_src_touch": lazy_on_touch,
            "demoted_star_injects_on_any_touch": demoted_on_star_touch,
            "declared_always_on": declared_always,
            "declared_lazy": declared_lazy,
            "declared_bare_always_on": declared_bare,
            "declared_demoted_lazy": declared_demoted,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def live_census() -> dict[str, Any]:
    trees = host_skill_trees()
    repo = repo_skill_tree()
    repo_rows = classify_tree(repo) if repo.is_dir() else []
    live_present = [t for t in trees if t["role"] == "live" and t["is_dir"]]
    live_rows: list[dict[str, Any]] = []
    live_traces: list[dict[str, Any]] = []
    for t in live_present:
        root = Path(t["path"])
        live_rows.extend(
            [{**r, "tree": t["path"]} for r in classify_tree(root)]
        )
        trace = load_turn_zero(root)
        live_traces.append({"tree": t["path"], **as_record(trace)})

    repo_trace = load_turn_zero(repo) if repo.is_dir() else None
    repo_disagreements = []
    repo_demoted = []
    if repo_trace is not None:
        for cap in repo_trace.capabilities:
            declared = cap.declared_load_class
            measured = (
                "ALWAYS-ON"
                if cap.cap_id in repo_trace.injected_bodies
                else "LAZY"
            )
            if declared != measured:
                repo_disagreements.append(
                    {
                        "id": cap.cap_id,
                        "declared": declared,
                        "measured": measured,
                        "winner": "measurement",
                    }
                )
            if cap.kind == "skill" and cap.paths_present:
                repo_demoted.append(
                    {
                        "id": cap.cap_id,
                        "rel_path": cap.rel_path,
                        "path_globs": cap.path_globs,
                    }
                )

    no_fm = [r for r in repo_rows if not r["has_frontmatter"]]
    injected_ids = repo_trace.injected_ids() if repo_trace else []
    catalog_eight_instantiated = (
        len(no_fm) == 8 and set(r["id"] for r in no_fm) == set(injected_ids)
    )
    return {
        "trees": trees,
        "repo_present": repo.is_dir(),
        "repo_skill_md_count": sum(1 for r in repo_rows if r["kind"] == "skill"),
        "repo_rows": repo_rows,
        "repo_turn0": as_record(repo_trace) if repo_trace else None,
        "repo_disagreements": repo_disagreements,
        "repo_skills_with_paths": repo_demoted,
        "repo_no_frontmatter": no_fm,
        "repo_no_frontmatter_count": len(no_fm),
        "catalog_eight_no_frontmatter_instantiated": catalog_eight_instantiated,
        "live_trees_present": live_present,
        "live_rows": live_rows,
        "live_traces": live_traces,
        "grok_inspect": grok_inspect_available(),
        "fixture_root": str(HERE / "fixtures" / "estate"),
    }


def run_audit() -> dict[str, Any]:
    controls = fixture_controls()
    live = live_census()
    return {"controls": controls, "live": live, "repo": str(REPO)}
