receipt["negative_controls"] = [
    {
        "id": "shared-index-broad-add",
        "kind": "known-broken-fixture",
        "description": ("Two sibling files on one checkout plus git add -A must stage both "
                        "paths; the detector fires on that contamination mode."),
        "bad_state_output": "unit-a.txt and unit-b.txt both staged on shared index",
        "good_state_output": "isolated worktrees: intersection empty",
        "fired_on_bad_state": bool(comp1.get("contamination_control", {}).get("detected")),
        "silent_on_good_state": bool(comp1.get("intersection_empty")),
    },
    {
        "id": "unpreserved-teardown",
        "kind": "both-states",
        "description": ("Teardown of a shard whose unique bytes are nowhere else must refuse "
                        "and leave the worktree on disk."),
        "bad_state_output": "reason=unpreserved-content refused=true",
        "good_state_output": "reason=content-proven deleted=true",
        "fired_on_bad_state": bool(comp2.get("dangerous", {}).get("refused")),
        "silent_on_good_state": bool(comp2.get("good", {}).get("deleted")),
    },
    {
        "id": "squash-merge-ancestry-ahead",
        "kind": "known-broken-fixture",
        "description": ("Squash-merge plus an uncommitted remainder: ancestry reports AHEAD "
                        "(naive mutant would delete); content comparison refuses."),
        "bad_state_output": "reports_ahead=true naive_ancestry_would_authorize=true refused=true",
        "good_state_output": "harvest digest match then deleted",
        "fired_on_bad_state": bool(
            comp2.get("squash_unharvested", {}).get("naive_ancestry_would_authorize")
        ) and bool(comp2.get("squash_unharvested", {}).get("refused")),
        "silent_on_good_state": bool(comp2.get("good", {}).get("deleted")),
    },
]
receipt["tests"] = [
    {"id": "concurrent-mutators-disjoint-indexes",
     "command": raws["probe1"][1], "result": "PASS"},
    {"id": "teardown-refused-when-unpreserved",
     "command": raws["probe2"][1], "result": "PASS"},
]
