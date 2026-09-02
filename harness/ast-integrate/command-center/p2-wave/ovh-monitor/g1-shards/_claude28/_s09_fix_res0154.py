import json
import sys
from pathlib import Path

HERE = Path(r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\probes\RES-0154")
REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
sys.path.insert(0, str(HERE))
import experiment as E  # noqa: E402
from util import OUT_REL, SENTINEL  # noqa: E402

art = REPO / OUT_REL
doc = json.loads(art.read_text(encoding="utf-8"))
live = E.run_experiment()

doc["negative_control"] = live["negative_control"]
doc["volume_ranking_differs"] = live["volume_ranking_differs"]
doc["author_swap_invariant"] = live["author_swap_invariant"]
doc["comparison"] = live["comparison"]
doc["ranking_honest"] = live["ranking_honest"]
doc["ranking_volume"] = live["ranking_volume"]

text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
assert SENTINEL in text, "sentinel lost"
art.write_text(text, encoding="utf-8")

# re-read and check every artifact-vs-live assertion the two probes make
d = json.loads(art.read_text(encoding="utf-8"))
nc = live["negative_control"]
anc = d.get("negative_control") or {}
checks = {
    "art nc.honest_surviving==0": int(anc.get("honest_surviving", -1)) == 0,
    "art nc.noisy_floor==live": int(anc.get("noisy_emitted_on_known_correct", -1)) == int(nc["noisy_emitted_on_known_correct"]),
    "art volume_ranking_differs is True": d.get("volume_ranking_differs") is True,
    "art author_swap_invariant is True": d.get("author_swap_invariant") is True,
    "art honest_precision==live": float((d.get("comparison") or {}).get("honest_precision", -1)) == float(live["comparison"]["honest_precision"]),
}
for k, v in checks.items():
    print(("PASS " if v else "FAIL "), k)
print("bytes:", art.stat().st_size)
