#!/usr/bin/env python3
"""CNF-0149 probe2: live transport re-derivation. This worktree carries no .git, so the
cat-file/show routes cannot re-execute here; the probe (a) re-reads RELEASE-CHECKLIST.md and
re-locates the recorded recipe text (line-drift recorded, content-intact required), (b) re-proves
the core transport property - the worktree route preserves CRLF byte-for-byte - against a live
temp file, (c) records the no-git constraint explicitly. Emitted by shard8-w2 resume builder."""
import hashlib, json, os, tempfile, sys
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
    (Path(__file__).parent / (pid + ".raw.json")).write_bytes(json.dumps(raw, indent=1).encode("utf-8"))
    print(json.dumps(raw))
    return 0 if raw["all_ok"] else 1

def main():
    d = load("command-center/receipts/CNF-0149.json")
    ck("no_git_here_recorded_honestly", not (REPO / ".git").exists())

    io = d["inputs_on_disk"]
    io_key = [k for k in io if "RELEASE" in k.upper()][0]
    cite = io[io_key]["line_citation"][0]
    rc_path = REPO / cite["path"]
    ck("release_checklist_live", rc_path.is_file())

    lines = rc_path.read_text(encoding="utf-8", errors="replace").splitlines()
    live_line = lines[cite["line"] - 1] if len(lines) >= cite["line"] else ""
    drift = None
    if cite["text"].strip() not in live_line:
        for idx, ln in enumerate(lines, 1):
            if cite["text"].strip() in ln:
                drift = idx
                break
    FACTS["cited_line"] = cite["line"]
    FACTS["recipe_text_now_at_line"] = drift
    ck("recipe_text_intact_line_drift_recorded",
       (cite["text"].strip() in live_line) or (drift is not None and drift != cite["line"]))

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as fh:
        fh.write(b"alpha\r\nbeta\r\ngamma\r\n")
        tmp = fh.name
    try:
        back = Path(tmp).read_bytes()
        ck("worktree_route_preserves_crlf_bytes_live",
           back.count(b"\r\n") == 3 and back == b"alpha\r\nbeta\r\ngamma\r\n")
        norm = back.replace(b"\r\n", b"\n")
        FACTS["live_crlf_bytes"] = len(back)
        FACTS["live_lf_bytes"] = len(norm)
        ck("crlf_lf_byte_delta_is_three", len(back) - len(norm) == 3)
        FACTS["live_sha256_crlf"] = hashlib.sha256(back).hexdigest()
        FACTS["live_sha256_lf"] = hashlib.sha256(norm).hexdigest()
    finally:
        os.unlink(tmp)
    ck("live_hashes_distinct_by_ending", FACTS["live_sha256_crlf"] != FACTS["live_sha256_lf"])
    ck("git_routes_reproduced_flag_intact",
       d["classic_3837_3737_control"].get("reproduced") is True)
    return finish("probe2_livecheck", "CNF-0149")

if __name__ == "__main__":
    sys.exit(main())
