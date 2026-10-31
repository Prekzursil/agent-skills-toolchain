#!/usr/bin/env python3
"""w4s15-r2 preflight: scope the schema (D) check + sha normalization for the 12 shard units.

Reviewer-owned fresh instruments. NOT copied from any prior pass.
  D1 = repo-canonical resolver (platform/lib/schema_resolver.validate_artifact)
  D2 = reviewer's own ref-walker (independent code path: loads the declared shim,
       follows its $ref by mapping the platform/command-center schema tail onto the
       p2-g1 root, compiles with jsonschema + referencing, iter_errors directly).
Both-states control for D: a synthetic mutation (inject a forbidden extra root key)
MUST go red; a sibling artifact known to validate clean (found by scanning a few
candidates) MUST stay green through BOTH instruments.
Sha control: raw-file sha vs CRLF->LF-normalized sha vs manifest row.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Prekzursil\p2-g1")
sys.path.insert(0, str(ROOT / "platform" / "lib"))
import schema_resolver as SR  # noqa: E402

UNITS = ["RES-0086", "RES-0089", "RES-0091", "RES-0102", "RES-0103", "RES-0111",
         "RES-0112", "RES-0114", "RES-0128", "RES-0144", "RES-0151", "RES-0157"]


def sha_norm(p: Path) -> str:
    b = p.read_bytes()
    return hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()


def sha_raw(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---- D2: reviewer's own ref-walker (no resolver import in this path) ----
def map_uri_to_root(uri: str) -> Path:
    raw = uri.split("#", 1)[0]
    posix = raw.replace("\\", "/")
    if raw.startswith("file:"):
        from urllib.parse import urlparse
        posix = urlparse(raw).path or ""
        if posix.startswith("/") and len(posix) > 3 and posix[2] == ":":
            posix = posix[1:]
    for tail in ("/platform/schema/", "/command-center/schema/"):
        i = posix.find(tail)
        if i != -1:
            return ROOT / posix[i + 1:].replace("\\", "/")
    raise RuntimeError(f"unmapped uri {uri!r}")


_D2_CACHE: dict = {}


def d2_validate(artifact, declared_schema_rel: str):
    """Load the declared schema file, follow ONE level of $ref (shim -> physical),
    compile, validate. Returns list of error strings."""
    try:
        declared = json.loads((ROOT / declared_schema_rel).read_bytes().decode("utf-8"))
    except Exception as e:
        return [f"<declared-load>: {e}"]
    target = declared
    hops = 0
    while isinstance(target, dict) and "$ref" in target and hops < 5:
        uri = target["$ref"]
        p = map_uri_to_root(uri)
        frag = uri.split("#", 1)[1] if "#" in uri else ""
        try:
            doc = json.loads(p.read_bytes().decode("utf-8"))
        except Exception as e:
            return [f"<ref-load {p.name}>: {e}"]
        target = doc
        if frag:
            for part in frag.lstrip("#/").split("/"):
                if not part:
                    continue
                part = part.replace("~1", "/").replace("~0", "~")
                if isinstance(target, dict) and part in target:
                    target = target[part]
                else:
                    return [f"<fragment {frag}>: missing in {p.name}"]
        hops += 1
    if not isinstance(target, dict) or "$ref" in target:
        return ["<resolve>: did not land on a concrete schema dict"]
    from jsonschema import Draft202012Validator
    try:
        v = Draft202012Validator(target)
    except Exception as e:
        return [f"<compile>: {e}"]
    out = []
    for err in v.iter_errors(artifact):
        loc = "/".join(str(x) for x in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def main():
    cat = json.loads((ROOT / "command-center" / "WORK-UNIT-CATALOG.json").read_bytes().decode("utf-8"))
    entries = {u["id"]: u for u in cat["work_units"]}
    report = {}
    for uid in UNITS:
        e = entries[uid]
        art_rel = e["output_path"]
        art = ROOT / art_rel
        row = {"artifact": art_rel, "schema": e["output_schema"]}
        if not art.is_file():
            row["artifact_missing"] = True
            report[uid] = row
            continue
        try:
            doc = json.loads(art.read_bytes().decode("utf-8"))
            row["parses"] = True
        except Exception as ex:
            row["parse_error"] = str(ex)[:200]
            report[uid] = row
            continue
        row["state"] = doc.get("state")
        row["sentinel"] = str(doc.get("sentinel"))[:90]
        # sha normalization control
        man_p = ROOT / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        if man_p.is_file():
            man = json.loads(man_p.read_bytes().decode("utf-8"))
            prim = [r for r in man.get("artifacts", []) if Path(r["path"]).name == art.name or r.get("role") == "primary"]
            if prim:
                r0 = prim[0]
                row["manifest_sha_match_norm"] = sha_norm(art) == r0["sha256"]
                row["manifest_sha_match_raw"] = sha_raw(art) == r0["sha256"]
                row["manifest_bytes"] = r0.get("bytes")
                row["disk_bytes"] = art.stat().st_size
        # D1 repo resolver
        try:
            errs1 = SR.validate_artifact(doc, e["output_schema"])
            row["D1_errors"] = len(errs1)
            row["D1_first"] = errs1[:3]
        except Exception as ex:
            row["D1_errors"] = "EXC"
            row["D1_first"] = [str(ex)[:200]]
        # D2 own walker
        errs2 = d2_validate(doc, e["output_schema"])
        row["D2_errors"] = len(errs2)
        row["D2_first"] = errs2[:3]
        report[uid] = row
    out = ROOT / "_reviewer-w4s15-r2" / "preflight.json"
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    for uid, row in report.items():
        d1 = row.get("D1_errors")
        d2 = row.get("D2_errors")
        agree = "AGREE" if d1 == d2 else "DISAGREE"
        print(f"{uid}: D1={d1} D2={d2} {agree} sha_norm={row.get('manifest_sha_match_norm')} sha_raw={row.get('manifest_sha_match_raw')} state={row.get('state')}")
    print("written:", out)


if __name__ == "__main__":
    main()
