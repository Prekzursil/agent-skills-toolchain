import json, re, subprocess
from pathlib import Path
REPO = Path.home() / "p2-g1"

def head(p, n=60):
    try:
        return "\n".join((REPO / p).read_text(encoding="utf-8").splitlines()[:n])
    except Exception as e:
        return "ERR %s" % e

print("=== corpus.py ===")
print(head("tools/marketplace/corpus.py", 80))
print("=== fixtures dir ===")
fx = REPO / "tools/marketplace/fixtures"
if fx.is_dir():
    for p in sorted(fx.iterdir()):
        print(" ", p.name, p.stat().st_size if p.is_file() else "(dir)")
else:
    print("  NO fixtures dir")
print("=== registry_corpus.json ===")
try:
    d = json.loads((fx / "registry_corpus.json").read_text(encoding="utf-8"))
    print("top keys:", list(d.keys()))
    plugs = d.get("plugins") or []
    print("plugins:", len(plugs))
    for pl in plugs:
        print(" -", pl.get("name"), "| skills:", [s.get("name") if isinstance(s, dict) else s for s in (pl.get("skills") or [])][:8],
              "| desc has quuxzorch:", "quuxzorch" in json.dumps(pl))
except Exception as e:
    print("ERR", e)
print("=== who imports marketplace.search ===")
r = subprocess.run(["grep", "-rln", "marketplace.search\|marketplace import", str(REPO / "tools"),
                    str(REPO / "command-center/p2-wave/probes"), str(REPO / "platform")],
                   capture_output=True, text=True)
print("\n".join(l for l in r.stdout.splitlines() if "__pycache__" not in l)[:2500])
