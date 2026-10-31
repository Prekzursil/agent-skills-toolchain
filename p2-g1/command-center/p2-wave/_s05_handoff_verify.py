#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

WIN = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards")
# When run from Windows python, use Windows path.
if not WIN.is_dir():
    WIN = Path(r"C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\ovh-monitor\g1-shards")

shard = [ln.strip() for ln in (WIN / "shard-05.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
rem = [ln.strip() for ln in (WIN / "shard-05.remaining.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
raw = (WIN / "shard-05.remaining.txt").read_bytes()
res = json.loads((WIN / "shard-05.txt.result.json").read_text(encoding="utf-8"))
ok_ids = [i for i in shard if i not in set(rem)]
print("shard_n", len(shard))
print("remaining_n", len(rem))
print("ok_from_setdiff", len(ok_ids))
print("ok_ids", " ".join(ok_ids))
print("remaining_fp", hashlib.sha256(raw).hexdigest())
print("result_ok", res.get("ok"), "result_fail", res.get("fail"), "result_attempted", res.get("attempted"))
print("result_remaining_fp", res.get("remaining_fp"))
print("fp_match", hashlib.sha256(raw).hexdigest() == res.get("remaining_fp"))
print("dup_shard", len(shard) - len(set(shard)))
print("dup_rem", len(rem) - len(set(rem)))
print("rem_not_in_shard", [i for i in rem if i not in set(shard)])
print("arith", len(ok_ids) + len(rem) == len(shard))
