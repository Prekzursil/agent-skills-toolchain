import subprocess, json, base64, re, time

LISTS = [
    "Yeti-791/Awesome-Offensive-AI-Agentic-Landscape",
    "R00T-Kim/awesome-offensive-mcp",
    "yeyintminthuhtut/awesome-ai-offensive-security",
    "skyvanguard/awesome-ai-pentesting",
    "Ed-Marcavage/awesome-security-agent-harnesses",
    "pazo01/awesome-cyber-ai-arsenal",
    "scadastrangelove/awesome-ai-security-tools",
    "sbilly/awesome-security",
    "Letszooming/awesome-red-teaming",
    "GangZhuo/awesome-red-teaming",
    "Gotham/awesome-llm-security",
    "punkpeye/awesome-mcp-servers",
]

link_re = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/?\)?")
all_links = {}
for repo in LISTS:
    try:
        r = subprocess.run(["gh", "api", f"repos/{repo}/readme", "--jq", ".content"], capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            print(f"SKIP {repo}: {r.stderr[:100]}")
            continue
        content = base64.b64decode(r.stdout.strip()).decode("utf-8", errors="replace")
        links = set(link_re.findall(content))
        all_links[repo] = links
        print(f"[{len(links):4d} links] {repo} (pushed: ", end="")
        r2 = subprocess.run(["gh", "api", f"repos/{repo}", "--jq", ".pushed_at"], capture_output=True, text=True, timeout=30)
        print(f"{r2.stdout.strip()})")
    except Exception as e:
        print(f"ERR {repo}: {e}")
    time.sleep(1)

# save flattened link set
flat = sorted(set(f"{o}/{n}" for s in all_links.values() for o, n in s if o not in ("topics","features","site","about","enterprise","pricing","security","settings","marketplace","solutions","orgs","users")))
with open("out/research/awesome_links.json", "w") as f:
    json.dump({"lists": {k: sorted(v) for k, v in all_links.items()}, "flat": flat}, f, indent=1)
print(f"\nTOTAL FLAT LINKS: {len(flat)}")
