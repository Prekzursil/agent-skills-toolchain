import subprocess, json, time

SHORTLIST = [
 "elder-plinius/T3MP3ST","Netw0rkNoob/VulnClaw","xalgorix/xalgorix","PentesterFlow/agent","0xSteph/pentest-ai",
 "0xSteph/pentest-ai-agents","chainreactors/cyber-harness","h5i-dev/h5i","Zyrexnn/Cybermes","cdxiaodong/cain-agent",
 "s0ld13rr/pentestcode","garagehq/nightcrawler","zakirkun/oh-my-open-pentest","martian56/redcell","Yean-Sec/StrikeAgent_AtkBrain-Flash",
 "LING71671/open-reverselab","Dest1ny-Sec/dhunter","Dest1ny-Sec/Luvv-MCP","xiaoli-one/FlowLens","skyvanguard/mcp-vanguard",
 "SnailSploit/Claude-Red","zhaoxuya520/reverse-skill","awarexone/Agentic-Bug-Hunter","sooryathejas/METATRON","blacklanternsecurity/red-run",
 "yaklang/hack-skills","elementalsouls/Claude-BugHunter","vmihalis/hacker-bob","operantlabs/operant-mcp","MickyBalladelli/qwythos",
 "Red-Team-Leaders/NeuroSploit","ktol1/RedTeam-Agent","gy15901580825/Argus","adithyan-ak/AgentHound","opena2a-org/hackmyagent",
 "kulchankas/paranoid","0sec-labs/0","gatsby-sec/llm-sec-range","us/shannon-on-claude-code","adikrn/shannon",
 "D0rs4n/mcpwn","nedlir/MCPwner","verialabs/ctf-agent","R00T-Kim/Terminator","loegaire/CTF-MCP-Swarm","decoy-run/decoy-redteam",
 "Fennec-AI/Fennec","lingbol088-spec/reverse-flow-skill","capture0x/AdStrike","ok-helloworld/vibe-pentest","MingyiSecLab/Atlas",
 "shinthink/blitzstrike","h4ckologic/bughunter-ai","weidutech/PentestPi","n1majne3/CyberPenda","branover/hexgraph",
 "AntAISecurityLab/Creation","nullc0d30/HunterX","laoshu666/hermes-seagull","huihuilikaile/CTF-BTFly","xoxruns/deadend-cli",
 "vvts-alpha/VERDICT","S1N6H/pentest-harness","Sumamovva/probeagent","lzy756/pen-agents","caoshanpu/AutoRedTeam-Orchestrator",
]

def gql(chunk):
    parts = []
    for j, repo in enumerate(chunk):
        o, n = repo.split("/", 1)
        parts.append(f'r{j}: repository(owner:"{o}", name:"{n}") {{ nameWithOwner createdAt pushedAt stargazerCount description isArchived isFork openIssues: issues(states:OPEN) {{ totalCount }} releases(last:1) {{ nodes {{ tagName publishedAt }} }} primaryLanguage {{ name }} }}')
    q = "{" + " ".join(parts) + "}"
    r = subprocess.run(["gh", "api", "graphql", "-f", f"query={q}"], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        return None
    return (json.loads(r.stdout).get("data") or {})

results = {}
def resolve(chunk, depth=0):
    if depth > 4 or len(chunk) == 1:
        data = gql(chunk)
        if data:
            for k, node in data.items():
                if node: results[node["nameWithOwner"]] = node
        return
    data = gql(chunk)
    if data is not None:
        for k, node in data.items():
            if node: results[node["nameWithOwner"]] = node
        time.sleep(1)
    else:
        m = len(chunk)//2
        resolve(chunk[:m], depth+1); resolve(chunk[m:], depth+1)

B = 40
for i in range(0, len(SHORTLIST), B):
    resolve(SHORTLIST[i:i+B])

with open("out/research/shortlist_verified.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=1)
for k, v in sorted(results.items(), key=lambda x: -x[1]["stargazerCount"]):
    rel = v["releases"]["nodes"]
    print(f"{v['stargazerCount']:6d} c{v['createdAt'][:10]} p{v['pushedAt'][:10]} iss{v['openIssues']['totalCount']:3d} rel{(rel[0]['tagName'] if rel else '-'):>10s} {'ARCH' if v['isArchived'] else '    '} {k} | {(v.get('description') or '')[:90]}")
print(f"\nverified: {len(results)}/{len(SHORTLIST)}")
missing = [s for s in SHORTLIST if s.lower() not in {k.lower() for k in results}]
print("MISSING:", missing)
