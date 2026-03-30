#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


CONTROLLER_REPO = "Prekzursil/quality-zero-platform"
DEFAULT_CONTROLLER_REF = "main"
WRAPPER_FILES = [
    ".github/workflows/quality-zero-platform.yml",
    ".github/workflows/quality-zero-gate.yml",
    ".github/workflows/codecov-analytics.yml",
    ".github/workflows/quality-zero-backlog.yml",
    ".github/workflows/quality-zero-remediation.yml",
]
RUN_NAMES = [
    "Quality Zero Platform",
    "Quality Zero Gate",
    "Codecov Analytics",
    "Quality Zero Remediation",
    "Quality Zero Backlog",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit quality-zero-platform rollout truth for one repo.")
    parser.add_argument("--repo", required=True, help="Target repo slug, for example Prekzursil/env-inspector")
    parser.add_argument(
        "--controller-path",
        default="",
        help="Optional local checkout or worktree of Prekzursil/quality-zero-platform",
    )
    parser.add_argument(
        "--controller-ref",
        default=DEFAULT_CONTROLLER_REF,
        help="Controller ref expected in wrapper workflow uses lines. Default: main",
    )
    parser.add_argument(
        "--fixture-dir",
        default="",
        help="Optional fixture directory for offline tests",
    )
    parser.add_argument("--format", choices=("json", "md"), default="json")
    parser.add_argument("--fail-on-drift", action="store_true")
    return parser.parse_args()


def run_command(args: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        args,
        check=True,
        capture_output=True,
        text=True,
        input=input_text,
    )
    return result.stdout


def gh_api_json(endpoint: str) -> Any:
    return json.loads(run_command(["gh", "api", endpoint]) or "null")


def gh_contents_text(repo: str, path: str, ref: str) -> str:
    payload = gh_api_json(f"repos/{repo}/contents/{path}?ref={ref}")
    content = payload.get("content", "")
    return base64.b64decode(content).decode("utf-8", "replace")


def yaml_load(text: str) -> Any:
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError:
        interpreter = find_python_with_yaml()
        if interpreter:
            stdout = run_command(
                [
                    *interpreter,
                    "-c",
                    (
                        "import json, sys, yaml; "
                        "print(json.dumps(yaml.safe_load(sys.stdin.read())))"
                    ),
                ],
                input_text=text,
            )
            return json.loads(stdout)
        raise RuntimeError(
            "PyYAML is required to parse controller configuration. "
            "Install PyYAML or set CODEX_PYTHON_WITH_YAML to an interpreter that has it."
        )
    return yaml.safe_load(text)


def find_python_with_yaml() -> list[str] | None:
    candidates: list[list[str]] = []

    override = os.environ.get("CODEX_PYTHON_WITH_YAML")
    if override:
        candidates.append([override])

    candidates.append([sys.executable])
    candidates.extend([["python"], ["py", "-3"], ["python3"]])

    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    for root in (local_app_data / "Programs" / "Python", local_app_data / "Python"):
        if not root.exists():
            continue
        for child in sorted(root.iterdir(), reverse=True):
            python_exe = child / "python.exe"
            if python_exe.exists():
                candidates.append([str(python_exe)])

    seen: set[tuple[str, ...]] = set()
    for candidate in candidates:
        key = tuple(candidate)
        if key in seen:
            continue
        seen.add(key)
        try:
            result = subprocess.run(
                [*candidate, "-c", "import yaml"],
                capture_output=True,
                text=True,
            )
        except OSError:
            continue
        if result.returncode == 0:
            return candidate
    return None


def deep_merge(base: Any, overlay: Any) -> Any:
    if isinstance(base, dict) and isinstance(overlay, dict):
        merged = dict(base)
        for key, value in overlay.items():
            merged[key] = deep_merge(merged[key], value) if key in merged else value
        return merged
    if isinstance(base, list) and isinstance(overlay, list):
        return list(base) + [item for item in overlay if item not in base]
    return overlay


def dedupe_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        value = str(item).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


class ControllerSource:
    def __init__(self, controller_path: str, controller_ref: str, fixture_dir: str) -> None:
        self.controller_path = Path(controller_path).resolve() if controller_path else None
        self.controller_ref = controller_ref
        self.fixture_dir = Path(fixture_dir).resolve() if fixture_dir else None

    def load_yaml(self, relative_path: str) -> Any:
        return yaml_load(self.load_text(relative_path))

    def load_text(self, relative_path: str) -> str:
        if self.fixture_dir:
            return (self.fixture_dir / "controller" / relative_path).read_text(encoding="utf-8")
        if self.controller_path:
            return (self.controller_path / relative_path).read_text(encoding="utf-8")
        return gh_contents_text(CONTROLLER_REPO, relative_path.replace("\\", "/"), self.controller_ref)


class LiveSource:
    def __init__(self, fixture_dir: str) -> None:
        self.fixture_dir = Path(fixture_dir).resolve() if fixture_dir else None

    @staticmethod
    def fixture_slug(repo_slug: str) -> str:
        return repo_slug.replace("/", "__")

    def load_workflow_text(self, repo_slug: str, default_branch: str, workflow_path: str) -> str | None:
        if self.fixture_dir:
            payload = json.loads(
                (self.fixture_dir / "live" / self.fixture_slug(repo_slug) / "workflows.json").read_text(encoding="utf-8")
            )
            return payload.get(workflow_path)
        try:
            return gh_contents_text(repo_slug, workflow_path, default_branch)
        except subprocess.CalledProcessError:
            return None

    def load_rulesets(self, repo_slug: str) -> list[dict[str, Any]]:
        if self.fixture_dir:
            path = self.fixture_dir / "live" / self.fixture_slug(repo_slug) / "rulesets.json"
            return json.loads(path.read_text(encoding="utf-8"))
        try:
            return gh_api_json(f"repos/{repo_slug}/rulesets") or []
        except subprocess.CalledProcessError:
            return []

    def load_runs(self, repo_slug: str, default_branch: str) -> list[dict[str, Any]]:
        if self.fixture_dir:
            path = self.fixture_dir / "live" / self.fixture_slug(repo_slug) / "runs.json"
            return json.loads(path.read_text(encoding="utf-8"))
        try:
            stdout = run_command(
                [
                    "gh",
                    "run",
                    "list",
                    "-R",
                    repo_slug,
                    "--branch",
                    default_branch,
                    "--limit",
                    "30",
                    "--json",
                    "workflowName,status,conclusion,createdAt,displayTitle",
                ]
            )
            return json.loads(stdout or "[]")
        except subprocess.CalledProcessError:
            return []


def merge_required_contexts(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, list[str]]:
    return {
        "always": dedupe_strings([*base.get("always", []), *overlay.get("always", [])]),
        "pull_request_only": dedupe_strings(
            [*base.get("pull_request_only", []), *overlay.get("pull_request_only", [])]
        ),
        "target": dedupe_strings([*base.get("target", []), *overlay.get("target", [])]),
    }


def load_stack(source: ControllerSource, stack_id: str) -> dict[str, Any]:
    payload = source.load_yaml(f"profiles/stacks/{stack_id}.yml") or {}
    parents = payload.pop("extends", [])
    if isinstance(parents, str):
        parents = [parents]
    merged: dict[str, Any] = {}
    for parent in parents:
        merged = deep_merge(merged, load_stack(source, str(parent)))
    return deep_merge(merged, payload)


def resolve_controller_expectation(source: ControllerSource, repo_slug: str) -> dict[str, Any]:
    inventory = source.load_yaml("inventory/repos.yml") or {}
    repos = inventory.get("repos", [])
    repo_entry = next((item for item in repos if item.get("slug") == repo_slug), None)
    if repo_entry is None:
        return {
            "controller_repository": CONTROLLER_REPO,
            "controller_ref": source.controller_ref,
            "repo_slug": repo_slug,
            "enrolled": False,
            "status": "partial",
            "notes": ["Repo is not enrolled in inventory/repos.yml."],
        }

    profile_id = str(repo_entry.get("profile", "")).strip()
    repo_profile = source.load_yaml(f"profiles/repos/{profile_id}.yml") or {}
    stack_id = str(repo_profile.get("stack", "")).strip()
    stack_profile = load_stack(source, stack_id)
    required_mode = str(repo_profile.get("required_contexts_mode", "merge")).strip() or "merge"

    if required_mode == "replace":
        required_contexts = {
            "always": dedupe_strings(repo_profile.get("required_contexts", {}).get("always", [])),
            "pull_request_only": dedupe_strings(repo_profile.get("required_contexts", {}).get("pull_request_only", [])),
            "target": dedupe_strings(repo_profile.get("required_contexts", {}).get("target", [])),
        }
    else:
        required_contexts = merge_required_contexts(
            stack_profile.get("required_contexts", {}),
            repo_profile.get("required_contexts", {}),
        )

    merged = deep_merge(stack_profile, repo_profile)
    default_branch = str(repo_entry.get("default_branch", merged.get("default_branch", "main"))).strip() or "main"
    target_contexts = dedupe_strings(
        required_contexts.get("target")
        or [*required_contexts.get("always", []), *required_contexts.get("pull_request_only", [])]
    )

    return {
        "controller_repository": CONTROLLER_REPO,
        "controller_ref": source.controller_ref,
        "repo_slug": repo_slug,
        "enrolled": True,
        "profile_id": profile_id,
        "stack_id": stack_id,
        "rollout": repo_entry.get("rollout", ""),
        "default_branch": default_branch,
        "expected_ruleset_name": f"quality-zero-platform / {repo_slug.split('/', 1)[1]}",
        "expected_required_contexts": target_contexts,
    }


def extract_wrapper_uses(text: str | None) -> list[dict[str, str]]:
    if not text:
        return []
    matches: list[dict[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if "uses:" not in line or "quality-zero-platform/.github/workflows/" not in line:
            continue
        value = line.split("uses:", 1)[1].strip()
        ref = value.rsplit("@", 1)[1] if "@" in value else ""
        matches.append({"uses": value, "ref": ref})
    return matches


def audit_live_state(live: LiveSource, expectation: dict[str, Any]) -> dict[str, Any]:
    if not expectation.get("enrolled"):
        return {"wrappers": [], "ruleset_present": False, "ruleset_contexts": [], "runs": []}

    repo_slug = expectation["repo_slug"]
    default_branch = expectation["default_branch"]
    wrappers: list[dict[str, Any]] = []
    for workflow_path in WRAPPER_FILES:
        text = live.load_workflow_text(repo_slug, default_branch, workflow_path)
        wrappers.append(
            {
                "path": workflow_path,
                "present": text is not None,
                "uses": extract_wrapper_uses(text),
            }
        )

    rulesets = live.load_rulesets(repo_slug)
    target_ruleset = next((item for item in rulesets if item.get("name") == expectation["expected_ruleset_name"]), None)
    live_contexts: list[str] = []
    if target_ruleset:
        for rule in target_ruleset.get("rules", []):
            if rule.get("type") != "required_status_checks":
                continue
            live_contexts = [
                item.get("context", "").strip()
                for item in rule.get("parameters", {}).get("required_status_checks", [])
                if item.get("context")
            ]
            break

    raw_runs = live.load_runs(repo_slug, default_branch)
    latest_runs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_runs:
        name = item.get("workflowName")
        if name not in RUN_NAMES or name in seen:
            continue
        seen.add(name)
        latest_runs.append(
            {
                "workflowName": name,
                "status": item.get("status", ""),
                "conclusion": item.get("conclusion", ""),
                "createdAt": item.get("createdAt", ""),
                "displayTitle": item.get("displayTitle", ""),
            }
        )

    return {
        "wrappers": wrappers,
        "ruleset_present": bool(target_ruleset),
        "ruleset_contexts": live_contexts,
        "runs": latest_runs,
    }


def classify(
    expectation: dict[str, Any],
    live_state: dict[str, Any],
    controller_ref: str,
    *,
    controller_repository: str,
) -> tuple[str, list[str], list[str]]:
    drift: list[str] = []
    notes: list[str] = []

    if not expectation.get("enrolled"):
        return "partial", drift, expectation.get("notes", [])

    missing_wrappers = [item["path"] for item in live_state["wrappers"] if not item["present"]]
    if missing_wrappers:
        drift.append("missing_wrappers")
        notes.append(f"Missing wrapper workflows: {', '.join(missing_wrappers)}")

    stale_refs: list[str] = []
    missing_uses: list[str] = []
    is_controller_self = expectation["repo_slug"] == controller_repository
    for item in live_state["wrappers"]:
        if not item["present"]:
            continue
        if not item["uses"]:
            if not is_controller_self:
                missing_uses.append(item["path"])
            continue
        refs = {use["ref"] for use in item["uses"] if use["ref"]}
        if controller_ref not in refs:
            stale_refs.append(f"{item['path']} -> {', '.join(sorted(refs)) or 'no-ref'}")
    if stale_refs:
        drift.append("stale_wrapper_refs")
        notes.append(f"Wrapper refs differ from controller ref `{controller_ref}`: {'; '.join(stale_refs)}")
    if missing_uses:
        drift.append("wrapper_not_pointing_to_controller")
        notes.append(f"Wrapper workflows do not call controller reusable workflows: {', '.join(missing_uses)}")

    if not live_state["ruleset_present"]:
        drift.append("missing_ruleset")
        notes.append(f"Live ruleset is missing: {expectation['expected_ruleset_name']}")
    else:
        expected = expectation["expected_required_contexts"]
        observed = dedupe_strings(live_state["ruleset_contexts"])
        if expected != observed:
            drift.append("ruleset_context_drift")
            notes.append("Ruleset contexts differ from controller expectation.")

    core_workflows = {"Quality Zero Platform", "Quality Zero Gate", "Codecov Analytics"}
    failed_runs = [
        run
        for run in live_state["runs"]
        if run.get("workflowName") in core_workflows and run.get("conclusion") not in {"success", "", None}
    ]
    if failed_runs:
        drift.append("failing_runs")
        notes.append(
            "Latest relevant workflow failures: "
            + ", ".join(f"{run['workflowName']}={run['conclusion']}" for run in failed_runs)
        )

    if drift:
        return "partial", drift, notes
    return "success", drift, ["Repo matches controller expectation for wrappers, ruleset, and latest run state."]


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    controller = ControllerSource(args.controller_path, args.controller_ref, args.fixture_dir)
    live = LiveSource(args.fixture_dir)
    expectation = resolve_controller_expectation(controller, args.repo)
    live_state = audit_live_state(live, expectation)
    status, drift, notes = classify(
        expectation,
        live_state,
        args.controller_ref,
        controller_repository=CONTROLLER_REPO,
    )
    return {
        "controller_repository": expectation["controller_repository"],
        "controller_ref": expectation["controller_ref"],
        "repo_slug": args.repo,
        "enrolled": expectation.get("enrolled", False),
        "profile_id": expectation.get("profile_id", ""),
        "rollout": expectation.get("rollout", ""),
        "expected_ruleset_name": expectation.get("expected_ruleset_name", ""),
        "expected_required_contexts": expectation.get("expected_required_contexts", []),
        "wrappers": live_state["wrappers"],
        "ruleset_present": live_state["ruleset_present"],
        "ruleset_contexts": live_state["ruleset_contexts"],
        "latest_runs": live_state["runs"],
        "drift_categories": drift,
        "status": status,
        "notes": notes,
    }


def format_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Quality Zero Platform Audit",
        "",
        f"- Controller: `{report['controller_repository']}@{report['controller_ref']}`",
        f"- Repo: `{report['repo_slug']}`",
        f"- Status: `{report['status']}`",
        f"- Enrolled: `{report['enrolled']}`",
    ]
    if report.get("profile_id"):
        lines.append(f"- Profile: `{report['profile_id']}`")
    if report.get("rollout"):
        lines.append(f"- Rollout: `{report['rollout']}`")
    if report.get("expected_ruleset_name"):
        lines.append(f"- Expected ruleset: `{report['expected_ruleset_name']}`")
    lines.extend(["", "## Expected contexts", ""])
    lines.extend([f"- `{item}`" for item in report.get("expected_required_contexts", [])] or ["- None"])
    lines.extend(["", "## Wrapper workflows", ""])
    for item in report.get("wrappers", []):
        if not item["present"]:
            lines.append(f"- `{item['path']}`: missing")
            continue
        uses = ", ".join(use["uses"] for use in item["uses"]) if item["uses"] else "present but no controller `uses:` entry found"
        lines.append(f"- `{item['path']}`: {uses}")
    lines.extend(["", "## Ruleset", ""])
    lines.append(f"- Present: `{report['ruleset_present']}`")
    lines.extend([f"- `{item}`" for item in report.get("ruleset_contexts", [])] or ["- No live ruleset contexts found"])
    lines.extend(["", "## Latest runs", ""])
    for item in report.get("latest_runs", []):
        lines.append(
            f"- `{item['workflowName']}`: status=`{item['status']}` conclusion=`{item['conclusion']}` title=`{item['displayTitle']}`"
        )
    if not report.get("latest_runs"):
        lines.append("- None")
    lines.extend(["", "## Drift categories", ""])
    lines.extend([f"- `{item}`" for item in report.get("drift_categories", [])] or ["- None"])
    lines.extend(["", "## Notes", ""])
    lines.extend([f"- {item}" for item in report.get("notes", [])] or ["- None"])
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    try:
        report = build_report(args)
    except (FileNotFoundError, KeyError, subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as exc:
        report = {
            "controller_repository": CONTROLLER_REPO,
            "controller_ref": args.controller_ref,
            "repo_slug": args.repo,
            "enrolled": False,
            "profile_id": "",
            "rollout": "",
            "expected_ruleset_name": "",
            "expected_required_contexts": [],
            "wrappers": [],
            "ruleset_present": False,
            "ruleset_contexts": [],
            "latest_runs": [],
            "drift_categories": ["audit_error"],
            "status": "blocked",
            "notes": [str(exc)],
        }

    if args.format == "md":
        print(format_markdown(report), end="")
    else:
        print(json.dumps(report, indent=2, sort_keys=True))

    if args.fail_on_drift and report["enrolled"] and report["status"] != "success":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
