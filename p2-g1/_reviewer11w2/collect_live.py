import json, subprocess, sys
from pathlib import Path
ROOT = Path.home() / "p2-g1"
UNITS = ["IMP-0095","IMP-0096","IMP-0102","IMP-0107","IMP-0122","IMP-0133",
         "IMP-0138","IMP-0146","IMP-0151","IMP-0153","IMP-0160","IMP-0161"]
out = {}
for uid in UNITS:
    d = ROOT / "command-center/p2-wave/probes" / uid
    tails = {}
    for i in (1, 2):
        hits = [h for h in sorted(d.glob(f"probe{i}*.py")) if h.suffix == ".py"]
        p = subprocess.run([sys.executable, "-B", str(hits[0])], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=2700,
                           env={"PYTHONDONTWRITEBYTECODE": "1", "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT",""),
                                "PATH": __import__("os").environ.get("PATH",""), "HOME": str(ROOT)})
        text = (p.stdout + p.stderr).strip()
        tails[f"probe{i}"] = {"exit": p.returncode, "tail": text[-1400:]}
        print(uid, f"probe{i}", "rc=", p.returncode)
    out[uid] = tails
json.dump(out, open(Path(__file__).parent / "live_outputs.json", "w"), indent=1)
print("saved")
