"""ADV-0021 INDEPENDENT VERIFIER probe (round-1 build lane).

Mechanically DIFFERENT from the dead agent's Probe 2 absence checks, which were
token searches over source text. This probe instead:
  * parses each module with `ast` and reasons over the parsed tree, and
  * EXECUTES the semver regex against a traversal payload.

Every absence assertion is paired with a positive control over the SAME mechanism,
so a silent detector is caught (both-states rule).

Read-only. Writes nothing; prints a JSON blob between sentinels.
"""
from __future__ import annotations

import ast
import io
import json
import os
import re

ROOT = r"C:/Users/Prekzursil/source/ast-integrate"
PLUG = os.path.join(ROOT, "platform/plugin")

MODULES = ["cli.py", "lifecycle.py", "packager.py", "fsops.py", "journal.py",
           "deploy.py", "manifest.py", "proc.py", "payload.py", "cache.py"]

out: dict = {"probe": "ADV-0021-verifier-ast-and-exec", "checks": {}}


def tree(mod: str):
    src = io.open(os.path.join(PLUG, mod), encoding="utf-8").read()
    return src, ast.parse(src, filename=mod)


def call_names(node) -> list[str]:
    """Every callee NAME reachable under `node` (attribute or bare)."""
    names = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                names.append(f.id)
            elif isinstance(f, ast.Attribute):
                names.append(f.attr)
    return names


def find_func(t, name):
    for n in ast.walk(t):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    return None


# ---------------------------------------------------------------- V1: semver
# The dead agent READ the regex. This EXECUTES it.
src_m, t_m = tree("manifest.py")
semver_literal = None
for n in ast.walk(t_m):
    if isinstance(n, ast.Assign):
        for tgt in n.targets:
            if isinstance(tgt, ast.Name) and tgt.id == "SEMVER_RE":
                for sub in ast.walk(n.value):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                        semver_literal = sub.value
compiled = re.compile(semver_literal) if semver_literal else None
payloads = {
    "benign": "1.2.3",
    "traversal_dash": "1.2.3-../../OUTSIDE_TREE",
    "traversal_plus": "1.2.3+../../OUTSIDE_TREE",
    "backslash": "1.2.3-..\\..\\OUTSIDE",
    "nul_adjacent": "1.2.3-a\tb",
    "control_must_reject": "not-a-version",
}
out["checks"]["V1_semver_regex_executed"] = {
    "pattern_literal": semver_literal,
    "pattern_anchor": "platform/plugin/manifest.py:SEMVER_RE",
    "accepts": {k: bool(compiled.match(v)) for k, v in payloads.items()} if compiled else None,
    "detector_control_rejects_garbage": (not bool(compiled.match(payloads["control_must_reject"])))
    if compiled else None,
}

# ------------------------------------------------- V2: signature verification
SIG_VERBS = {"verify_signature", "check_signature", "verify", "gpg_verify",
             "cosign_verify", "minisign_verify", "verify_detached", "load_public_key"}
HASH_VERBS = {"sha256", "archive_sha256", "content_hash"}
sig_hits, hash_hits = [], []
for m in MODULES:
    s, t = tree(m)
    for n in ast.walk(t):
        if isinstance(n, ast.Call):
            f = n.func
            nm = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
            if nm in SIG_VERBS:
                sig_hits.append(f"{m}:{n.lineno}:{nm}")
            if nm in HASH_VERBS:
                hash_hits.append(f"{m}:{n.lineno}:{nm}")
out["checks"]["V2_signature_calls_ast"] = {
    "signature_verb_callsites": sig_hits,
    "signature_verb_count": len(sig_hits),
    "detector_control_hash_verb_callsites_count": len(hash_hits),
    "detector_control_sample": hash_hits[:6],
    "interpretation": "0 signature callsites WITH a non-zero hash-verb control proves the "
                      "absence is real and the AST walker is not inert",
}

# ------------------------------------- V3: containment on version_dir vs deploy
s_j, t_j = tree("journal.py")
vd = find_func(t_j, "version_dir")
vd_calls = call_names(vd) if vd else None
s_d, t_d = tree("deploy.py")
deploy_safe_join_fns = []
for n in ast.walk(t_d):
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if "safe_join" in call_names(n):
            deploy_safe_join_fns.append(f"deploy.py:{n.name}:{n.lineno}")
out["checks"]["V3_version_dir_containment_ast"] = {
    "version_dir_found": vd is not None,
    "version_dir_lineno": getattr(vd, "lineno", None),
    "version_dir_callees": vd_calls,
    "safe_join_in_version_dir": ("safe_join" in (vd_calls or [])),
    "detector_control_functions_that_DO_call_safe_join": deploy_safe_join_fns,
    "detector_control_count": len(deploy_safe_join_fns),
}

# --------------------------------------------- V4: decompression / size bound
# AST: any Compare node whose operands mention an uncompressed-size attribute.
SIZE_TOKENS = {"file_size", "compress_size", "max_uncompressed", "decompress_limit",
               "uncompressed_size"}
FREE_TOKENS = {"disk_usage", "free", "dir_size"}
size_cmps, free_cmps = [], []
for m in ("packager.py", "lifecycle.py", "fsops.py", "cache.py"):
    s, t = tree(m)
    for n in ast.walk(t):
        if isinstance(n, ast.Compare):
            seg = ast.get_source_segment(s, n) or ""
            if any(tok in seg for tok in SIZE_TOKENS):
                size_cmps.append(f"{m}:{n.lineno}:{seg[:120]}")
            if any(tok in seg for tok in FREE_TOKENS):
                free_cmps.append(f"{m}:{n.lineno}:{seg[:120]}")
out["checks"]["V4_expansion_bound_ast"] = {
    "uncompressed_size_comparisons": size_cmps,
    "uncompressed_size_comparison_count": len(size_cmps),
    "detector_control_freespace_comparisons_count": len(free_cmps),
    "detector_control_sample": free_cmps[:4],
    "interpretation": "0 size-ratio comparisons WITH >0 free-space comparisons proves the "
                      "Compare-node walker fires and the ratio cap is genuinely absent",
}

# ------------------------------------------------- V5: CLI exception surface
s_c, t_c = tree("cli.py")
handlers = []
for n in ast.walk(t_c):
    if isinstance(n, ast.ExceptHandler):
        ty = ast.get_source_segment(s_c, n.type) if n.type else "BARE-EXCEPT"
        handlers.append(f"cli.py:{n.lineno}:{ty}")
out["checks"]["V5_cli_exception_handlers_ast"] = {
    "handlers": handlers,
    "handler_count": len(handlers),
    "catches_broad_exception": any("Exception" == h.split(":")[-1] or "BaseException" in h
                                   for h in handlers),
}

# ------------------------------------------- V6: test-gap, by AST not by grep
# The dead agent's T1 lane token-SEARCHED the six test modules. This instead parses
# each test module and reasons over test FUNCTION NAMES plus every string constant,
# which is a different mechanism over the same question.
TEST_MODULES = ["test_cli.py", "test_foundation.py", "test_health.py",
                "test_lifecycle.py", "test_package.py", "test_schemas.py"]
# DETECTOR-DEFECT NOTE (found and fixed during this build, recorded so it is not
# silently deleted): a first pass matched bare substrings and reported 3 spurious
# "zip_decompression_bomb" tests because the token "ratio" occurs inside the word
# "migration". Word-boundary matching is therefore mandatory here, and each
# behaviour is CONJUNCTIVE - the test must mention the boundary AND the attack,
# because the question is not "is traversal tested anywhere" but "is traversal
# tested AT THIS BOUNDARY".
BEHAVIOURS = {
    # behaviour -> (must match one of A) AND (must match one of B)
    "version_string_traversal": ((r"version", r"semver"), (r"traversal", r"\.\.", r"escape", r"outside", r"slip")),
    "provenance_live_path_escape": ((r"provenance", r"live_path", r"livepath"), (r"escape", r"outside", r"traversal", r"\.\.")),
    "zip_decompression_bomb": ((r"zip", r"archive", r"unpack", r"decompress"), (r"bomb", r"ratio", r"expansion", r"quota", r"limit", r"cap")),
    "package_signature": ((r"signature", r"signed", r"gpg", r"cosign", r"pubkey", r"trust[_ ]?anchor"), None),
}
ADJACENT = {  # the weaker "is this attack tested ANYWHERE" reading, reported separately
    "any_traversal_test": (r"traversal", r"zip[_ ]?slip", r"unsafe[_ ]?path", r"outside[_ ]the[_ ]prefix"),
}
found: dict[str, list[str]] = {k: [] for k in BEHAVIOURS}
adjacent: dict[str, list[str]] = {k: [] for k in ADJACENT}
control_hits: list[str] = []
test_fn_total = 0


def wb(tok: str, hay: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + tok + r"(?![a-z0-9])", hay) is not None


for m in TEST_MODULES:
    p = os.path.join(PLUG, m)
    if not os.path.exists(p):
        continue
    s = io.open(p, encoding="utf-8").read()
    t = ast.parse(s, filename=m)
    for n in ast.walk(t):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test"):
            test_fn_total += 1
            hay = n.name.lower() + " " + " ".join(
                c.value.lower() for c in ast.walk(n)
                if isinstance(c, ast.Constant) and isinstance(c.value, str))
            for beh, (grp_a, grp_b) in BEHAVIOURS.items():
                hit_a = any(wb(tok, hay) for tok in grp_a)
                hit_b = True if grp_b is None else any(wb(tok, hay) for tok in grp_b)
                if hit_a and hit_b:
                    found[beh].append(f"{m}:{n.name}:{n.lineno}")
            for k, toks in ADJACENT.items():
                if any(wb(tok, hay) for tok in toks):
                    adjacent[k].append(f"{m}:{n.name}:{n.lineno}")
            if wb("diverged", hay):
                control_hits.append(f"{m}:{n.name}:{n.lineno}")
out["checks"]["V6_test_gap_ast"] = {
    "test_functions_parsed": test_fn_total,
    "modules_parsed": TEST_MODULES,
    "behaviour_hits_at_the_specific_boundary": found,
    "behaviours_with_zero_tests_at_the_specific_boundary": [k for k, v in found.items() if not v],
    "adjacent_coverage_weaker_reading": adjacent,
    "detector_control_diverged_test_functions": control_hits,
    "detector_control_count": len(control_hits),
    "detector_defect_found_and_fixed":
        "A substring pass reported 3 false zip_decompression_bomb hits because 'ratio' is a "
        "substring of 'migration'. Fixed with word-boundary + conjunctive matching. The false "
        "hits were test_dry_run_migration_moves_nothing, "
        "test_a_failing_step_rolls_the_migration_back, test_migration_ledger_serialises.",
    "interpretation": "The AST walker is proven live by the 'diverged' positive control (4 test "
                      "functions). behaviour_hits_at_the_specific_boundary answers the unit's "
                      "actual question; adjacent_coverage_weaker_reading is reported separately "
                      "so the finding is not overstated - traversal IS tested elsewhere in the "
                      "suite, just not at the version-string boundary that D1b exploited.",
}

print("ADV0021_V_BEGIN")
print(json.dumps(out, indent=2, sort_keys=True))
print("ADV0021_V_END")
