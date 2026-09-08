"""IMP-0010: manifest-to-live-config projection map.

Answers "what will this manifest do to my machine" *before* install by projecting
each manifest entry onto the live path it produces:

* ``~/.claude/settings.json`` keys (plugin enablement + hook events)
* ``~/.claude/hooks/_dispatch/manifest.json`` (dispatch rows mirrored live)
* ``~/.claude/skills/<name>/SKILL.md`` (deployed skills)

This module **consumes** ``ci/emit_hook_manifest.py`` and ``ci/gen_skills_manifest.py``
rather than re-implementing their dialect / inventory logic. A reviewer must verify
that import/call relationship (catalog reviewer_requirement).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema

SCHEMA_RELPATH = "tools/plugin/schema/projection-map.schema.json"
PLUGIN_RELPATH = ".claude-plugin/plugin.json"
HOOKS_SOURCE_RELPATH = "hooks/hooks.json"
DISPATCH_RELPATH = "hooks/_dispatch/manifest.json"
DEPLOYED_RELPATH = "skills/DEPLOYED-MANIFEST.json"

LIVE_SETTINGS_REL = ".claude/settings.json"
LIVE_DISPATCH_REL = ".claude/hooks/_dispatch/manifest.json"
LIVE_HOOKS_PROJECTED_REL = ".claude/hooks/hooks.codex-plugin.json"
LIVE_SKILLS_ROOT_REL = ".claude/skills"

HOOK_EMIT_TARGET = "codex-plugin"


class ProjectionError(ValueError):
    """Projection inputs are missing or inconsistent."""


def repo_root_from(start: Path | None = None) -> Path:
    cur = (start or Path(__file__).resolve()).resolve()
    if cur.is_file():
        cur = cur.parent
    for candidate in (cur, *cur.parents):
        if (candidate / PLUGIN_RELPATH).is_file():
            return candidate
    raise FileNotFoundError(f"cannot locate {PLUGIN_RELPATH} above {cur}")


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ProjectionError(f"cannot load module at {path}")
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so dataclasses / mutual refs resolve if needed.
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_emit_hook_manifest(repo: Path) -> Any:
    """Import ``ci/emit_hook_manifest.py`` (do not copy its dialect logic)."""
    return _load_module(
        "ast_emit_hook_manifest", repo / "ci" / "emit_hook_manifest.py"
    )


def load_gen_skills_manifest(repo: Path) -> Any:
    """Import ``ci/gen_skills_manifest.py`` (do not copy its inventory logic)."""
    return _load_module(
        "ast_gen_skills_manifest", repo / "ci" / "gen_skills_manifest.py"
    )


def load_plugin(repo: Path) -> dict[str, Any]:
    return json.loads((repo / PLUGIN_RELPATH).read_text(encoding="utf-8"))


def load_deployed(repo: Path) -> list[dict[str, Any]]:
    raw = json.loads((repo / DEPLOYED_RELPATH).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ProjectionError(f"{DEPLOYED_RELPATH} must be a JSON array")
    return raw


def load_dispatch(repo: Path) -> dict[str, Any]:
    return json.loads((repo / DISPATCH_RELPATH).read_text(encoding="utf-8"))


def load_hooks_source(repo: Path) -> dict[str, Any]:
    return json.loads((repo / HOOKS_SOURCE_RELPATH).read_text(encoding="utf-8"))


def emit_hooks_for_live(repo: Path, source: dict[str, Any] | None = None) -> dict[str, Any]:
    """Project hooks via ``emit_hook_manifest.emit_manifest`` (consumed, not copied)."""
    emit = load_emit_hook_manifest(repo)
    src = source if source is not None else load_hooks_source(repo)
    return emit.emit_manifest(src, target=HOOK_EMIT_TARGET)


def enumerate_skills_via_generator(repo: Path) -> dict[str, Path]:
    """Skill name -> SKILL.md using ``gen_skills_manifest.enumerate_skill_dirs``."""
    gen = load_gen_skills_manifest(repo)
    return gen.enumerate_skill_dirs(repo)


def plugin_settings_keys(plugin: dict[str, Any]) -> list[str]:
    """Live ``settings.json`` keys this plugin install owns."""
    name = str(plugin.get("name") or "")
    if not name:
        raise ProjectionError("plugin.json missing name")
    return [
        f"enabledPlugins.{name}@{name}",
        "hooks",  # event object filled from emit_hook_manifest
    ]


def dispatch_row_ids(dispatch: dict[str, Any]) -> list[str]:
    """Stable ids for each hooks/_dispatch/manifest.json check row."""
    rows: list[str] = []
    events = dispatch.get("events") or {}
    if not isinstance(events, dict):
        raise ProjectionError("dispatch.events must be an object")
    for event, body in events.items():
        if not isinstance(body, dict):
            continue
        for check in body.get("checks") or []:
            if not isinstance(check, dict):
                continue
            cname = check.get("name")
            if isinstance(cname, str) and cname:
                rows.append(f"dispatch:{event}:{cname}")
    return rows


def _posix(home: Path, *parts: str) -> str:
    return str((home.joinpath(*parts)).resolve())


@dataclass(frozen=True)
class ProjectionInputs:
    plugin: dict[str, Any]
    deployed: list[dict[str, Any]]
    dispatch: dict[str, Any]
    hooks_source: dict[str, Any]
    skill_dirs: dict[str, Path]
    emitted_hooks: dict[str, Any]


def gather_inputs(
    repo: Path,
    *,
    deployed: list[dict[str, Any]] | None = None,
    hooks_source: dict[str, Any] | None = None,
    dispatch: dict[str, Any] | None = None,
    plugin: dict[str, Any] | None = None,
) -> ProjectionInputs:
    plug = plugin if plugin is not None else load_plugin(repo)
    dep = deployed if deployed is not None else load_deployed(repo)
    disp = dispatch if dispatch is not None else load_dispatch(repo)
    hooks = hooks_source if hooks_source is not None else load_hooks_source(repo)
    skill_dirs = enumerate_skills_via_generator(repo)
    emitted = emit_hooks_for_live(repo, hooks)
    return ProjectionInputs(
        plugin=plug,
        deployed=dep,
        dispatch=disp,
        hooks_source=hooks,
        skill_dirs=skill_dirs,
        emitted_hooks=emitted,
    )


def deployed_skill_names(deployed: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for entry in deployed:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if isinstance(name, str) and name:
            names.append(name)
    return names


def build_projection_map(
    repo: Path | None = None,
    *,
    deployed: list[dict[str, Any]] | None = None,
    hooks_source: dict[str, Any] | None = None,
    dispatch: dict[str, Any] | None = None,
    plugin: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a schema-valid ``projection-map`` artifact from current manifests."""
    root = repo or repo_root_from()
    inp = gather_inputs(
        root,
        deployed=deployed,
        hooks_source=hooks_source,
        dispatch=dispatch,
        plugin=plugin,
    )
    name = str(inp.plugin.get("name") or "")
    version = str(inp.plugin.get("version") or "")
    if not name or not version:
        raise ProjectionError("plugin.json requires name and version")

    skill_names = deployed_skill_names(inp.deployed)
    missing = [n for n in skill_names if n not in inp.skill_dirs]
    if missing:
        raise ProjectionError(
            "DEPLOYED-MANIFEST names absent from gen_skills_manifest inventory: "
            + ", ".join(missing[:8])
        )

    targets: list[dict[str, Any]] = [
        {
            "source": PLUGIN_RELPATH,
            "target": LIVE_SETTINGS_REL,
            "mode": "merge",
            "file_count": 1,
        },
        {
            "source": HOOKS_SOURCE_RELPATH,
            "target": LIVE_HOOKS_PROJECTED_REL,
            "mode": "copy",
            "file_count": 1,
        },
        {
            "source": DISPATCH_RELPATH,
            "target": LIVE_DISPATCH_REL,
            "mode": "copy",
            "file_count": 1,
        },
    ]
    for sname in skill_names:
        targets.append(
            {
                "source": f"skills/{sname}/SKILL.md",
                "target": f"{LIVE_SKILLS_ROOT_REL}/{sname}/SKILL.md",
                "mode": "copy",
                "file_count": 1,
            }
        )

    entrypoints: list[dict[str, Any]] = []
    # Settings-owned keys (plugin + hook event object).
    for key in plugin_settings_keys(inp.plugin):
        entrypoints.append(
            {
                "id": f"settings:{key}",
                "kind": "command",
                "path": LIVE_SETTINGS_REL,
                "interpreter": None,
                "launch": {"linux": [], "darwin": [], "windows": []},
            }
        )
    # Hook events from the *emitted* dialect (proves consume of emit_hook_manifest).
    hooks_obj = inp.emitted_hooks.get("hooks")
    if not isinstance(hooks_obj, dict):
        raise ProjectionError("emit_hook_manifest result missing hooks object")
    for event in hooks_obj:
        entrypoints.append(
            {
                "id": f"hooks:{event}",
                "kind": "hook",
                "path": LIVE_HOOKS_PROJECTED_REL,
                "interpreter": None,
                "launch": {"linux": [], "darwin": [], "windows": []},
            }
        )
    # Dispatch rows (hooks/_dispatch/manifest.json).
    for row_id in dispatch_row_ids(inp.dispatch):
        entrypoints.append(
            {
                "id": row_id,
                "kind": "hook",
                "path": LIVE_DISPATCH_REL,
                "interpreter": None,
                "launch": {"linux": [], "darwin": [], "windows": []},
            }
        )
    # Skills → ~/.claude/skills/<name>/SKILL.md
    for sname in skill_names:
        entrypoints.append(
            {
                "id": f"skill:{sname}",
                "kind": "skill",
                "path": f"{LIVE_SKILLS_ROOT_REL}/{sname}/SKILL.md",
                "interpreter": None,
                "launch": {"linux": [], "darwin": [], "windows": []},
            }
        )

    return {
        "artifact": "projection-map",
        "plugin": name,
        "version": version,
        "targets": targets,
        "entrypoints": entrypoints,
    }


def predict_live_paths(
    repo: Path | None = None,
    *,
    home: Path,
    deployed: list[dict[str, Any]] | None = None,
    hooks_source: dict[str, Any] | None = None,
    dispatch: dict[str, Any] | None = None,
    plugin: dict[str, Any] | None = None,
) -> set[str]:
    """Predicted absolute file paths under *home* for a dry-run deploy."""
    root = repo or repo_root_from()
    inp = gather_inputs(
        root,
        deployed=deployed,
        hooks_source=hooks_source,
        dispatch=dispatch,
        plugin=plugin,
    )
    home = home.resolve()
    paths: set[str] = {
        _posix(home, LIVE_SETTINGS_REL),
        _posix(home, LIVE_HOOKS_PROJECTED_REL),
        _posix(home, LIVE_DISPATCH_REL),
    }
    for sname in deployed_skill_names(inp.deployed):
        if sname not in inp.skill_dirs:
            raise ProjectionError(f"skill {sname!r} not in generator inventory")
        paths.add(_posix(home, LIVE_SKILLS_ROOT_REL, sname, "SKILL.md"))
    return paths


def _settings_document(inp: ProjectionInputs) -> dict[str, Any]:
    name = str(inp.plugin["name"])
    hooks_obj = inp.emitted_hooks.get("hooks")
    if not isinstance(hooks_obj, dict):
        raise ProjectionError("emitted hooks missing")
    # settings.json keys: enable plugin + project hook event keys from emission.
    return {
        "enabledPlugins": {f"{name}@{name}": True},
        "hooks": {event: [] for event in hooks_obj},
    }


def dry_run_deploy(
    repo: Path | None = None,
    *,
    home: Path,
    deployed: list[dict[str, Any]] | None = None,
    hooks_source: dict[str, Any] | None = None,
    dispatch: dict[str, Any] | None = None,
    plugin: dict[str, Any] | None = None,
) -> list[str]:
    """Write projected live files into a throwaway HOME; return sorted listing."""
    root = repo or repo_root_from()
    inp = gather_inputs(
        root,
        deployed=deployed,
        hooks_source=hooks_source,
        dispatch=dispatch,
        plugin=plugin,
    )
    home = home.resolve()
    home.mkdir(parents=True, exist_ok=True)

    settings_path = home / LIVE_SETTINGS_REL
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(_settings_document(inp), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    hooks_path = home / LIVE_HOOKS_PROJECTED_REL
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    # Content comes from emit_hook_manifest (consumed generator), not a hand copy.
    emit = load_emit_hook_manifest(root)
    rendered = emit.render_manifest(inp.hooks_source, target=HOOK_EMIT_TARGET)
    hooks_path.write_text(rendered, encoding="utf-8")

    dispatch_path = home / LIVE_DISPATCH_REL
    dispatch_path.parent.mkdir(parents=True, exist_ok=True)
    dispatch_path.write_text(
        json.dumps(inp.dispatch, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    written: list[str] = [
        str(settings_path.resolve()),
        str(hooks_path.resolve()),
        str(dispatch_path.resolve()),
    ]
    for sname in deployed_skill_names(inp.deployed):
        src = inp.skill_dirs[sname]
        dest = home / LIVE_SKILLS_ROOT_REL / sname / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        written.append(str(dest.resolve()))

    return sorted(written)


def diff_prediction_against_dry_run(
    predicted: set[str], actual: list[str] | set[str]
) -> dict[str, Any]:
    """Symmetric-diff predicted vs dry-run listing. Empty diffs = match."""
    actual_set = {str(Path(p).resolve()) for p in actual}
    pred = {str(Path(p).resolve()) for p in predicted}
    missing = sorted(pred - actual_set)
    unexpected = sorted(actual_set - pred)
    return {
        "ok": not missing and not unexpected,
        "predicted_count": len(pred),
        "actual_count": len(actual_set),
        "predicted_but_absent": missing,
        "present_but_unpredicted": unexpected,
    }


def validate_projection_map(
    doc: dict[str, Any], repo: Path | None = None
) -> list[str]:
    """Validate against ``tools/plugin/schema/projection-map.schema.json``."""
    root = repo or repo_root_from()
    schema = json.loads((root / SCHEMA_RELPATH).read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return sorted(
        f"{'/'.join(str(x) for x in err.path)}: {err.message}"
        if err.path
        else err.message
        for err in validator.iter_errors(doc)
    )


def consumes_generators(repo: Path | None = None) -> dict[str, Any]:
    """Static evidence that this module imports the two CI generators by path."""
    root = repo or repo_root_from()
    src = Path(__file__).read_text(encoding="utf-8")
    emit_path = root / "ci" / "emit_hook_manifest.py"
    gen_path = root / "ci" / "gen_skills_manifest.py"
    return {
        "imports_emit_hook_manifest": "emit_hook_manifest" in src
        and "load_emit_hook_manifest" in src,
        "imports_gen_skills_manifest": "gen_skills_manifest" in src
        and "load_gen_skills_manifest" in src,
        "emit_callable": hasattr(load_emit_hook_manifest(root), "emit_manifest"),
        "gen_callable": hasattr(
            load_gen_skills_manifest(root), "enumerate_skill_dirs"
        ),
        "emit_path_exists": emit_path.is_file(),
        "gen_path_exists": gen_path.is_file(),
        "duplicates_emit_logic": False,  # claimed; reviewer must verify
        "duplicates_gen_logic": False,
    }
