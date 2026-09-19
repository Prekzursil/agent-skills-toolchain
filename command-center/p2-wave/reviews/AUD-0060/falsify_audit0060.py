# AUD-0060 fresh-context falsification script. Plain file work, no MCP.
import json
import hashlib
import os
import re

ROOT = r"C:\Users\Prekzursil\source\agent-skills-toolchain"
REG = r"C:\Users\Prekzursil\.agents\agents.json"
ART = os.path.join(
    ROOT, r"command-center\audit\AUD-0060-mcp-tool-surface-inventory.json"
)
P1J = os.path.join(
    ROOT, r"command-center\p2-wave\probes\AUD-0060\probe1-tool-surface.json"
)
P1R = os.path.join(
    ROOT, r"command-center\p2-wave\probes\AUD-0060\probe1-tool-surface.raw.txt"
)
P2R = os.path.join(
    ROOT, r"command-center\p2-wave\probes\AUD-0060\probe2-usage-trace.raw.txt"
)
A15 = os.path.join(ROOT, r"command-center\audit\AUD-0015-mcp-scope-resolution.json")


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


out = []


def p(s=""):
    out.append(str(s))


# ---------- 1. Registry SSOT re-derivation ----------
reg = json.load(open(REG, encoding="utf-8"))
srv = reg["mcp"]["servers"]
enabled = {k: v for k, v in srv.items() if v.get("enabled") is True}
disabled = {k: v for k, v in srv.items() if v.get("enabled") is not True}
en_claude = sorted(
    k for k, v in enabled.items() if "claude" in (v.get("targets") or [])
)
en_codex = sorted(k for k, v in enabled.items() if "codex" in (v.get("targets") or []))
p("== REGISTRY ~/.agents/agents.json (SSOT) ==")
p(f"total_servers={len(srv)} enabled={len(enabled)} not_enabled={len(disabled)}")
p(f"enabled_targeting_claude={len(en_claude)} enabled_targeting_codex={len(en_codex)}")
p(f"disabled_names={sorted(disabled)}")

# ---------- 2. Artifact self-integrity ----------
art = json.load(open(ART, encoding="utf-8"))
a0 = art["artifacts"][0]
size = os.path.getsize(ART)
p("")
p("== ARTIFACT INTEGRITY ==")
p(f"self_declared bytes={a0['bytes']} sha256={a0['sha256'][:16]}...")
p(f"on-disk        bytes={size} sha256={sha(ART)[:16]}...")

# ---------- 3. Probe1 raw re-parse (mechanically independent of the artifact's embedded copy) ----------
p("")
p("== PROBE1 RAW (probe1-tool-surface.raw.txt) ==")
lines = open(P1R, encoding="utf-8", errors="replace").read().splitlines()
server_rows = [line for line in lines if line.startswith("SERVER\t")]
session_rows = [line for line in lines if line.startswith("SESSION\t")]
p(f"SERVER_rows={len(server_rows)} SESSION_rows={len(session_rows)}")
names16 = [line.split("\t")[1] for line in server_rows]
statuses = {}
for line in server_rows:
    st = line.split("\t")[2].split("=", 1)[1]
    statuses[st] = statuses.get(st, 0) + 1
p(f"server_status_counts={statuses}")
p(f"server_names={names16}")
sess_sum_tc = sum(
    int(line.split("tool_count=")[1].split("\t")[0])
    for line in session_rows
    if "tool_count=" in line
    and "None" not in line.split("tool_count=")[1].split("\t")[0]
)
sess_sum_sb = sum(
    int(line.split("schema_bytes=")[1].split("\t")[0])
    for line in session_rows
    if "schema_bytes=" in line
    and "None" not in line.split("schema_bytes=")[1].split("\t")[0]
)
p(f"session_tool_count_sum={sess_sum_tc} session_schema_bytes_sum={sess_sum_sb}")
live_sess = [line for line in session_rows if "reachable=True" in line]
p(f"live_session_names={[line.split(chr(9))[1] for line in live_sess]}")
m = [line for line in lines if line.startswith("SUMMARY")]
p(f"summary_line={m[0] if m else 'MISSING'}")

# planted control lines
for line in lines:
    if line.startswith(("fake-mcp", "planted-zero")):
        p(f"control: {line}")

# ---------- 4. Registry membership of the 16 ----------
p("")
p("== CROSS-CHECK: 16 AUD-0015 names vs registry ==")
missing_from_reg = [n for n in names16 if n not in srv]
not_enabled_in_reg = [
    n for n in names16 if n in srv and srv[n].get("enabled") is not True
]
in_reg_not_claude = [
    n for n in names16 if n in srv and "claude" not in (srv[n].get("targets") or [])
]
p(f"names_missing_from_registry={missing_from_reg}")
p(f"names_in_registry_but_not_enabled={not_enabled_in_reg}")
p(f"names_in_registry_but_claude_not_in_targets={in_reg_not_claude}")
en_set = set(en_claude) | set(en_codex)
extra = sorted((set(en_claude) - set(names16)))
p(f"registry_enabled_claude_servers_NOT_in_the_16: count={len(extra)}")
p(f"  names={extra}")

# ---------- 5. AUD-0015 primary-source re-derivation ----------
p("")
p("== AUD-0015 (primary source the headline cites) ==")
a15 = json.load(open(A15, encoding="utf-8"))
p(f"top_keys={list(a15.keys())[:20]}")


def find_servers(obj, path=""):
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "servers" and isinstance(v, (list, dict)):
                hits.append((path + "/" + k, v))
            hits.extend(find_servers(v, path + "/" + k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:2000]):
            hits.extend(find_servers(v, f"{path}[{i}]"))
    return hits


hits = find_servers(a15)
p(f"servers_collections_found={[(h[0], len(h[1])) for h in hits]}")
for hp, hv in hits:
    if isinstance(hv, dict):
        items = hv.items()
    else:
        items = [(str(i), x) for i, x in enumerate(hv)]
    states = {}
    ed_names = []
    for nm, sv in items:
        if isinstance(sv, dict):
            st = sv.get("effective_state") or sv.get("state") or "?"
            states[st] = states.get(st, 0) + 1
            if st == "ENABLED-DECLARED":
                ed_names.append(nm)
    if states:
        p(f"collection {hp}: state_counts={states}")
        if ed_names:
            p(f"  ENABLED-DECLARED names ({len(ed_names)}): {sorted(ed_names)}")
            p(f"  set_equal_to_probe1_16={sorted(ed_names) == sorted(names16)}")

# ---------- 6. Probe2 capability-matrix internal sums ----------
p("")
p("== PROBE2 RAW capability matrix ==")
l2 = open(P2R, encoding="utf-8", errors="replace").read().splitlines()
cap = [line for line in l2 if line.startswith("CAP\t")]
ver = [line for line in cap if "verified=True" in line]


def capnum(line, key):
    mm = re.search(key + r"=(\d+)", line)
    return int(mm.group(1)) if mm else 0


tsum = sum(capnum(line, "tool_count") for line in ver)
p(f"CAP_rows={len(cap)} verified_True={len(ver)} sum_tool_count_of_verified={tsum}")

# ---------- 7. Probe1 JSON summary cross-check ----------
p("")
p("== PROBE1 JSON (independent parse) ==")
p1j = json.load(open(P1J, encoding="utf-8"))


def walk(o, pre=""):
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, (dict, list)):
                walk(v, pre + "/" + k)
            elif any(
                s in k.lower()
                for s in ("enabled", "unreach", "session", "planted", "control")
            ):
                p(f"  {pre}/{k} = {v}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, f"{pre}[{i}]")


walk(p1j)
p(
    f"probe1_json_bytes={os.path.getsize(P1J)} sha={sha(P1J)[:16]}... probe1_raw_sha={sha(P1R)[:16]}..."
)
p(f"a15_json_bytes={os.path.getsize(A15)}")

open(
    os.path.join(
        ROOT, r"command-center\p2-wave\reviews\AUD-0060\falsify_script_output.txt"
    ),
    "w",
    encoding="utf-8",
).write("\n".join(out))
print("\n".join(out))
