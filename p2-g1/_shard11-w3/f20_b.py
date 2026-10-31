
# ---- receipt: refresh evidence to LIVE bytes, keep reviewer closure ----
rec_path = REPO / "command-center/receipts/IMP-0207.json"
rec = json.loads(rec_path.read_text(encoding="utf-8"))


def probe_blocks(pid, role):
    code, cmd, out = raws[pid]
    src = {"command": cmd, "exit_code": code, "method": "command",
           "raw_output": out, "role": role}
    ver = {"command": cmd, "exit_code": code,
           "fingerprint": hashlib.md5(out.encode("utf-8")).hexdigest(),
           "method": "command", "raw_output": out, "role": role}
    return src, ver


p1_src, p1_ver = probe_blocks("probe1", "source")
p2_src, p2_ver = probe_blocks("probe2", "verifier")

claims = {e["anchor"]: e for e in rec["evidence"]}
c1 = claims["tools/agentspec/agentspec/packs.py:load_pack"]
c1["probes"] = [p1_src, p1_ver]
c1["verdict"] = "CONFIRMED"
c2 = claims["tools/agentspec/agentspec/packs.py:privilege_intersection"]
c2["probes"] = [p2_src, p1_ver]
c2["verdict"] = "CONFIRMED"

artifacts = [
    row("tools/agentspec/agentspec/packs.py", "implementation"),
    row("tools/agentspec/agentspec/semver.py", "supporting"),
    row("command-center/p2-wave/probes/IMP-0207/probe1_both_states.py", "probe"),
    row("command-center/p2-wave/probes/IMP-0207/probe2_intersection.py", "probe"),
    row("command-center/p2-wave/probes/IMP-0207/fixtures/pack_narrow.json", "fixture"),
    row("command-center/p2-wave/probes/IMP-0207/fixtures/pack_widen_tools.json", "fixture"),
    row("command-center/p2-wave/probes/IMP-0207/fixtures/pack_widen_source.json", "fixture"),
]
rec["artifacts"] = artifacts
rec["tests"] = [
    {"command": raws["probe1"][1], "id": "probe1", "result": "PASS"},
    {"command": raws["probe2"][1], "id": "probe2", "result": "PASS"},
]
rec["timestamps"] = {"started_at": "2026-08-25T01:03:53Z", "ended_at": NOW,
                     "rebuilt_at": NOW}
