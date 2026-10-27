def floor_enforcement_matrix() -> dict:
    rows = {}
    for cls in RISK_CLASSES:
        floor = FLOORS[cls]
        below = {}
        rejected = []
        for dim in floor:
            cfg = dict(floor)
            if dim == "evidence_standard":
                idx = EVIDENCE_TIER_RANK[str(floor[dim])]
                lower = EVIDENCE_TIERS[idx - 1]
                if idx < 1:
                    lower = EVIDENCE_TIERS[0]
                cfg[dim] = lower
            else:
                need = int(floor[dim])
                if need > 0:
                    cfg[dim] = need - 1
                else:
                    cfg[dim] = 0
            verdict = at_floor(cfg, cls)
            below[dim] = verdict.as_dict()
            if verdict.blocked:
                rejected.append(dim)
        entry = {}
        entry["floor"] = dict(floor)
        entry["at_floor_accepted"] = at_floor(dict(floor), cls).accepted
        entry["one_below"] = below
        entry["rejected_dims"] = rejected
        rows[cls] = entry
    return rows


def matrix_is_sound(matrix: dict) -> bool:
    if matrix is None:
        return False
    if len(matrix) != len(RISK_CLASSES):
        return False
    for cls in RISK_CLASSES:
        row = matrix.get(cls)
        if row is None:
            return False
        if row.get("at_floor_accepted") is not True:
            return False
        dims = sorted(row.get("one_below") or {})
        if sorted(row.get("rejected_dims") or []) != dims:
            return False
    ordered = list(RISK_CLASSES)
    for i in range(len(ordered) - 1):
        low = FLOORS[ordered[i]]
        high = FLOORS[ordered[i + 1]]
        for dim in ("protocol_strength", "quorum", "reviewer_count"):
            if int(low[dim]) > int(high[dim]):
                return False
        lo_ev = EVIDENCE_TIER_RANK[str(low["evidence_standard"])]
        hi_ev = EVIDENCE_TIER_RANK[str(high["evidence_standard"])]
        if lo_ev > hi_ev:
            return False
    return True
