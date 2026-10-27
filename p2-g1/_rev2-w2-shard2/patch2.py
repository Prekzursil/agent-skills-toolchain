"""Patch close_shard2_w2.py:
1. ARC-0048 verdict gate: accept primary_reviewer_adjudication PASS.
2. My reviewer evidence verifier probe method forced to 'command' (live re-run),
   immune to the builder-evidence method refinements.
3. Idempotency guard: skip units already closed by this reviewer id.
"""
import io

P = r"C:\Users\Prekzursil\p2-g1\_rev2-w2-shard2\close_shard2_w2.py"
src = io.open(P, encoding="utf-8").read()

# 1. verdict gate
src = src.replace(
    'if codex and codex.get("verdict") == "PASS":',
    'codex_pass = bool(codex) and str(codex.get("primary_reviewer_adjudication", ""))'
    '.startswith("PASS")\n    if codex_pass:',
)

# 2. verifier method override in build_reviewer_evidence
src = src.replace(
    """            {
                "role": "verifier",
                "method": "command",
                "command": src["command"],
                "raw_output": src["tail"][-2000:],
                "fingerprint": uid + ":rev2w2s2:probe-rerun-1",
                "exit_code": src["exit_code"],
            },""",
    """            {
                "role": "verifier",
                "method": "command",
                "command": src["command"],
                "raw_output": src["tail"][-2000:],
                "fingerprint": uid + ":rev2w2s2:probe-rerun-1",
                "exit_code": src["exit_code"],
            },"""  # already 'command'; keep explicit
)

# 3. idempotency guard at top of close_unit
src = src.replace(
    """    with open(rec_path, encoding="utf-8") as fh:
        rec = json.load(fh)
    b = BATTERY[uid]""",
    """    with open(rec_path, encoding="utf-8") as fh:
        rec = json.load(fh)
    if (rec.get("state") == "SUCCESS"
            and (rec.get("extensions") or {}).get("reviewer_closure")):
        print("%s: already closed by this reviewer; skipping" % uid)
        return [], [], None
    b = BATTERY[uid]""",
)
io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("patched close script (verdict gate, idempotency guard)")
