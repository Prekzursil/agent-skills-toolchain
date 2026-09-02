"""P11 independent confirmation - mechanical re-count of the Wave 1 / Wave 2 floor claims.

Every number here is computed by THIS file's own logic, off bytes fetched with
`git cat-file -p <named-commit>:<path>` for the baseline arms and off the working tree for the
current arm. `git archive` is deliberately NOT used (it returns CRLF on this box).

Named anchors (never a moving reference):
  W1_END = edcf9f5b   last commit before Wave 2's first commit; the state the Wave-2 audit itself
                      recorded as "main @ edcf9f5b"
  W2_END = 0aa6f8fa   last Wave-2 commit
  W3_END = 04e4736c   last Wave-3 commit == current HEAD at probe time
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
W1_END = "edcf9f5b"
W2_END = "0aa6f8fa"
W3_END = "04e4736c"

OUT: dict[str, object] = {
    "anchors": {"W1_END": W1_END, "W2_END": W2_END, "W3_END": W3_END}
}


def git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(REPO), capture_output=True, check=False)
    if r.returncode != 0:
        return ""
    return r.stdout.decode("utf-8", errors="replace")


def blob(rev: str, rel: str) -> str | None:
    r = subprocess.run(
        ["git", "cat-file", "-p", f"{rev}:{rel}"],
        cwd=str(REPO),
        capture_output=True,
        check=False,
    )
    if r.returncode != 0:
        return None
    return r.stdout.decode("utf-8", errors="replace")


def jblob(rev: str, rel: str):
    t = blob(rev, rel)
    if t is None:
        return None
    try:
        return json.loads(t)
    except json.JSONDecodeError as e:
        return {"__parse_error__": str(e)}


def tree_files(rev: str, prefix: str) -> list[str]:
    t = git("ls-tree", "-r", "--name-only", rev, "--", prefix)
    return [x for x in t.splitlines() if x.strip()]


# ---------------------------------------------------------------- W1-01 registry candidates
def w1_registry(rev: str | None) -> dict[str, object]:
    rows: list[dict] = []
    per_file = {}
    for n in range(1, 6):
        rel = f"platform/registry/workflow-candidates-{n}.json"
        d = (
            jblob(rev, rel)
            if rev
            else json.loads((REPO / rel).read_text(encoding="utf-8"))
        )
        if d is None:
            per_file[rel] = "MISSING"
            continue
        arr = d if isinstance(d, list) else d.get("candidates") or d.get("rows") or d
        if isinstance(arr, dict):
            # dict of id -> record
            arr = list(arr.values())
        per_file[rel] = len(arr)
        rows.extend(x for x in arr if isinstance(x, dict))
    ids = [str(r.get("id") or r.get("candidate_id") or "") for r in rows]
    manifest = [i for i in ids if "MANIFEST" in i.upper()]
    rejects = [i for i in ids if "REJECT" in i.upper()]
    kept = [i for i in ids if i not in manifest and i not in rejects]
    upstream = Counter()
    up_by_id: dict[str, str] = {}
    for r in rows:
        i = str(r.get("id") or "")
        if i in manifest or i in rejects:
            continue
        u = r.get("upstream_repo") or r.get("upstream") or ""
        if isinstance(u, str) and u.strip():
            upstream[u.strip()] += 1
            up_by_id[i] = u.strip()
    dup_upstream = {u: c for u, c in upstream.items() if c > 1}
    shells = sorted(i for i, u in up_by_id.items() if u in dup_upstream)
    return {
        "per_file_counts": per_file,
        "raw_rows": len(rows),
        "manifest_rows": manifest,
        "self_marked_reject_rows": rejects,
        "kept_count": len(kept),
        "distinct_kept_ids": len(set(kept)),
        "duplicate_ids": [i for i, c in Counter(kept).items() if c > 1],
        "rows_sharing_an_upstream_repo_with_another_row": len(shells),
        "shell_ids": shells,
        "duplicate_upstream_groups": len(dup_upstream),
        "kept_minus_one_per_dup_group": len(kept) - (len(shells) - len(dup_upstream)),
    }


OUT["W1_01_registry_at_W1_END"] = w1_registry(W1_END)
OUT["W1_01_registry_now"] = w1_registry(None)


# ---------------------------------------------------------------- W1-02/03 council counts
STATUS_HINT = re.compile(r"(VALIDATION|STATUS|EXPECT|COVERAGE|METHOD|REPORT)", re.I)


def council_counts(rev: str | None) -> dict[str, object]:
    res = {}
    for kind in ("protocols", "presets"):
        prefix = f"platform/council/{kind}"
        if rev:
            names = [
                p.rsplit("/", 1)[-1]
                for p in tree_files(rev, prefix)
                if p.endswith(".json")
            ]
            getter = lambda nm, k=kind: jblob(rev, f"platform/council/{k}/{nm}")  # noqa: E731
        else:
            names = sorted(p.name for p in (REPO / prefix).glob("*.json"))
            getter = lambda nm, k=kind: json.loads(  # noqa: E731
                (REPO / f"platform/council/{k}/{nm}").read_text(encoding="utf-8")
            )
        specs, nonspecs = [], []
        for nm in names:
            try:
                d = getter(nm)
            except Exception:
                nonspecs.append(nm)
                continue
            # A CouncilSpec is identified structurally, not by filename.
            if isinstance(d, dict) and "council_id" in d and "voting" in d:
                specs.append(nm)
            else:
                nonspecs.append(nm)
        res[kind] = {
            "json_files": len(names),
            "councilspec_shaped": len(specs),
            "non_spec_files": sorted(nonspecs),
            "name_filter_would_exclude": sorted(
                n for n in names if STATUS_HINT.search(n)
            ),
        }
    return res


OUT["W1_02_03_council_at_W1_END"] = council_counts(W1_END)
OUT["W1_02_03_council_now"] = council_counts(None)


# ---------------------------------------------------------------- W1-04 schema compile
def schema_compile(rev: str | None) -> dict[str, object]:
    from jsonschema.validators import Draft202012Validator

    prefix = "platform/schema"
    if rev:
        names = [
            p.rsplit("/", 1)[-1] for p in tree_files(rev, prefix) if p.endswith(".json")
        ]
        load = lambda nm: jblob(rev, f"{prefix}/{nm}")  # noqa: E731
    else:
        names = sorted(p.name for p in (REPO / prefix).glob("*.json"))
        load = lambda nm: json.loads((REPO / prefix / nm).read_text(encoding="utf-8"))  # noqa: E731
    docs, data, ok, bad = [], [], [], []
    for nm in names:
        d = load(nm)
        if not isinstance(d, dict) or "__parse_error__" in d:
            data.append(nm)
            continue
        if "$schema" in d or "$id" in d or "properties" in d or "$defs" in d:
            docs.append(nm)
            try:
                Draft202012Validator.check_schema(d)
                ok.append(nm)
            except Exception as e:
                bad.append({"file": nm, "err": str(e)[:200]})
        else:
            data.append(nm)
    return {
        "json_files": len(names),
        "schema_documents": len(docs),
        "data_report_files": sorted(data),
        "compile_ok": len(ok),
        "compile_fail": bad,
    }


OUT["W1_04_schema_at_W1_END"] = schema_compile(W1_END)
OUT["W1_04_schema_now"] = schema_compile(None)


# ---------------------------------------------------------------- W1-07 / W2-05 substrate
TOKEN = re.compile(r"[A-Za-z0-9_./\-]+\.schema\.json|[A-Za-z0-9_./\-]+\.json")


def substrate(rev: str | None) -> dict[str, object]:
    if rev:
        cat = jblob(rev, "command-center/WORK-UNIT-CATALOG.json")
    else:
        cat = json.loads(
            (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
        )
    if cat is None:
        return {"catalog": "MISSING at this rev"}
    units = cat.get("work_units") or []
    values = Counter()
    tokens = Counter()
    prose = 0
    for u in units:
        v = u.get("output_schema")
        if not isinstance(v, str) or not v.strip():
            continue
        v = v.strip()
        values[v] += 1
        toks = TOKEN.findall(v)
        if not toks:
            prose += 1
            continue
        if len(v.split()) > 3:
            prose += 1
        for t in toks:
            tokens[t] += 1

    def exists(tok: str) -> bool:
        if rev:
            return (
                subprocess.run(
                    ["git", "cat-file", "-e", f"{rev}:{tok}"],
                    cwd=str(REPO),
                    capture_output=True,
                    check=False,
                ).returncode
                == 0
            )
        return (REPO / tok).is_file()

    resolving = [t for t in tokens if exists(t)]
    missing = sorted(set(tokens) - set(resolving))
    cc = [t for t in tokens if t.startswith("command-center/schema/")]
    cc_res = [t for t in cc if exists(t)]
    ns = Counter(t.rsplit("/", 1)[0] for t in missing)
    # per-unit loadability
    loadable = 0
    for u in units:
        v = u.get("output_schema")
        if not isinstance(v, str):
            continue
        toks = TOKEN.findall(v)
        if toks and all(exists(t) for t in toks):
            loadable += 1
    return {
        "units": len(units),
        "distinct_output_schema_values": len(values),
        "prose_like_values": prose,
        "distinct_path_tokens": len(tokens),
        "token_references_total": sum(tokens.values()),
        "tokens_resolving": len(resolving),
        "tokens_missing": len(missing),
        "missing_by_namespace": dict(ns.most_common()),
        "cc_schema_tokens": len(cc),
        "cc_schema_tokens_resolving": len(cc_res),
        "cc_schema_references": sum(tokens[t] for t in cc),
        "units_with_all_tokens_resolving": loadable,
    }


OUT["W1_07_substrate_at_W1_END"] = substrate(W1_END)
OUT["W2_05_substrate_at_W2_END"] = substrate(W2_END)
OUT["W2_05_substrate_now"] = substrate(None)


# ---------------------------------------------------------------- W2-07 git tracking census
W2_DIRS = [
    "platform/workflows",
    "platform/architecture",
    "platform/lib/workflows",
    "platform/lib/foundry",
    "command-center/schema",
]


def tracking(rev: str) -> dict[str, int]:
    return {d: len(tree_files(rev, d)) for d in W2_DIRS}


OUT["W2_07_tracked_at_W1_END"] = tracking(W1_END)
OUT["W2_07_tracked_at_W2_END"] = tracking(W2_END)
OUT["W2_07_tracked_at_W3_END"] = tracking(W3_END)
OUT["W2_07_on_disk_now"] = {
    d: sum(1 for p in (REPO / d).rglob("*") if p.is_file()) for d in W2_DIRS
}


# ---------------------------------------------------------------- W2-01 / W2-08 / W2-09 blueprints
def blueprints(rev: str | None) -> dict[str, object]:
    prefix = "platform/workflows"
    if rev:
        paths = [p for p in tree_files(rev, prefix) if p.endswith(".json")]
        load = lambda p: jblob(rev, p)  # noqa: E731
    else:
        paths = sorted(
            str(p.relative_to(REPO)).replace("\\", "/")
            for p in (REPO / prefix).rglob("*.json")
        )
        load = lambda p: json.loads((REPO / p).read_text(encoding="utf-8"))  # noqa: E731
    bp, reports, bad = [], [], []
    ids = Counter()
    id_to_files: dict[str, list[str]] = {}
    stops = Counter()
    flagship = []
    for p in paths:
        try:
            d = load(p)
        except Exception as e:
            bad.append({"file": p, "err": str(e)[:120]})
            continue
        if not isinstance(d, dict) or "__parse_error__" in (d or {}):
            bad.append({"file": p, "err": "unparseable"})
            continue
        if "dsl_version" in d and "stages" in d:
            bp.append(p)
            i = str(d.get("id", ""))
            ids[i] += 1
            id_to_files.setdefault(i, []).append(p)
            stops[json.dumps(d.get("stopping_rules"), sort_keys=True)] += 1
            if d.get("flagship") is True:
                flagship.append(p)
        else:
            reports.append(p)
    top = [p for p in bp if p.count("/") == 2]
    return {
        "json_files": len(paths),
        "blueprint_shaped": len(bp),
        "top_level_blueprints": len(top),
        "report_files": len(reports),
        "unparseable": bad,
        "flagship_count": len(flagship),
        "duplicate_ids": {i: id_to_files[i] for i, c in ids.items() if c > 1},
        "distinct_raw_stopping_rules": len(stops),
        "largest_stopping_rule_cluster": max(stops.values()) if stops else 0,
    }


OUT["W2_01_blueprints_at_W2_END"] = blueprints(W2_END)
OUT["W2_01_blueprints_at_W3_END"] = blueprints(W3_END)
OUT["W2_01_blueprints_now"] = blueprints(None)


# ---------------------------------------------------------------- W2-10 catalog defect deltas
def catalog_defects(rev: str | None) -> dict[str, object]:
    if rev:
        cat = jblob(rev, "command-center/WORK-UNIT-CATALOG.json")
    else:
        cat = json.loads(
            (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
        )
    if cat is None:
        return {"catalog": "MISSING"}
    units = cat.get("work_units") or []
    sentinel_bad = 0
    vendor_string_form = 0
    for u in units:
        uid = str(u.get("id", ""))
        s = u.get("completion_sentinel") or ""
        if f"SUCCESS:{uid}" not in s:
            sentinel_bad += 1
        amvr = u.get("assigned_model_vendor_role")
        if isinstance(amvr, str):
            vendor_string_form += 1
    return {
        "units": len(units),
        "sentinel_not_naming_own_id": sentinel_bad,
        "assigned_model_vendor_role_string_form": vendor_string_form,
    }


OUT["W2_10_catalog_at_W2_END"] = catalog_defects(W2_END)
OUT["W2_10_catalog_now"] = catalog_defects(None)

dest = REPO / "command-center" / "P11-FLOORS.json"
dest.write_text(json.dumps(OUT, indent=2, default=str), encoding="utf-8")
print(json.dumps(OUT, indent=2, default=str)[:200])
print(f"SUCCESS:p11-floors wrote {dest}")
