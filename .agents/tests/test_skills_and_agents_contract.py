from __future__ import annotations

import hashlib
import json
import pathlib
import tomllib

import yaml


HOME = pathlib.Path.home()
CONTROL_ROOT = HOME / ".agents"
SKILLS_ROOT = CONTROL_ROOT / "skills"
CODEX_AGENTS_ROOT = HOME / ".codex" / "agents"

MEMORY_SKILLS = {
    "context-sandbox",
    "deep-research",
    "design-review-loop",
    "grill-with-docs",
    "mcp-code-orchestrate",
    "mcp-fleet-curation",
    "prototype",
    "research-ops",
    "simplest-probe-first",
    "to-prd",
    "video-watermark-removal",
}

GRILL_SKILLS = {"grill-me", "grill-me-extensive", "grill-with-docs"}
CLAUDE_COMMANDS_ROOT = HOME / ".claude" / "commands"
CORE_ROLES = {
    "explorer",
    "planner",
    "worker",
    "reviewer",
    "security-reviewer",
    "ui-ux-reviewer",
    "verifier",
}


def _frontmatter(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    assert text.startswith("---\n"), f"missing YAML frontmatter: {path}"
    _, raw, _ = text.split("---", 2)
    data = yaml.safe_load(raw)
    assert isinstance(data, dict), f"invalid YAML frontmatter: {path}"
    return data


def _load_yaml(path: pathlib.Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    assert isinstance(data, dict), f"expected mapping: {path}"
    return data


def test_all_canonical_skills_have_compact_valid_frontmatter() -> None:
    skill_dirs = sorted(path for path in SKILLS_ROOT.iterdir() if path.is_dir())
    assert len(skill_dirs) >= 271

    for skill_dir in skill_dirs:
        skill_path = skill_dir / "SKILL.md"
        assert skill_path.is_file(), f"missing SKILL.md: {skill_dir.name}"
        metadata = _frontmatter(skill_path)
        assert metadata.get("name") == skill_dir.name
        description = metadata.get("description")
        assert isinstance(description, str) and description.strip()
        assert len(description) <= 300, (
            f"description is {len(description)} chars: {skill_dir.name}"
        )
        assert len(description.encode("utf-8")) <= 300, (
            f"description is {len(description.encode('utf-8'))} UTF-8 bytes: "
            f"{skill_dir.name}"
        )


def test_normalized_descriptions_do_not_end_mid_clause() -> None:
    manifest_path = (
        CONTROL_ROOT / "archive-manifests" / "skill-description-normalization.json"
    )
    normalized = json.loads(manifest_path.read_text(encoding="utf-8"))
    fragment_endings = {
        "a",
        "an",
        "and",
        "as",
        "at",
        "by",
        "for",
        "from",
        "in",
        "into",
        "of",
        "on",
        "or",
        "over",
        "plus",
        "that",
        "the",
        "to",
        "under",
        "via",
        "which",
        "with",
    }
    for entry in normalized["entries"]:
        description = _frontmatter(SKILLS_ROOT / entry["skill"] / "SKILL.md")[
            "description"
        ]
        words = [word.lower() for word in description.rstrip(".?!").split()]
        assert words[-1] not in fragment_endings, (
            f"description ends mid-clause: {entry['skill']}: {description}"
        )


def test_basic_memory_skills_declare_the_mcp_dependency() -> None:
    for skill_name in sorted(MEMORY_SKILLS):
        metadata_path = SKILLS_ROOT / skill_name / "agents" / "openai.yaml"
        assert metadata_path.is_file(), f"missing OpenAI metadata: {skill_name}"
        metadata = _load_yaml(metadata_path)
        tools = metadata.get("dependencies", {}).get("tools", [])
        assert any(
            tool.get("type") == "mcp" and tool.get("value") == "basic-memory"
            for tool in tools
            if isinstance(tool, dict)
        ), f"missing basic-memory dependency: {skill_name}"


def test_grill_trio_uses_one_shared_workflow() -> None:
    workflow = _load_yaml(CONTROL_ROOT / "workflows" / "grill.yaml")
    assert workflow["id"] == "grill"
    assert set(workflow["skills"]) == GRILL_SKILLS
    assert workflow["providers"]["claude"]["invocation"] == "/grill-me"
    assert workflow["providers"]["codex"]["invocation"] == "$grill-me"

    for skill_name in GRILL_SKILLS:
        text = (SKILLS_ROOT / skill_name / "SKILL.md").read_text(
            encoding="utf-8-sig"
        )
        assert "Shared contract: `.agents/workflows/grill.yaml`" in text
        metadata = _load_yaml(SKILLS_ROOT / skill_name / "agents" / "openai.yaml")
        assert f"${skill_name}" in metadata["interface"]["default_prompt"]
        command = CLAUDE_COMMANDS_ROOT / f"{skill_name}.md"
        command_text = command.read_text(encoding="utf-8-sig")
        assert f"~/.agents/skills/{skill_name}/SKILL.md" in command_text
        assert ".agents/workflows/grill.yaml" in command_text


def test_shared_lifecycle_has_provider_adapters_and_no_codex_git_writes() -> None:
    workflow = _load_yaml(CONTROL_ROOT / "workflows" / "lifecycle.yaml")
    assert workflow["stages"] == [
        "discover",
        "recall",
        "grill",
        "plan",
        "plan-review",
        "execute",
        "spec-review",
        "quality-review",
        "acceptance",
        "capture",
    ]
    assert workflow["limits"] == {"max_threads": 4, "max_depth": 1}
    assert workflow["providers"]["codex"]["git_write"] == "delegate-to-claude"
    assert workflow["providers"]["claude"]["git_write"] == "allowed-by-user-policy"


def test_all_codex_agent_toml_files_parse_and_core_roles_are_bounded() -> None:
    agent_paths = sorted(CODEX_AGENTS_ROOT.glob("*.toml"))
    assert len(agent_paths) == 39
    names: set[str] = set()
    loaded: dict[str, dict] = {}

    for path in agent_paths:
        agent = tomllib.loads(path.read_text(encoding="utf-8-sig"))
        assert agent.get("name") == path.stem
        assert isinstance(agent.get("description"), str) and agent["description"].strip()
        assert isinstance(agent.get("developer_instructions"), str)
        assert agent["developer_instructions"].strip()
        assert agent["name"] not in names
        names.add(agent["name"])
        loaded[agent["name"]] = agent

    registry = _load_yaml(CONTROL_ROOT / "agent-roles" / "core.yaml")
    assert registry["limits"] == {"max_threads": 4, "max_depth": 1}
    assert set(registry["roles"]) == CORE_ROLES
    assert registry["providers"] == {
        "claude": {
            "flagship": "opus",
            "worker": "sonnet",
            "fast": "haiku",
        },
        "codex": {
            "flagship": "gpt-5.6-sol",
            "worker": "gpt-5.4",
            "fast": "gpt-5.4-mini",
        },
    }

    for role_name, role in registry["roles"].items():
        agent = loaded[role_name]
        assert agent.get("model") == role["model"]
        assert role["model"] == registry["providers"]["codex"][role["tier"]]
        assert agent.get("sandbox_mode") == role["sandbox_mode"]
        assert role["tier"] in {"flagship", "worker", "fast"}


def test_legacy_markdown_agents_are_archived_with_hashes() -> None:
    assert not list(CODEX_AGENTS_ROOT.glob("*.md"))
    assert not list((CODEX_AGENTS_ROOT / "agents").glob("*.md"))

    manifest_path = CONTROL_ROOT / "archive-manifests" / "codex-agent-markdown.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert len(manifest["entries"]) == 56

    for entry in manifest["entries"]:
        archived = HOME / entry["archived_path"]
        assert archived.is_file(), f"missing archived file: {archived}"
        digest = hashlib.sha256(archived.read_bytes()).hexdigest()
        assert digest == entry["sha256"]
        assert entry["canonical_toml"].endswith(".toml")
