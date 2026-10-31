def unit_config(uid: str) -> dict:
    u = CAT_BY_ID[uid]
    pdir = REPO / "command-center/p2-wave/probes" / uid
    p1 = sorted(pdir.glob("probe1*.py"))
    p2 = sorted(pdir.glob("probe2*.py"))

    def pick(paths):
        named = [x for x in paths if x.name not in ("probe1.py", "probe2.py")]
        if named:
            return named[0]
        return paths[0] if paths else None

    a, b = pick(p1), pick(p2)
    probes = []
    for x in (a, b):
        if x is None:
            continue
        probes.append("PYTHONDONTWRITEBYTECODE=1 python3 -B "
                      + x.relative_to(REPO).as_posix())
    anchors = [i for i in (u.get("inputs") or [])
               if isinstance(i, str) and "_USER-PROMPTS" in i]
    anchor = anchors[0] if anchors else ("WORK-UNIT-CATALOG.json#" + uid)
    return {
        "artifact": str(u.get("output_path") or "").replace(chr(92), "/"),
        "schema": str(u.get("output_schema") or "").replace(chr(92), "/"),
        "probes": probes,
        "anchor": anchor,
        "retry_policy": str(u.get("retry_policy") or "two-strikes-then-pivot"),
        "report_kind": REPORT_KIND.get(uid),
        "self_rows_ok": uid == "CNL-0076",
    }


REPORT_KIND = {
    "CNF-0173": "confirmation-record",
    "CNF-0177": "confirmation-record",
    "CNF-0178": "confirmation-record",
    "CNF-0180": "confirmation-record",
    "CNF-0188": "program-gate-report",
    "CNL-0076": "councilspec-v2",
    "IMP-0003": None,
    "IMP-0013": None,
    "IMP-0018": None,
    "IMP-0020": None,
    "IMP-0022": None,
}
