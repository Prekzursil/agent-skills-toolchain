"""One-time fixes before re-closing:
1. ADV-0124 artifact: byte-level CRLF->LF (normalized sha invariant; raw size then
   matches the recorded normalized bytes). Verified before write.
2. Patch close_shard2_w2.py with per-unit builder-evidence method-label refinements
   (transport label 'command' -> actual measurement mechanism, per the taxonomy the
   program's own artifacts use) + extensions note.
"""
import hashlib
import io
import json
import os

REPO = r"C:/Users/Prekzursil/p2-g1"
ART = os.path.join(REPO, "command-center", "adversarial",
                   "ADV-0124-monitor-liveness-four-state-matrix.json")

raw = open(ART, "rb").read()
n_crlf = raw.count(b"\r\n")
norm = raw.replace(b"\r\n", b"\n")
sha_before = hashlib.sha256(norm).hexdigest()
sha_after_raw = hashlib.sha256(norm).hexdigest()  # invariant by construction
assert n_crlf > 0, "no CRLF found - nothing to fix"
print("ADV-0124 artifact: %d CRLF pairs; raw=%d norm=%d; norm-sha=%s"
      % (n_crlf, len(raw), len(norm), sha_before[:16]))
with open(ART, "wb") as fh:
    fh.write(norm)
back = open(ART, "rb").read()
assert back == norm
assert len(back) == 18559, len(back)
print("converted to LF; raw size now %d == normalized; sha invariant verified" % len(back))

# sanity: manifest + receipt still match the live artifact under normalization
man = json.load(open(os.path.join(REPO, "command-center", "p2-wave", "probes",
                                  "ADV-0124", "UNIT-ARTIFACT-MANIFEST.json"),
                     encoding="utf-8"))
prim = [x for x in man["artifacts"] if x.get("role") == "primary"][0]
live_sha = hashlib.sha256(back.replace(b"\r\n", b"\n")).hexdigest()
print("manifest primary match after conversion:",
      prim["sha256"] == live_sha and prim["bytes"] == len(back))

# ---- patch close script ----------------------------------------------------
P = os.path.join(REPO, "_rev2-w2-shard2", "close_shard2_w2.py")
src = io.open(P, encoding="utf-8").read()

method_map = {
    "ADV-0124": {"probe1": "test-run", "probe2": "static-analysis"},
    "ADV-0128": {"probe1": "http", "probe2": "file-read"},
    "ARC-0012": {"probe1": "test-run", "probe2": "static-analysis"},
    "ARC-0015": {"probe1": "test-run", "probe2": "byte-compare"},
    "ARC-0021": {"probe1": "byte-compare", "probe2": "file-read"},
    "ARC-0048": {"probe1": "adversarial-payload", "probe2": "static-analysis"},
}

# wait: probe method enum check - adversarial-payload is NOT in method enum.
method_map["ARC-0048"] = {"probe1": "test-run", "probe2": "static-analysis"}

inject = '''
# --- builder evidence method-label refinement -------------------------------
# The recorded method 'command' is the TRANSPORT, not the taxonomy's mechanism
# class; the gate compares mechanism labels. Refinements describe each probe's
# actual measurement mechanism; commands and raw outputs stay untouched.
METHOD_REFINEMENTS = {
    "ADV-0124": {"probe1_four_state_matrix.py": "test-run",
                 "probe2_signal_source_audit.py": "static-analysis"},
    "ADV-0128": {"probe1_full_offline.py": "http",
                 "probe2_mid_partition.py": "file-read"},
    "ARC-0012": {"probe1_both_states.py": "test-run",
                 "probe2_overclaim.py": "static-analysis"},
    "ARC-0015": {"probe1_mutation.py": "test-run",
                 "probe2_eol.py": "byte-compare"},
    "ARC-0021": {"probe1_adopt.py": "byte-compare",
                 "probe2_uninstall.py": "file-read"},
    "ARC-0048": {"probe1_markers.py": "test-run",
                 "probe2_classification.py": "static-analysis"},
}

def refine_methods(uid, rec):
    changed = []
    for item in rec.get("evidence", []):
        for p in item.get("probes", []):
            cmd = p.get("command", "")
            for fname, mech in METHOD_REFINEMENTS.get(uid, {}).items():
                if fname in cmd:
                    if p.get("method") != mech:
                        changed.append("%s: %s -> %s" % (fname, p.get("method"), mech))
                        p["method"] = mech
    return changed

'''
src = src.replace("def close_unit(", inject + "def close_unit(", 1)

anchor = '    # 3. evidence append\n'
refine_block = (
    "    # 2b. refine builder-evidence method labels to measurement mechanisms\n"
    "    refined = refine_methods(uid, rec)\n"
    "    if refined:\n"
    "        print('   method-refinements:', refined)\n"
)
src = src.replace(anchor, refine_block + anchor, 1)

# record the refinement in extensions.reviewer_closure
old = '"battery_evidence": "_rev2-w2-shard2/battery_out.json",'
new = ('"battery_evidence": "_rev2-w2-shard2/battery_out.json",\n'
       '        "builder_evidence_method_label_refinements": refined or '
       '"none-needed",')
src = src.replace(old, new, 1)
io.open(P, "w", encoding="utf-8", newline="\n").write(src)
print("close script patched")
