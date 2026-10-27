def reanchor(uid: str) -> str:
    unit = BYID[uid]
    out_rel = unit["output_path"].replace("\\", "/")
    man_rel = f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json"
    probe_dir = M.PROBES / uid
    receipt_path = REPO / out_rel
    doc = json.loads(receipt_path.read_text(encoding="utf-8"))
    ret = json.loads((probe_dir / "SUBAGENT-RETURN.json").read_text(encoding="utf-8"))
    ref = unit["output_schema"]

    cmds, (rc1, out1), (rc2, out2) = live_probes(uid, ret, probe_dir)
    if rc1 != 0 or rc2 != 0:
        return f"FAILED:shard19-reanchor {uid} live probes rc {rc1}/{rc2}"
    print(f"  {uid}: probes exit 0/0")

    cc = consumer_cmd(uid)
    ext = doc.setdefault("extensions", {})
    prev_state = doc.get("state")
    PLACEHOLDER = "PENDING-ADMISSION-RUN (substituted with the real ACCEPT tail after the consumer executed against v1; final file re-validated inline as the assertion)"

    if uid in DEMOTE:
        reason = str(doc.get("sentinel") or "")
        defect_summ = "; ".join(
            f"{d.get(chr(39)+chr(105)+chr(100)+chr(39)) if False else d.get('id')}({d.get('severity')},{d.get('status')}): {str(d.get('summary'))[:220]}"
            for d in (doc.get("defects") or []) if isinstance(d, dict)
        )
