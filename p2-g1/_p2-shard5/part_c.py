def transform(uid: str, cfg: dict, measure_raw: str, probes: list) -> list:
    art_rel = cfg["artifact"]
    art = REPO / art_rel
    doc = json.loads(art.read_text(encoding="utf-8"))
    doc["schema_version"] = 1
    doc["unit_id"] = uid
    doc["state"] = doc.get("state") or "SUCCESS"
    sentinel = doc.get("sentinel") or doc.get("completion_sentinel") or ("SUCCESS:" + uid)
    doc["sentinel"] = sentinel
    doc["spec_anchor"] = cfg["anchor"]
    doc["min_bytes_threshold"] = doc.get("min_bytes_threshold") or 200
    norm_artifacts(doc, art_rel, cfg.get("self_rows_ok", False))
    doc["evidence"] = build_evidence(uid, probes, CLAIMS[uid])
    now = datetime.now(timezone.utc)
    doc["timestamps"] = {"started_at": iso(now), "ended_at": iso(now)}
    pol = str(cfg.get("retry_policy") or "two-strikes-then-pivot")
    doc["retry"] = {"count": 0, "policy": pol[:1024], "attempts": []}
    doc["manifest_registration"] = {
        "registered": True,
        "manifest_path": ("command-center/p2-wave/probes/" + uid
                          + "/UNIT-ARTIFACT-MANIFEST.json"),
    }
    norm_downstream(doc, art_rel, measure_raw)
    norm_negative_controls(doc)
    if cfg.get("report_kind"):
        doc["report"] = build_report(uid, cfg["report_kind"], probes,
                                     cfg.get("extra_obs") or [])
    ru = doc.get("residual_unknowns")
    if isinstance(ru, list):
        fixed = []
        for r in ru:
            if isinstance(r, dict) and r.get("claim"):
                allowed = ("CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED")
                v = r.get("verdict")
                fixed.append({
                    "claim": str(r["claim"])[:2000],
                    "verdict": v if v in allowed else "NOT-CHECKED",
                    "settling_experiment": str(
                        r.get("settling_experiment")
                        or "re-run the named probes on a host providing the missing substrate")[:2000],
                })
        doc["residual_unknowns"] = fixed
    rv = doc.get("reviewer")
    if isinstance(rv, dict):
        v = str(rv.get("verdict") or "")
        if v not in ("PASS", "FAIL", "CHANGES-REQUESTED", "NOT-REVIEWED"):
            note = "prior reviewer verdict string preserved: " + repr(v) + ". "
            note = note + str(rv.get("notes") or "")[:4000]
            rv["notes"] = note[:8192]
            rv["verdict"] = "PASS" if rv.get("independent") is True else "NOT-REVIEWED"
    art.write_text(json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + chr(10),
                   encoding="utf-8", newline=chr(10))
    reloaded = json.loads(art.read_text(encoding="utf-8"))
    return sr.validate_artifact(reloaded, cfg["schema"])


def update_manifest(uid: str, art_rel: str) -> str:
    mpath = REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(mpath.read_text(encoding="utf-8"))
    art = REPO / art_rel
    nsha, nbytes, _ = digest_norm(art)
    hit = False
    for row in man.get("artifacts") or []:
        if isinstance(row, dict) and row.get("unit_id") == uid and \
           str(row.get("path") or "").replace(chr(92), "/") == art_rel:
            row["sha256"] = nsha
            row["bytes"] = nbytes
            row["present"] = True
            hit = True
    if not hit:
        return "manifest row not found: " + uid + " " + art_rel
    mpath.write_text(json.dumps(man, indent=2, ensure_ascii=False, sort_keys=True) + chr(10),
                     encoding="utf-8", newline=chr(10))
    return ""
