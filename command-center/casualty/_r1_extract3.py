"""Round-1 extraction pass 3: ADV-0021 probe1 STRIDE inputs + sibling conventions."""
import json
import os

ROOT = r"C:/Users/Prekzursil/source/ast-integrate"
PO = os.path.join(ROOT, "command-center/casualty/probe-output")

p1 = json.load(open(os.path.join(PO, "adv0021_probe1_out.ORIGINAL.json"), encoding="utf-8"))

print("=" * 18, "verb_call_graph", "=" * 18)
for verb, calls in p1["verb_call_graph"].items():
    print(f"  {verb}: {json.dumps(calls)[:600]}")

print()
print("=" * 18, "unguarded_external_joins (all 12)", "=" * 18)
for j in p1["unguarded_external_joins"]:
    print(f"  {j['anchor']:22s} fn={j['in_function']:22s} expr={j['expr'][:110]}")

print()
print("=" * 18, "semver_gate", "=" * 18)
print(json.dumps(p1["semver_gate"], indent=1)[:1200])

print()
print("=" * 18, "cli_exception_handlers", "=" * 18)
print(json.dumps(p1["cli_exception_handlers"], indent=1))

print()
print("=" * 18, "sink_sites by category", "=" * 18)
cats = {}
for s in p1["sink_sites"]:
    cats.setdefault(s["category"], []).append(s["anchor"])
for c, v in sorted(cats.items(), key=lambda kv: -len(kv[1])):
    print(f"  {c:18s} n={len(v):3d}  e.g. {', '.join(v[:6])}")

print()
print("=" * 18, "control_sites by control", "=" * 18)
ctl = {}
for s in p1["control_sites"]:
    ctl.setdefault(s["control"], []).append(s["anchor"])
for c, v in sorted(ctl.items(), key=lambda kv: -len(kv[1])):
    print(f"  {c:24s} n={len(v):3d}  e.g. {', '.join(v[:5])}")

print()
print("=" * 18, "modules", "=" * 18)
print(p1["modules"])

print()
print("=" * 18, "SIBLING CONVENTION: ADV-0024 extensions/downstream/report tail", "=" * 18)
d24 = json.load(open(os.path.join(ROOT, "command-center/adversarial/ADV-0024-packager-secret-and-bloat-refusal.json"), encoding="utf-8"))
print("state:", d24["state"])
print("sentinel:", d24["sentinel"][:400])
print("min_bytes_threshold:", d24["min_bytes_threshold"])
print("artifacts:", json.dumps(d24["artifacts"], indent=1)[:900])
print("extensions.self_digest_recipe:", d24["extensions"]["self_digest_recipe"])
print("downstream_consumers[0]:", json.dumps(d24["downstream_consumers"][0], indent=1)[:1500])
print("manifest_registration:", json.dumps(d24["manifest_registration"]))
print("reviewer:", json.dumps(d24["reviewer"])[:700])
print("failure:", json.dumps(d24["failure"])[:900])
print("retry:", json.dumps(d24["retry"])[:700])
print("report.control_ids:", json.dumps(d24["report"]["control_ids"]))
print("report.observations[0]:", json.dumps(d24["report"]["observations"][0], indent=1))
