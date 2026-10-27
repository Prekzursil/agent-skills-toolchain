"""Patch 4: 0113 rubric what-part, 0136 http-date clock base, 0139 pass-key verdicts, 0144 doc load."""
from pathlib import Path

p = Path(__file__).resolve().parent / "_p2shard23-w2-build.py"
src = p.read_text(encoding="utf-8")


def must_replace(old: str, new: str, tag: str) -> None:
    global src
    assert old in src, "MISSING TARGET: " + tag
    src = src.replace(old, new)
    print("patched:", tag)


# ---- 0113: WHAT = names the failed component/operation; live message forms count ----
must_replace(
    '''    what = ("refuse" in t or "install" in t) and any(w in t for w in ("version", "client", "manifest"))''',
    '''    what = any(w in t for w in ("version", "client", "manifest", "registry", "install refused"))''',
    "0113 rubric what",
)

# ---- 0136: generate http-dates relative to the clock's actual now ----
must_replace(
    '''    clock = mod.WallClock()
    now0 = clock.datetime_now()
    honor_pass = ignore_fail = 0
    kinds_seen = set()
    for c in fixed:''',
    '''    clock = mod.WallClock()
    now0 = clock.datetime_now()
    if now0.tzinfo is None:
        now0 = now0.replace(tzinfo=timezone.utc)
    for c in fixed:  # http-dates are issued relative to the clock's actual now
        if c["value"] == "@@HTTP_DATE@@":
            c["value"] = formatdate((now0 + timedelta(seconds=c["instructed"])).timestamp(), usegmt=True)
        elif c["value"] == "@@PAST_DATE@@":
            c["value"] = formatdate((now0 - timedelta(seconds=1000)).timestamp(), usegmt=True)
    honor_pass = ignore_fail = 0
    kinds_seen = set()
    for c in fixed:''',
    "0136 clock-relative dates",
)

# 0136 needs timezone import
must_replace(
    "from datetime import timedelta",
    "from datetime import timedelta, timezone",
    "0136 timezone import",
)

# ---- 0139: verdicts read from the pass key of the live helpers ----
must_replace(
    '''    d = mod.classify_branches_are_distinct()
    chk(d.get("distinct") is True, "live-ast-branches", d)
    m = mod.mislabel_is_detected()
    chk(m.get("detected") is True, "live-mislabel-silent", m)''',
    '''    d = mod.classify_branches_are_distinct()
    chk(d.get("pass") is True, "live-ast-branches", d)
    m = mod.mislabel_is_detected()
    chk(m.get("pass") is True, "live-mislabel-silent", m)''',
    "0139 pass-key verdicts",
)

# ---- 0144: load the receipt before reading production_surfaces ----
must_replace(
    '''    prod = doc.get("production_surfaces") or []
    chk(len(prod) == 3, "production-surfaces", prod)''',
    '''    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    prod = doc.get("production_surfaces") or []
    chk(len(prod) == 3, "production-surfaces", prod)''',
    "0144 doc load",
)

p.write_text(src, encoding="utf-8", newline="\n")
print("patch4 complete, bytes:", len(src))
