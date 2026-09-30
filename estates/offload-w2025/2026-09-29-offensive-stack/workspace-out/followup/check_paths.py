import json, os

# Candidate "known-lost" surfaces: ask list + audit home-configs.md findings + canonical-mcp-servers.json paths
candidates = {
    "BurpSuite config (AppData Roaming)": r"C:\Users\prekzursil\AppData\Roaming\BurpSuite",
    "BurpSuite ProgFiles install": r"C:\Program Files\BurpSuite",
    "burp mcp-proxy jar (audit agents.json:1526)": r"C:\Users\prekzursil\AppData\Roaming\BurpSuite\mcp-proxy",
    "D:/bolt zai-lane surface": r"D:\bolt",
    "D:/opt/cursor-bridge": r"D:\opt\cursor-bridge",
    "tools/mcp/dbx-ai (repo vault copy)": r"D:\opt\vault\agent-skills-toolchain\tools\mcp\dbx-ai",
    "tools/mcp/dbx-ai (live source copy)": r"C:\Users\prekzursil\source\agent-skills-toolchain\tools\mcp\dbx-ai",
    "lifesciences-research source": r"C:\Users\prekzursil\source\lifesciences-research",
    "lifesciences-research (Prekzursil casing)": r"C:\Users\Prekzursil\source\lifesciences-research",
    "gh-cli-mcp on PATH (resolved via which)": "WHICH:gh-cli-mcp",
    "mcp_agent_mail pkg (audit :18812 / canonical :8812)": "WHICH:mcp_agent_mail",
    "D:/ReverseTools (paper-search, perplexity)": r"D:\ReverseTools",
    "paper-search venv exe": r"D:\ReverseTools\mcp\paper-search-mcp\venv\Scripts\paper-search-mcp.exe",
    "perplexity pwm-mcp exe": r"D:\ReverseTools\mcp\perplexity-web-mcp\.venv\Scripts\pwm-mcp.exe",
    "D:/opt/breach-mcp": r"D:\opt\breach-mcp",
    "D:/opt/burp": r"D:\opt\burp",
    # .local/opt RE suite (canonical paths; audit line 105 says some exist on VM)
    ".local/opt/ghidra-mcp": r"C:\Users\prekzursil\.local\opt\ghidra-mcp",
    ".local/opt/ida-pro-mcp": r"C:\Users\prekzursil\.local\opt\ida-pro-mcp",
    ".local/opt/jadx-mcp-server": r"C:\Users\prekzursil\.local\opt\jadx-mcp-server",
    ".local/opt/apktool-mcp-server": r"C:\Users\prekzursil\.local\opt\apktool-mcp-server",
    ".local/opt/hexstrike-ai": r"C:\Users\prekzursil\.local\opt\hexstrike-ai",
    ".local/opt/cloud-audit-mcp": r"C:\Users\prekzursil\.local\opt\cloud-audit-mcp",
    ".local/opt/mitmproxy-mcp": r"C:\Users\prekzursil\.local\opt\mitmproxy-mcp",
    ".local/opt/cheatengine-mcp-bridge": r"C:\Users\prekzursil\.local\opt\cheatengine-mcp-bridge",
    ".local/opt/frida": r"C:\Users\prekzursil\.local\opt\frida",
    ".local/opt/angr": r"C:\Users\prekzursil\.local\opt\angr",
    # sliver / msf anywhere obvious
    "sliver (D:/sliver)": r"D:\sliver",
    "sliver (.local/opt/sliver)": r"C:\Users\prekzursil\.local\opt\sliver",
    "metasploit (D:/metasploit)": r"D:\metasploit",
    "msf (.local/opt/metasploit)": r"C:\Users\prekzursil\.local\opt\metasploit",
    # other canonical D: surfaces
    "D:/mcp-servers (ocr-suite)": r"D:\mcp-servers",
    "D:/micromamba (openmm-md env)": r"D:\micromamba",
    "source/repos (rdkit, schrodinger, fb-messenger, openmm-md)": r"C:\Users\prekzursil\source\repos",
    "source/repos (Prekzursil casing)": r"C:\Users\Prekzursil\source\repos",
    # java (burp dependency per audit #1)
    "MS jdk-21 (burp java)": r"C:\Program Files\Microsoft\jdk-21.0.10.7-hotspot",
    "D:/opt/mirrored-from-home": r"D:\opt\mirrored-from-home",
    # env backups + secrets mentioned by ask
    ".agents/secrets/env-backups": r"C:\Users\prekzursil\.agents\secrets\env-backups",
    "vault secrets/env-backups": r"D:\opt\vault\agent-skills-toolchain\secrets\env-backups",
}

def du(path):
    total = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total

import shutil
for label, p in candidates.items():
    if p.startswith("WHICH:"):
        name = p.split(":", 1)[1]
        loc = shutil.which(name)
        print(f"{'PRESENT' if loc else 'MISSING':8} | {label:55} | which -> {loc}")
        continue
    exists = os.path.exists(p)
    size = f"{du(p)/1e6:.1f}MB" if exists and os.path.isdir(p) else ("file" if exists else "-")
    print(f"{'PRESENT' if exists else 'MISSING':8} | {label:55} | {p} | {size}")
