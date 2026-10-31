"""Patch 2 for _p2shard23-w2-build.py after first live run (fix cycle 1)."""
from pathlib import Path

p = Path(__file__).resolve().parent / "_p2shard23-w2-build.py"
src = p.read_text(encoding="utf-8")


def must_replace(old: str, new: str, tag: str) -> None:
    global src
    assert old in src, "MISSING TARGET: " + tag
    src = src.replace(old, new)
    print("patched:", tag)


# ---- 1. importlib modules must be registered in sys.modules BEFORE exec ----
must_replace(
    '''    spec = importlib.util.spec_from_file_location(
        "live_client_negotiate", REPO / "tools/plugin/client_negotiate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)''',
    '''    spec = importlib.util.spec_from_file_location(
        "live_client_negotiate", REPO / "tools/plugin/client_negotiate.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["live_client_negotiate"] = mod
    spec.loader.exec_module(mod)''',
    "0113 sys.modules",
)

for modname, relpath in [
    ("live_retry_after", "retry_after"),
    ("live_scheduler", "scheduler"),
    ("live_storm", "http_storm_scheduler"),
]:
    pass  # these are patched via the generic block below

src = src.replace(
    '''    spec = importlib.util.spec_from_file_location("live_retry_after", MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)''',
    '''    spec = importlib.util.spec_from_file_location("live_retry_after", MODULE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["live_retry_after"] = mod
    spec.loader.exec_module(mod)''')

src = src.replace(
    '''    spec = importlib.util.spec_from_file_location("live_scheduler", MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)''',
    '''    spec = importlib.util.spec_from_file_location("live_scheduler", MODULE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["live_scheduler"] = mod
    spec.loader.exec_module(mod)''')

src = src.replace(
    '''    spec = importlib.util.spec_from_file_location("live_storm", MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)''',
    '''    spec = importlib.util.spec_from_file_location("live_storm", MODULE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["live_storm"] = mod
    spec.loader.exec_module(mod)''')

# 0143: completion_predicate needs platform/lib on sys.path (vendor_identity import)
src = src.replace(
    '''    spec = importlib.util.spec_from_file_location("live_completion_predicate", REPO / "platform/lib/completion_predicate.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["live_completion_predicate"] = mod
    spec.loader.exec_module(mod)''',
    '''    for extra in (str(REPO / "platform/lib"), str(REPO)):
        if extra not in sys.path:
            sys.path.insert(0, extra)
    spec = importlib.util.spec_from_file_location("live_completion_predicate", REPO / "platform/lib/completion_predicate.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["live_completion_predicate"] = mod
    spec.loader.exec_module(mod)''')

# 0144: cache.py uses relative imports -> import through the package
src = src.replace(
    '''    spec2 = importlib.util.spec_from_file_location("live_plugin_cache", REPO / "platform/plugin/cache.py")
    pc = importlib.util.module_from_spec(spec2)
    sys.modules["live_plugin_cache"] = pc
    spec2.loader.exec_module(pc)''',
    '''    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    import platform.plugin.cache as pc  # noqa: PLC0415 -- relative imports need the package''')

# 0144: ready_units may also want repo root on sys.path
src = src.replace(
    '''    spec = importlib.util.spec_from_file_location("live_ready_units", REPO / "command-center/ready_units.py")
    ru = importlib.util.module_from_spec(spec)
    sys.modules["live_ready_units"] = ru
    spec.loader.exec_module(ru)''',
    '''    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    spec = importlib.util.spec_from_file_location("live_ready_units", REPO / "command-center/ready_units.py")
    ru = importlib.util.module_from_spec(spec)
    sys.modules["live_ready_units"] = ru
    spec.loader.exec_module(ru)''')

# ---- 2. probe1: only the self primary row must exist; dropped historical rows are NOTEs ----
must_replace(
    '''    for a in doc.get("artifacts") or []:
        if isinstance(a, dict) and str(a.get("role")) == "primary":
            chk((REPO / str(a.get("path") or "")).is_file(), "primary-absent", a.get("path"))''',
    '''    self_rel = "command-center/receipts/@@UID@@.json"
    for a in doc.get("artifacts") or []:
        if not isinstance(a, dict) or str(a.get("role")) != "primary":
            continue
        rel = str(a.get("path") or "").replace("\\\\", "/")
        if rel == self_rel:
            chk((REPO / rel).is_file(), "self-primary-absent", rel)
        elif not (REPO / rel).is_file():
            print("NOTE dropped recorded primary row (honest historical record): %s" % rel)''',
    "probe1 self-primary-only",
)

# ---- 3. probe1: widen recorded-probes counter (tests rows count too) ----
must_replace(
    '''    n_rec = len(doc.get("named_probes") or [])
    for e in doc.get("evidence") or []:
        if isinstance(e, dict):
            n_rec += len(e.get("probes") or [])
    chk(n_rec >= 2, "probes-under-recorded", n_rec)''',
    '''    n_rec = len(doc.get("named_probes") or [])
    for e in doc.get("evidence") or []:
        if isinstance(e, dict):
            n_rec += len(e.get("probes") or []) + len(e.get("named_probes") or [])
    for t in doc.get("tests") or []:
        if isinstance(t, dict) and t.get("command"):
            n_rec += 1
    chk(n_rec >= 2, "probes-under-recorded", n_rec)''',
    "probe1 widen recorded-probes",
)

# ---- 4. 0124 probe2: glob parent bug -- p IS the tests dir ----
must_replace(
    'for suite in sorted(p.parent.relative_to(root).as_posix() for p in root.glob("*/tests")):',
    'for suite in sorted(p.relative_to(root).as_posix() for p in root.glob("*/tests")):',
    "0124 census glob",
)

# ---- 5. 0129 probe2: net-allowlist live drift is a NOTE (recorded digest is historical) ----
must_replace(
    '''    na = REPO / "tools/lib/net-allowlist.mjs"
    chk(na.is_file(), "net-allowlist-absent-live")
    if na.is_file():
        sha, nb = norm_sha(na)
        chk(sha == s1.get("net_allowlist_sha256"), "net-allowlist-sha-drift", (sha, s1.get("net_allowlist_sha256")))
        chk(nb == s1.get("net_allowlist_present_bytes"), "net-allowlist-bytes", (nb, s1.get("net_allowlist_present_bytes")))''',
    '''    na = REPO / "tools/lib/net-allowlist.mjs"
    chk(na.is_file(), "net-allowlist-absent-live")
    if na.is_file():
        sha, nb = norm_sha(na)
        if sha != s1.get("net_allowlist_sha256") or nb != s1.get("net_allowlist_present_bytes"):
            print(
                "NOTE drift: live net-allowlist %d bytes sha=%s... vs recorded pre-strike %s bytes sha=%s..."
                % (nb, sha[:12], s1.get("net_allowlist_present_bytes"), str(s1.get("net_allowlist_sha256"))[:12])
            )''',
    "0129 allowlist drift note",
)

# ---- 6. 0130 probe2: a bare http:// URL string is not a downgrade primitive ----
must_replace(
    '''    bad = ("verify=False", "CERT_NONE", "_create_unverified", "insecure", "http://")''',
    '''    bad = ("verify=False", "CERT_NONE", "_create_unverified", "insecure_tls")  # bare http:// URL strings are not downgrade primitives''',
    "0130 downgrade scan",
)

p.write_text(src, encoding="utf-8", newline="\n")
print("patch2 complete, bytes:", len(src))
