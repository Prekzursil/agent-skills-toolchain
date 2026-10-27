import json
d = json.load(open("/tmp/s0_state.json"))
for uid, r in d.items():
    man = r.get("manifest_rows")
    if isinstance(man, list):
        man = man[0] if man else "NO-ROW"
    print(uid, "| art:", r["artifact_exists"], r["artifact_bytes"], "B | ret:", r.get("ret_status"),
          "| man:", json.dumps(man) if not isinstance(man, str) else man,
          "| emit:", ",".join(r.get("emit_scripts") or []))
