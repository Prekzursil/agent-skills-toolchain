"""Resume patch 2/3: build_shard4.py (schema-valid probe rows + NC kinds)."""
from pathlib import Path

W1 = Path.home() / "p2-g1" / "command-center" / "p2-wave" / "probes" / "_shard4_w1"
drv = W1 / "build_shard4.py"
src = drv.read_text(encoding="utf-8")

old_probe_row = '''         "probes": [dict(id=m["id"], command=m["command"], exit_code=m["rc"],
                         raw_output=m["raw"][-400:], method="live-recompute",
                         fingerprint=L.sha_lf_bytes((m["command"] + m["raw"]).encode())) for m in meta]},'''
new_probe_row = '''         "probes": [_probe_row(m) for m in meta]},'''
assert src.count(old_probe_row) == 2, "drv: probe-row block count=%d" % src.count(old_probe_row)
src = src.replace(old_probe_row, new_probe_row)

old_generic_probe = '''"anchor": a, "probes": [dict(id=m["id"], command=m["command"], exit_code=m["rc"],
                                        raw_output=m["raw"][-400:], method=method,
                                        fingerprint=L.sha_lf_bytes((m["command"] + m["raw"]).encode()))
                                   for m in meta]}'''
new_generic_probe = '''"anchor": a, "probes": [_probe_row(m) for m in meta]}'''
assert old_generic_probe in src, "drv: generic probe-row block not found"
src = src.replace(old_generic_probe, new_generic_probe)

helper = '''def _probe_row(m):
    """Schema-valid probe row (platform/schema/receipt.schema.json $defs/probe):
    only role/method/command/raw_output/fingerprint/exit_code allowed; method
    from the enum. probe1 is the positive recomputation (source, live command);
    probe2 is the both-states/mutation battery (verifier, test-run)."""
    return {
        "role": "source" if m["id"] == "probe1" else "verifier",
        "method": "command" if m["id"] == "probe1" else "test-run",
        "command": m["command"],
        "exit_code": m["rc"],
        "raw_output": m["raw"][-400:],
        "fingerprint": L.sha_lf_bytes((m["command"] + m["raw"]).encode()),
    }


def _rows_cc0022(doc, meta):'''
assert "def _rows_cc0022(doc, meta):" in src
src = src.replace("def _rows_cc0022(doc, meta):", helper, 1)

old_kind1 = '''        "kind": "both-states",'''
assert old_kind1 in src, "drv: cc0022 neg kind not found"
src = src.replace(old_kind1, '''        "kind": "known-broken-fixture",''')

old_kind2 = '''        "kind": "both-states+mutation",'''
assert old_kind2 in src, "drv: generic neg kind not found"
src = src.replace(old_kind2, '''        "kind": "mutation",''')
drv.write_text(src, encoding="utf-8", newline="\n")
print("patched build_shard4.py OK")
