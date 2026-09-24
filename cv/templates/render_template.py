#!/usr/bin/env python3
"""templates/render_template.py — render a document TEMPLATE end to end.

A *view* (in `profile.yaml: x_views`) is editorial: which sections, in which
order, for which audience. A *template* (here) is the render contract for one
delivered document: the view spec in render vocabulary, plus the three things a
view cannot express —

  1. `transform`  — profile edits that belong to the DOCUMENT, not to the facts:
                    dropping a profile link that must not be published yet, or
                    rendering the same verified fact in another language.
  2. `checks`     — what the finished PDF must satisfy (templates/docgate.py).
  3. provenance   — a manifest tying the PDF back to the exact profile bytes.

A template holds NO facts. Every sentence it renders comes from `profile.yaml`;
a translation entry is a 1:1 restatement of a profile string whose digits must
survive unchanged, and that rule is enforced here, not trusted.

Pipeline:

    profile.yaml  +  templates/<id>/template.yaml
      -> transform (strip links · date notes · translate, digit-parity enforced)
      -> out/templates/<id>/<slug>.resolved.yaml          (inspectable, audited)
      -> tools/build.py   (zerofab gate -> RenderCV -> tools/verify.py)
      -> templates/docgate.py   (the rendered PDF is re-checked)
      -> <slug>.template-manifest.json
      -> SUCCESS:<id> | FAILED:<id>

Usage
-----
    PY=~/.agents/cv/.venv/Scripts/python
    $PY templates/render_template.py --template ats-en
    $PY templates/render_template.py --template ro --reference out/templates/ats-en/<x>.pdf
    $PY templates/render_template.py --all
    $PY templates/render_template.py --template ats-en --drift-check   # no render

Exit codes: 0 ok · 2 usage/template error · 3 transform refused (digit parity,
missing translation target) · 4 build.py failed (gate, render or verify) ·
5 docgate failed.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                          # pragma: no cover
        pass

HERE = Path(__file__).resolve().parent                 # ~/.agents/cv/templates
ROOT = HERE.parent                                     # ~/.agents/cv
TOOLS = ROOT / "tools"
PROFILE = ROOT / "profile.yaml"
OUT = ROOT / "out" / "templates"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

TODO_MARKER = "TODO-CONFIRM"


def log(msg: str) -> None:
    print(msg, flush=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def load_yaml(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    try:
        from ruamel.yaml import YAML

        return YAML(typ="safe").load(text)
    except ImportError:                                        # pragma: no cover
        import yaml as pyyaml

        return pyyaml.safe_load(text)


def dump_yaml(obj: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from ruamel.yaml import YAML

        y = YAML()
        y.default_flow_style = False
        y.width = 4096
        y.allow_unicode = True
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            y.dump(obj, fh)
    except ImportError:                                        # pragma: no cover
        import yaml as pyyaml

        path.write_text(
            pyyaml.safe_dump(obj, sort_keys=False, allow_unicode=True, width=4096),
            encoding="utf-8",
        )


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


# --------------------------------------------------------------------------- #
# transforms                                                                   #
# --------------------------------------------------------------------------- #
def digits_of(text: str) -> list[str]:
    """The digit-bearing tokens of a string, in order, as written.

    A translation must not change a figure. Comparing this list on both sides is
    the whole enforcement: "1,016 commits" may become "1,016 commit-uri", never
    "1.016 commit-uri" (a Romanian thousands separator reads as a decimal point
    to every downstream parser, including tools/zerofab.py).
    """
    import zerofab

    return [t.raw for t in zerofab.tokenize(text, apply_masks=False)]


def strip_networks(profile: dict[str, Any], rules: list[Any]) -> list[str]:
    """Remove a social profile the owner has decided not to publish yet."""
    applied: list[str] = []
    wanted = {}
    for row in rules or []:
        if isinstance(row, dict):
            wanted[str(row.get("network", "")).lower()] = str(row.get("reason", ""))
        else:
            wanted[str(row).lower()] = ""
    if not wanted:
        return applied
    basics = profile.get("basics") or {}
    kept = []
    for prof in basics.get("profiles") or []:
        net = str((prof or {}).get("network", "")).lower()
        if net in wanted:
            applied.append(f"{net}: {wanted[net] or 'no reason recorded'}")
            continue
        kept.append(prof)
    basics["profiles"] = kept
    return applied


def apply_date_notes(profile: dict[str, Any], rules: list[dict[str, Any]]) -> list[str]:
    """Replace an untypeable date range with a written note, in this document's
    language. build.py already refuses to guess such a date and emits an English
    "Dates: …" line; a Romanian rendering needs the same fact in Romanian."""
    applied: list[str] = []
    for rule in rules or []:
        block = str(rule.get("block", "work"))
        key = norm(rule.get("key", ""))
        note = norm(rule.get("note", ""))
        if not key or not note:
            continue
        for item in profile.get(block) or []:
            if not isinstance(item, dict):
                continue
            ident = "|".join(
                x for x in (norm(item.get("name") or item.get("institution")),
                            norm(item.get("position"))) if x
            )
            if ident != key:
                continue
            if rule.get("drop_dates", True):
                item.pop("startDate", None)
                item.pop("endDate", None)
            item["highlights"] = [note, *(item.get("highlights") or [])]
            applied.append(f"{block}[{key}] -> {note!r}")
    return applied


def apply_translations(
    profile: dict[str, Any], pairs: list[dict[str, str]]
) -> tuple[dict[str, str], list[str], list[str]]:
    """Substitute every declared 1:1 restatement across the whole profile.

    Returns (source_map rendered->source, drift, errors). `drift` names a pair
    whose source string is no longer in the profile — the profile moved under
    the template and that bullet will render untranslated, which is honest but
    must be seen. `errors` are refusals: a changed figure, or a dropped
    TODO-CONFIRM marker.
    """
    table: dict[str, str] = {}
    errors: list[str] = []
    for i, row in enumerate(pairs or []):
        src, dst = norm(row.get("from", "")), norm(row.get("to", ""))
        if not src or not dst:
            errors.append(f"translate[{i}] needs both `from` and `to`")
            continue
        if digits_of(src) != digits_of(dst):
            errors.append(
                f"translate[{i}] changes a figure: {digits_of(src)} -> "
                f"{digits_of(dst)}. A translation restates a verified number; "
                f"it never renotates it ({src[:60]!r})"
            )
            continue
        if (TODO_MARKER in src) != (TODO_MARKER in dst):
            errors.append(
                f"translate[{i}] adds or drops the {TODO_MARKER} marker "
                f"({src[:60]!r}) — an unresolved gap must stay visible"
            )
            continue
        table[src] = dst

    used: set[str] = set()
    source_map: dict[str, str] = {}

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: (v if k.startswith("x_") and k != "x_master" else walk(v))
                    for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        if isinstance(node, str):
            hit = table.get(norm(node))
            if hit is not None:
                used.add(norm(node))
                source_map[norm(hit)] = norm(node)
                return hit
        return node

    # x_master is the evidence bank and stays in its original language: it is
    # what the document is checked AGAINST, so translating it would move the
    # yardstick with the thing being measured.
    master = profile.get("x_master")
    translated = walk(profile)
    if master is not None:
        translated["x_master"] = master
    profile.clear()
    profile.update(translated)

    drift = [s for s in table if s not in used]
    return source_map, drift, errors


def patch_intermediate(
    path: Path, spec: dict[str, Any]
) -> tuple[list[str], list[str]]:
    """Apply the template's document-level patches to the emitted intermediate.

    Two things only a rendered document knows about live here:

      * `locale` — build.py ships a Romanian pack, but RenderCV's locale model has
        fields that pack does not set (`phrases.degree_with_area` still reads
        "DEGREE in AREA", printing "Licență in Informatică" in a Romanian CV).
      * `entries` — a RENDERING artefact that asserts more than the profile knows.
        profile.yaml holds the bachelor's as the years 2022 and 2025; RenderCV
        expands a bare year to "Jan 2022" and prints a month nobody verified.

    The invariant that keeps this from becoming a back door: a patch may only
    REMOVE precision or restate what the entry already says. Every digit in a
    patched value must already appear in the entry it patches, and every patch
    must carry a written reason. A patch that introduces a new figure is refused.
    """
    applied: list[str] = []
    errors: list[str] = []
    if not spec:
        return applied, errors
    doc = load_yaml(path)
    if not isinstance(doc, dict):
        return applied, [f"{path} did not parse to a mapping"]

    locale_patch = spec.get("locale") or {}
    if locale_patch:
        base = dict(doc.get("locale") or {})
        for k, v in locale_patch.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                base[k] = {**base[k], **v}
            else:
                base[k] = v
        doc["locale"] = base
        applied.append(f"locale: {sorted(locale_patch)}")

    sections = ((doc.get("cv") or {}).get("sections") or {})
    for i, rule in enumerate(spec.get("entries") or []):
        section = str(rule.get("section", ""))
        match = rule.get("match") or {}
        setters = rule.get("set") or {}
        unset = [str(x) for x in (rule.get("unset") or [])]
        reason = norm(rule.get("reason", ""))
        if not reason:
            errors.append(f"intermediate.entries[{i}] has no reason; a document "
                          f"patch without a written reason is a silent edit")
            continue
        rows = sections.get(section)
        if not isinstance(rows, list):
            errors.append(f"intermediate.entries[{i}] targets section {section!r}, "
                          f"which this document does not render "
                          f"(have: {', '.join(sections) or 'none'})")
            continue
        hit = False
        for row in rows:
            if not isinstance(row, dict):
                continue
            if not all(norm(row.get(k)) == norm(v) for k, v in match.items()):
                continue
            hit = True
            have = set(digits_of(" ".join(str(v) for v in row.values())))
            for k, v in setters.items():
                new = set(digits_of(str(v)))
                if not new <= have:
                    errors.append(
                        f"intermediate.entries[{i}] sets {k}={v!r}, introducing "
                        f"{sorted(new - have)} — a document patch may restate what "
                        f"the entry already says, never add a figure"
                    )
                    break
            else:
                for k in unset:
                    row.pop(k, None)
                row.update(setters)
                applied.append(f"{section}/{match} -> set {sorted(setters)} "
                               f"unset {unset} ({reason[:70]})")
        if not hit:
            errors.append(f"intermediate.entries[{i}] matched nothing in "
                          f"{section!r} — the document moved under the template")
    if not errors:
        dump_yaml(doc, path)
    return applied, errors


# --------------------------------------------------------------------------- #
# drift against the profile's own x_views entry                                #
# --------------------------------------------------------------------------- #
def view_drift(profile: dict[str, Any], template: dict[str, Any]) -> list[str]:
    """Report where the template's render contract differs from the editorial
    view declared in profile.yaml. Advisory: the template is what renders, but a
    silent divergence between the two is exactly how two documents drift apart."""
    import build as build_mod

    vid = str(template.get("extends_view") or template.get("id") or "")
    try:
        declared = build_mod.resolve_view(profile, vid)
    except (KeyError, ValueError) as exc:
        return [f"profile.yaml declares no view {vid!r} to compare against ({exc})"]
    render = template.get("render") or {}
    out: list[str] = []
    for key in ("sections", "section_titles", "page", "locale", "theme",
                "page_budget", "headline", "todo_policy"):
        if key not in render:
            continue
        mine, theirs = render[key], declared.get(key)
        if mine != theirs:
            out.append(f"{key}: template={mine!r} vs profile x_views={theirs!r}")
    return out


# --------------------------------------------------------------------------- #
# driver                                                                       #
# --------------------------------------------------------------------------- #
def render(template_id: str, args: argparse.Namespace) -> int:
    tdir = HERE / template_id
    tpath = tdir / "template.yaml"
    if not tpath.exists():
        log(f"  ERROR no template at {tpath}")
        log(f"FAILED:{template_id}")
        return 2
    template = load_yaml(tpath)
    if not isinstance(template, dict):
        log(f"  ERROR {tpath} did not parse to a mapping")
        log(f"FAILED:{template_id}")
        return 2

    profile_path = Path(args.profile).resolve()
    if not profile_path.exists():
        log(f"  ERROR profile not found: {profile_path}")
        log(f"FAILED:{template_id}")
        return 2
    profile = load_yaml(profile_path)
    if not isinstance(profile, dict):
        log(f"  ERROR {profile_path} did not parse to a mapping")
        log(f"FAILED:{template_id}")
        return 2

    log(f"  TEMPLATE {template_id}  ({tpath})")
    log(f"  PROFILE  {profile_path}  sha256={sha256(profile_path)[:16]}…")

    drift_view = view_drift(profile, template)
    for d in drift_view:
        log(f"  DRIFT  view contract: {d}")
    if args.drift_check:
        log(f"SUCCESS:{template_id}:drift-check" if not drift_view
            else f"SUCCESS:{template_id}:drift-check ({len(drift_view)} difference(s))")
        return 0

    # ---- 1. transform ------------------------------------------------------ #
    resolved = copy.deepcopy(profile)
    transform = template.get("transform") or {}
    stripped = strip_networks(resolved, transform.get("strip_networks") or [])
    for row in stripped:
        log(f"  STRIP  social profile {row}")
    notes = apply_date_notes(resolved, transform.get("date_notes") or [])
    for row in notes:
        log(f"  DATE   {row}")
    source_map, drift_tr, errs = apply_translations(
        resolved, transform.get("translate") or []
    )
    for e in errs:
        log(f"  ERROR  {e}")
    if errs:
        log(f"FAILED:{template_id}")
        return 3
    if source_map:
        log(f"  TRANS  {len(source_map)} string(s) rendered in "
            f"{template.get('render', {}).get('locale', 'en')}")
    for d in drift_tr:
        log(f"  DRIFT  translation source no longer in the profile: {d[:90]!r}")
    if drift_tr and str(transform.get("on_drift", "warn")).lower() == "fail":
        log("  ERROR  on_drift=fail and the profile moved under this template")
        log(f"FAILED:{template_id}")
        return 3

    # ---- 2. inject the render contract as the view build.py will resolve --- #
    render_spec = dict(template.get("render") or {})
    view_id = f"template:{template_id}"
    views = resolved.get("x_views")
    spec = {"id": view_id, **render_spec}
    if isinstance(views, list):
        resolved["x_views"] = [*views, spec]
    elif isinstance(views, dict):
        resolved["x_views"] = {**views, view_id: render_spec}
    else:
        resolved["x_views"] = [spec]

    out_dir = (Path(args.out).resolve() if args.out else OUT / template_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = str(render_spec.get("slug") or f"{template_id}")
    resolved_path = out_dir / f"{slug}.resolved.yaml"
    dump_yaml(resolved, resolved_path)
    log(f"  EMIT   {resolved_path}  ({resolved_path.stat().st_size} bytes)")
    map_path = out_dir / f"{slug}.source-map.json"
    map_path.write_text(json.dumps(source_map, indent=1, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    # ---- 3a. emit the intermediate through build.py (zerofab gate runs here) - #
    cmd = [sys.executable, str(TOOLS / "build.py"), "--view", view_id,
           "--profile", str(resolved_path), "--out", str(out_dir), "--emit-only"]
    log(f"  BUILD  {' '.join(cmd[1:])}")
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False,
                          encoding="utf-8", errors="replace")
    for line in (proc.stdout or "").rstrip().splitlines():
        log(f"  | {line}")
    for line in (proc.stderr or "").rstrip().splitlines()[:40]:
        log(f"  | {line}")
    if proc.returncode != 0:
        log(f"  ERROR build.py exited {proc.returncode}")
        log(f"FAILED:{template_id}")
        return 4

    build_manifest_path = out_dir / f"{slug}.manifest.json"
    build_manifest = (json.loads(build_manifest_path.read_text(encoding="utf-8"))
                      if build_manifest_path.exists() else {})
    intermediate = Path(build_manifest.get("intermediate")
                        or (out_dir / f"{slug}.rendercv.yaml"))
    if not intermediate.exists():
        log(f"  ERROR build.py produced no intermediate at {intermediate}")
        log(f"FAILED:{template_id}")
        return 4

    # ---- 3b. document-level patches to the intermediate --------------------- #
    patches, perrs = patch_intermediate(intermediate, template.get("intermediate") or {})
    for e in perrs:
        log(f"  ERROR  {e}")
    if perrs:
        log(f"FAILED:{template_id}")
        return 3
    for row in patches:
        log(f"  PATCH  {row}")

    # ---- 3c. render + the no-regression contract (build.py's own functions) -- #
    import build as build_mod
    import verify as verify_mod

    ok, msg, pdf = build_mod.render_rendercv(intermediate, out_dir, f"{slug}.pdf")
    log(f"  RENDER {msg}")
    if not ok or not pdf.exists():
        log(f"FAILED:{template_id}")
        return 4
    build_manifest["pdf"] = str(pdf)
    build_manifest["pdf_bytes"] = pdf.stat().st_size
    build_manifest["pdf_sha256"] = sha256(pdf)
    build_manifest["intermediate_patches"] = patches
    build_manifest_path.write_text(
        json.dumps(build_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    try:
        vok, findings = verify_mod.verify_pdf(pdf, build_manifest, resolved)
    except Exception as exc:                                   # pragma: no cover
        log(f"  VERIFY could not run tools/verify.py: {exc!r}")
        log(f"FAILED:{template_id}")
        return 4
    for f in findings:
        log(f"  {f}")
    if not vok:
        log("  ERROR tools/verify.py refused the PDF")
        log(f"FAILED:{template_id}")
        return 4

    # ---- 4. docgate on the artefact ---------------------------------------- #
    ref = None
    if args.reference:
        ref = Path(args.reference).resolve()
    elif template.get("checks", {}).get("reference_pdf"):
        ref = (ROOT / str(template["checks"]["reference_pdf"])).resolve()
    gate_json = out_dir / f"{slug}.docgate.json"
    gate_cmd = [sys.executable, str(HERE / "docgate.py"),
                "--pdf", str(pdf), "--profile", str(resolved_path),
                "--template", str(tpath), "--source-map", str(map_path),
                "--json", str(gate_json)]
    if ref and ref.exists():
        gate_cmd += ["--reference", str(ref)]
    gproc = subprocess.run(gate_cmd, capture_output=True, text=True, check=False,
                           encoding="utf-8", errors="replace")
    for line in (gproc.stdout or "").rstrip().splitlines():
        log(f"  | {line}")
    for line in (gproc.stderr or "").rstrip().splitlines()[:40]:
        log(f"  | {line}")
    gate_summary = (json.loads(gate_json.read_text(encoding="utf-8"))
                    if gate_json.exists() else {})

    manifest = {
        "template": template_id,
        "template_path": str(tpath),
        "template_sha256": sha256(tpath),
        "source_profile": str(profile_path),
        "source_profile_sha256": sha256(profile_path),
        "resolved_profile": str(resolved_path),
        "resolved_profile_sha256": sha256(resolved_path),
        "transforms": {
            "stripped_networks": stripped,
            "date_notes": notes,
            "translated_strings": len(source_map),
            "translation_drift": drift_tr,
        },
        "view_contract_drift": drift_view,
        "build": build_manifest,
        "docgate": gate_summary,
        "pdf": str(pdf),
        "pdf_bytes": pdf.stat().st_size,
        "pdf_sha256": sha256(pdf),
    }
    man_path = out_dir / f"{slug}.template-manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    log(f"  EMIT   {man_path}")
    log(f"  PDF    {pdf}  ({pdf.stat().st_size} bytes, "
        f"{gate_summary.get('pages', '?')} page(s), "
        f"status={gate_summary.get('status', 'UNKNOWN')})")

    if gproc.returncode != 0:
        log(f"  ERROR docgate refused the document (exit {gproc.returncode})")
        log(f"FAILED:{template_id}")
        return 5
    log(f"SUCCESS:{template_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="render_template.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", help="template directory name, e.g. ats-en")
    ap.add_argument("--all", action="store_true", help="render every template")
    ap.add_argument("--profile", default=str(PROFILE))
    ap.add_argument("--out", help="output directory (default out/templates/<id>)")
    ap.add_argument("--reference", help="reference PDF for the expansion check")
    ap.add_argument("--drift-check", action="store_true",
                    help="compare with profile.yaml's x_views and stop")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)

    # Only directories whose template.yaml speaks THIS contract (a `render:`
    # block). templates/ also holds other document systems with their own
    # renderer and their own template shape; --all must not reach into them.
    available = []
    for path in sorted(HERE.glob("*/template.yaml")):
        try:
            spec = load_yaml(path)
        except Exception:                                      # pragma: no cover
            continue
        if isinstance(spec, dict) and isinstance(spec.get("render"), dict):
            available.append(path.parent.name)
    if args.list:
        for t in available:
            spec = load_yaml(HERE / t / "template.yaml") or {}
            log(f"  {t:<10} {str(spec.get('audience', ''))[:80]}")
        log("SUCCESS:--list")
        return 0
    if args.all:
        worst = 0
        for t in available:
            log(f"--- {t} ---")
            worst = max(worst, render(t, args))
        log("SUCCESS:--all" if worst == 0 else "FAILED:--all")
        return worst
    if not args.template:
        ap.error(f"--template is required (have: {', '.join(available)}) or use --all")
    return render(args.template, args)


if __name__ == "__main__":
    raise SystemExit(main())
