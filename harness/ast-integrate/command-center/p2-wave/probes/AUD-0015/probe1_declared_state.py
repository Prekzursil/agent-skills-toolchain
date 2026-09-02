#!/usr/bin/env python3
"""Probe 1: parse four config surfaces and compute declared effective state.

Also runs the both-states scope control (root disable vs per-project disable
must differ) and proves the field-scoped reader does not leak a planted env
secret.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fixtures import SERVER, CWD, build_project_disabled, build_root_disabled  # noqa: E402
from reader import PLANTED_SECRET, leak_hits, load_json_scoped  # noqa: E402
from resolver import resolve_estate  # noqa: E402


def _enabled(estate: dict, name: str):
    rec = (estate.get("by_name") or {}).get(name) or {}
    return rec.get("effective_enabled"), rec


def main() -> int:
    live = resolve_estate(Path.home(), Path("/opt/p2/ast-integrate"))
    live_text = json.dumps(live, sort_keys=True)
    live_leaks = leak_hits(live_text)
    if live_leaks:
        print("FAILED:AUD-0015-probe1 live extract leaked credential-shaped text")
        return 1

    with tempfile.TemporaryDirectory(prefix="aud0015-p1-") as tmp:
        tmp_path = Path(tmp)
        root_estate = build_root_disabled(tmp_path / "root")
        proj_estate = build_project_disabled(tmp_path / "proj")
        cwd = Path(CWD)

        correct_root = resolve_estate(root_estate / "home", cwd)
        correct_proj = resolve_estate(proj_estate / "home", cwd)
        naive_root = resolve_estate(
            root_estate / "home", cwd, treat_root_disable_as_effective=True
        )
        naive_proj = resolve_estate(
            proj_estate / "home", cwd, treat_root_disable_as_effective=True
        )

        cr_en, cr_rec = _enabled(correct_root, SERVER)
        cp_en, cp_rec = _enabled(correct_proj, SERVER)
        nr_en, _ = _enabled(naive_root, SERVER)
        np_en, _ = _enabled(naive_proj, SERVER)

        scoped = load_json_scoped(root_estate / "home" / ".claude" / "settings.json")
        scoped_text = json.dumps(scoped, sort_keys=True)
        wholesale = json.loads(
            (root_estate / "home" / ".claude" / "settings.json").read_text(
                encoding="utf-8"
            )
        )
        wholesale_text = json.dumps(wholesale)
        leak_scoped = leak_hits(scoped_text)
        leak_wholesale = leak_hits(wholesale_text)

        mcp_scoped = load_json_scoped(root_estate / "home" / ".mcp.json")
        mcp_text = json.dumps(mcp_scoped, sort_keys=True)
        mcp_leaks = leak_hits(mcp_text)

    both_states = cr_en != cp_en
    naive_same = nr_en == np_en
    leak_ok = (not leak_scoped) and bool(leak_wholesale) and (not mcp_leaks)
    root_inert = (
        cr_en is True
        and cr_rec.get("root_disabled_listed") is True
        and cr_rec.get("project_disabled") is False
    )
    project_wins = (
        cp_en is False
        and cp_rec.get("project_disabled") is True
        and cp_rec.get("winning_surface", "").startswith("claude.json:projects")
    )
    ok = (
        both_states
        and naive_same
        and leak_ok
        and root_inert
        and project_wins
        and not live_leaks
        and cr_en is True
        and cp_en is False
    )
    result = {
        "unit_id": "AUD-0015",
        "probe": "probe1-declared-state",
        "pass": ok,
        "both_states": both_states,
        "correct_root_enabled": cr_en,
        "correct_project_enabled": cp_en,
        "correct_root_winner": cr_rec.get("winning_surface"),
        "correct_project_winner": cp_rec.get("winning_surface"),
        "naive_root_enabled": nr_en,
        "naive_project_enabled": np_en,
        "naive_answers_identical": naive_same,
        "root_disable_inert": root_inert,
        "project_disable_wins": project_wins,
        "leak_proof": {
            "scoped_settings_clean": not leak_scoped,
            "wholesale_settings_contains_plant": bool(leak_wholesale),
            "scoped_mcp_json_clean": not mcp_leaks,
            "planted_secret_length": len(PLANTED_SECRET),
            "pass": leak_ok,
        },
        "live": {
            "home": str(Path.home()),
            "surfaces": live.get("surfaces"),
            "server_count": len(live.get("servers") or []),
            "server_names": [s.get("name") for s in (live.get("servers") or [])],
            "estate_absent": all(
                (live.get("surfaces") or {}).get(k, {}).get("status")
                in {"ABSENT", None}
                or (live.get("surfaces") or {}).get(k, {}).get("file_status") == "ABSENT"
                for k in ("home_mcp_json", "settings_json")
            )
            and (live.get("surfaces") or {})
            .get("claude_root", {})
            .get("file_status")
            == "ABSENT",
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if not ok:
        print("FAILED:AUD-0015-probe1 declared-state both-states or leak-proof")
        return 1
    print(
        "SUCCESS:AUD-0015-probe1 four surfaces parsed; "
        "root disable inert; per-project disable wins; reader does not leak env"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
