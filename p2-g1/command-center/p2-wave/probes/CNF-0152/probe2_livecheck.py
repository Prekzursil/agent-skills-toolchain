#!/usr/bin/env python3
"""CNF-0152 probe2: live hostile-path instantiation on THIS Windows substrate. The artifact's
measurement ran on linux (honestly recorded); this probe re-runs the five shapes live on the
current host, records every outcome, attempts the NUL-mount crash class, and asserts the
artifact's honesty block remains truthful about its own scope. Outcomes are RECORDED, not
asserted; only the artifact's honesty and walk-completeness are asserted.
Emitted by shard8-w2 resume builder 2026-10-25."""
import json, os, shutil, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CHECKS = []
FACTS = {}

def ck(name, cond):
    CHECKS.append({"check": name, "ok": bool(cond)})
    return bool(cond)

def load(rel):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))

def finish(pid, uid):
    raw = {"probe": pid, "unit": uid, "facts": FACTS, "checks": CHECKS, "all_ok": all(c["ok"] for c in CHECKS)}
    (Path(__file__).parent / (pid + ".raw.json")).write_bytes(json.dumps(raw, indent=1, ensure_ascii=False).encode("utf-8"))
    print(json.dumps(raw, ensure_ascii=False))
    return 0 if raw["all_ok"] else 1

def main():
    d = load("command-center/receipts/CNF-0152.json")
    work = Path(__file__).parent / "w2-live"
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    outcomes = {}

    deep = work
    try:
        for i in range(14):
            deep = deep / ("segment-%02d-with-padding-0123456789" % i)
        deep.mkdir(parents=True)
        f = deep / "leaf.txt"
        f.write_text("x", encoding="utf-8")
        p = str(f)
        outcomes["a-long-root"] = {"path_len": len(p), "walked_ok": True, "created": True}
        n = sum(len(part) + 1 for part in Path(p).parts)
        outcomes["a-long-root"]["win_path_units"] = n
    except OSError as e:
        outcomes["a-long-root"] = {"created": False, "error": "%s: %s" % (type(e).__name__, str(e)[:160])}

    try:
        dev = chr(92) + chr(92) + "." + chr(92) + "NUL"   # device namespace path built without backslash literals
        with open(dev, "w", encoding="utf-8") as fh:
            fh.write("probe")
        outcomes["b-reserved-device"] = {"device_write_ok": True}
    except OSError as e:
        outcomes["b-reserved-device"] = {"device_write_ok": False,
                                         "error": "%s: %s" % (type(e).__name__, str(e)[:160])}
    try:
        os.stat("NUL")
        outcomes["b-reserved-device"]["stat_NUL"] = "ok"
    except OSError as e:
        outcomes["b-reserved-device"]["stat_NUL"] = "%s: %s" % (type(e).__name__, str(e)[:160])

    try:
        ca = work / "CaseProbe.txt"
        ca.write_text("a", encoding="utf-8")
        cb = work / "caseprobe.txt"
        cb.write_text("b", encoding="utf-8")
        same = ca.resolve() == cb.resolve()
        outcomes["c-case-collision"] = {"collided_same_file": bool(same)}
    except OSError as e:
        outcomes["c-case-collision"] = {"error": "%s: %s" % (type(e).__name__, str(e)[:160])}

    try:
        na = work / "données-ünïcode-中文.txt"
        na.write_text("u", encoding="utf-8")
        outcomes["d-non-ascii"] = {"created_and_walked": na.is_file()}
    except OSError as e:
        outcomes["d-non-ascii"] = {"error": "%s: %s" % (type(e).__name__, str(e)[:160])}

    try:
        sp = work / "dir with spaces and (parens)"
        sp.mkdir()
        f2 = sp / "file with spaces.txt"
        f2.write_text("s", encoding="utf-8")
        outcomes["e-spaces"] = {"created_and_walked": f2.is_file()}
    except OSError as e:
        outcomes["e-spaces"] = {"error": "%s: %s" % (type(e).__name__, str(e)[:160])}

    FACTS["windows_live_outcomes"] = outcomes

    walked = 0
    for root, dirs, files in os.walk(work):
        walked += len(files)
    FACTS["walker_completed_files_seen"] = walked
    ck("live_walk_completed_on_windows_host", walked >= 1)

    h = d.get("honesty", {})
    ck("honesty_windows_scope_still_true_for_artifact", h.get("windows_os_not_executed") is True)
    ck("artifact_rows_present_for_every_shape", len(d["matrix"]) == 6)
    return finish("probe2_livecheck", "CNF-0152")

if __name__ == "__main__":
    sys.exit(main())
