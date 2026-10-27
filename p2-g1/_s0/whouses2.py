import subprocess
from pathlib import Path
REPO = Path.home() / "p2-g1"
pats = ["marketplace\.search", "from marketplace.search import", "from marketplace import search",
        "import marketplace.search", "SearchIndex", "search_path"]
hits = {}
for pat in pats:
    r = subprocess.run(["grep", "-rln", "-e", pat, str(REPO / "command-center/p2-wave/probes"),
                        str(REPO / "tools"), str(REPO / "platform")], capture_output=True, text=True)
    files = [l for l in r.stdout.splitlines() if "__pycache__" not in l and l.endswith(".py")]
    hits[pat] = files
    print(pat, "->", len(files))
    for f in files:
        print("   ", f.replace(str(REPO) + "/", ""))
