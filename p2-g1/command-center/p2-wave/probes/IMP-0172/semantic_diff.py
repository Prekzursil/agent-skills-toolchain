"""IMP-0172: semantic diff of two workflows over aligned stages, roles, gates,
tools and edges. Two-directional verdicts: IDENTICAL / LEFT-AHEAD / RIGHT-AHEAD
/ DIVERGED. The one-directional mutant mode is carried ONLY as the recorded
counterexample: it drops left-unique content and reports RIGHT-AHEAD.

Antisymmetry: reverse(diff(a, b)) == diff(b, a), always.
"""
from __future__ import annotations


def _pair_diff(xs, ys, op_removed, op_added):
    sx, sy = [tuple(sorted(map(str, x))) for x in xs], [tuple(sorted(map(str, y))) for y in ys]
    ops = []
    for x in xs:
        if tuple(sorted(map(str, x))) not in sy:
            ops.append({"op": op_removed, "value": x})
    for y in ys:
        if tuple(sorted(map(str, y))) not in sx:
            ops.append({"op": op_added, "value": y})
    return ops


def _stage_shape(stage: dict) -> tuple:
    return (
        tuple(sorted(stage.get("roles") or [])),
        tuple(sorted(stage.get("tools") or [])),
        tuple(sorted(stage.get("gates") or [])),
    )


def diff_workflows(left: dict, right: dict, one_directional: bool = False) -> dict:
    ops = []
    # Stages align by NAME first. A stage name unique to one side is a semantic
    # remove/add unless an unpaired stage of the SAME SHAPE exists on the other
    # side - that is a pure rename, a semantic no-op (recorded, never counted).
    ls, rs = list(left.get("stages") or []), list(right.get("stages") or [])
    used_r = set()
    pairs_by_name = []
    for s in ls:
        match = next((i for i, t2 in enumerate(rs)
                      if i not in used_r and t2.get("name") == s.get("name")), None)
        if match is not None:
            used_r.add(match)
            pairs_by_name.append((s, rs[match]))
    left_only = [s for s in ls if not any(p[0] is s for p in pairs_by_name)]
    right_only = [t2 for i, t2 in enumerate(rs) if i not in used_r]
    for s in left_only:
        twin = next((t2 for t2 in right_only if _stage_shape(t2) == _stage_shape(s)), None)
        if twin is not None:
            right_only.remove(twin)
            ops.append({"op": "renamed_stage", "value": [s.get("name"), twin.get("name")]})
        else:
            ops.append({"op": "removed_stage", "value": s.get("name")})
            # An unmatched stage takes its contents with it: enumerate them so
            # the diff says WHAT was lost, not just that a stage vanished.
            ops += [{"op": "removed_role", "value": r} for r in sorted(s.get("roles") or [])]
            ops += [{"op": "removed_tool", "value": tl} for tl in sorted(s.get("tools") or [])]
            ops += [{"op": "removed_gate", "value": g} for g in sorted(s.get("gates") or [])]
    for s in left_only:
        if not any(o["op"] == "renamed_stage" and o["value"][0] == s.get("name") for o in ops):
            pass
    for t2 in list(right_only):
        if any(o["op"] == "renamed_stage" and o["value"][1] == t2.get("name") for o in ops):
            right_only.remove(t2)
            continue
        ops.append({"op": "added_stage", "value": t2.get("name")})
        ops += [{"op": "added_role", "value": r} for r in sorted(t2.get("roles") or [])]
        ops += [{"op": "added_tool", "value": tl} for tl in sorted(t2.get("tools") or [])]
        ops += [{"op": "added_gate", "value": g} for g in sorted(t2.get("gates") or [])]
    for s, t2 in pairs_by_name:
        if s.get("name") != t2.get("name"):
            ops.append({"op": "renamed_stage", "value": [s.get("name"), t2.get("name")]})
        if _stage_shape(s) != _stage_shape(t2):
            ops += _pair_diff(s.get("roles") or [], t2.get("roles") or [],
                              "removed_role", "added_role")
            ops += _pair_diff(s.get("tools") or [], t2.get("tools") or [],
                              "removed_tool", "added_tool")
            ops += _pair_diff(s.get("gates") or [], t2.get("gates") or [],
                              "removed_gate", "added_gate")
    ops += _pair_diff(left.get("roles") or [], right.get("roles") or [],
                      "removed_role", "added_role")
    ops += _pair_diff(left.get("gates") or [], right.get("gates") or [],
                      "removed_gate", "added_gate")
    ops += _pair_diff(left.get("edges") or [], right.get("edges") or [],
                      "removed_edge", "added_edge")

    semantic = [o for o in ops if o["op"] != "renamed_stage"]
    left_unique = sum(1 for o in semantic if o["op"].startswith("removed_"))
    right_unique = sum(1 for o in semantic if o["op"].startswith("added_"))
    if one_directional:
        verdict = "IDENTICAL" if right_unique == 0 and left_unique == 0 else "RIGHT-AHEAD"
    elif left_unique == 0 and right_unique == 0:
        verdict = "IDENTICAL"
    elif right_unique == 0:
        verdict = "LEFT-AHEAD"
    elif left_unique == 0:
        verdict = "RIGHT-AHEAD"
    else:
        verdict = "DIVERGED"
    return {
        "verdict": verdict,
        "left_unique": left_unique,
        "right_unique": right_unique,
        "ops": [o["op"] for o in ops],
        "ops_detail": ops,
    }


def reverse_diff(result: dict) -> dict:
    swap = {"removed_stage": "added_stage", "added_stage": "removed_stage",
            "removed_role": "added_role", "added_role": "removed_role",
            "removed_gate": "added_gate", "added_gate": "removed_gate",
            "removed_tool": "added_tool", "added_tool": "removed_tool",
            "removed_edge": "added_edge", "added_edge": "removed_edge",
            "renamed_stage": "renamed_stage"}
    verdict = {"IDENTICAL": "IDENTICAL", "LEFT-AHEAD": "RIGHT-AHEAD",
               "RIGHT-AHEAD": "LEFT-AHEAD", "DIVERGED": "DIVERGED"}[result["verdict"]]
    return {
        "verdict": verdict,
        "left_unique": result["right_unique"],
        "right_unique": result["left_unique"],
        "ops": [swap[o] for o in result["ops"]],
        "ops_detail": [{"op": swap[o["op"]], "value": o["value"]} for o in result["ops_detail"]],
    }
