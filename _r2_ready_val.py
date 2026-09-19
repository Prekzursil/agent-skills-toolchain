from pathlib import Path
import json
ROOT = Path.cwd()
p = ROOT / "command-center/p2-wave/WAVE-STATE.json"
d = json.loads(p.read_text(encoding="utf-8"))
print(json.dumps(d, indent=1)[:3000])
