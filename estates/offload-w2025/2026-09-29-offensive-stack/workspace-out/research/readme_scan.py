import subprocess, base64, re, json

REPOS = ["zhaoxuya520/reverse-skill","elder-plinius/T3MP3ST","SnailSploit/Claude-Red","awarexone/Agentic-Bug-Hunter",
         "Netw0rkNoob/VulnClaw","0xSteph/pentest-ai","xalgorix/xalgorix","chainreactors/cyber-harness","h5i-dev/h5i",
         "garagehq/nightcrawler","PentesterFlow/agent","us/shannon-on-claude-code","skyvanguard/mcp-vanguard",
         "LING71671/open-reverselab","zakirkun/oh-my-open-pentest","operantlabs/operant-mcp","martian56/redcell",
         "Zyrexnn/Cybermes","cdxiaodong/cain-agent","weidutech/PentestPi","vmihalis/hacker-bob","MickyBalladelli/qwythos"]

PAT = re.compile(r"(pip install|pipx install|uv |npm i|npm install|npx |go install|cargo install|git clone|docker|winget|choco|scoop|setup\.py|pyproject|requires-python|Windows|windows|WSL|wsl|macOS|Linux|\.exe|installer|Install)", re.I)
summary = {}
for repo in REPOS:
    try:
        r = subprocess.run(["gh","api",f"repos/{repo}/readme","--jq",".content"], capture_output=True, text=True, timeout=40)
        if r.returncode != 0:
            summary[repo] = ["README FETCH FAIL: " + r.stderr[:80]]
            continue
        md = base64.b64decode(r.stdout.strip()).decode("utf-8", errors="replace")
        lines = md.splitlines()
        hits, n = [], 0
        for i, l in enumerate(lines):
            if PAT.search(l) and len(l.strip()) > 3:
                hits.append(f"L{i+1}: {l.strip()[:160]}")
                n += 1
                if n >= 14: break
        summary[repo] = hits if hits else ["(no install/windows keywords in first pass)"]
    except Exception as e:
        summary[repo] = [f"ERR {e}"]

with open("out/research/readme_scans.json","w",encoding="utf-8") as f:
    json.dump(summary, f, indent=1, ensure_ascii=False)
for repo, hits in summary.items():
    print(f"\n===== {repo}")
    for h in hits: print(f"  {h}")
