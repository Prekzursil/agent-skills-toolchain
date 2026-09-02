"""Published-before-measurement routing conflict task set.

RES-0101's catalog artifact is absent on this worktree. This unit
reconstructs a conflict-focused routing set: every conflict task has
two or more matching skills, a cwd, and a gold selection published
in this module before any strategy is scored.

Estate directory-scoped skill precedence: a skill with cwd_prefix only
enters the match set when the task cwd is under that prefix, and a
deeper scope_depth beats a user-global duplicate of the same trigger.
Generic skills are id-prefixed 'a-' so lex-min tie-breaks pick the
wrong generic on purpose.
"""
from __future__ import annotations

from typing import Any

from contract import ASK

Skill = dict[str, Any]
Task = dict[str, Any]


def _s(sid, triggers, depth, prefix, priority, layer):
    return {
        "id": sid,
        "triggers": list(triggers),
        "scope_depth": depth,
        "cwd_prefix": prefix,
        "priority": priority,
        "layer": layer,
    }


def _t(tid, family, query, cwd, gold):
    return {
        "id": tid,
        "family": family,
        "query": query,
        "cwd": cwd,
        "gold": gold,
    }


SKILLS: tuple[Skill, ...] = (
    _s("a-commit-generic", ["commit"], 0, "", 1, "user-global"),
    _s(
        "commit-msg-specific",
        ["git commit message", "commit message"],
        0,
        "",
        1,
        "user-global",
    ),
    _s("a-review-generic", ["review"], 0, "", 1, "user-global"),
    _s("security-review-specific", ["security review"], 0, "", 1, "user-global"),
    _s("a-deploy-generic", ["deploy"], 0, "", 1, "user-global"),
    _s(
        "k8s-deploy-specific",
        ["deploy kubernetes", "deploy k8s"],
        0,
        "",
        1,
        "user-global",
    ),
    _s("a-document-generic", ["document"], 0, "", 1, "user-global"),
    _s("api-document-specific", ["document the api"], 0, "", 1, "user-global"),
    _s("a-patch-generic", ["patch"], 0, "", 1, "user-global"),
    _s("security-patch-specific", ["security patch"], 0, "", 1, "user-global"),
    _s("a-release-generic", ["release"], 0, "", 1, "user-global"),
    _s("hotfix-release-specific", ["hotfix release"], 0, "", 1, "user-global"),
    _s("a-lint-global", ["lint"], 0, "", 80, "user-global"),
    _s("python-ruff-lint", ["lint"], 3, "python/", 5, "project-nested"),
    _s("a-format-global", ["format"], 0, "", 70, "user-global"),
    _s("python-black-format", ["format"], 4, "src/pkg/", 1, "project-nested"),
    _s("a-test-global", ["test"], 0, "", 60, "user-global"),
    _s("web-jest-test", ["test"], 2, "web/", 1, "project-nested"),
    _s("a-build-global", ["build"], 0, "", 50, "user-global"),
    _s("android-gradle-build", ["build"], 2, "android/", 1, "project-nested"),
    _s("a-pytest-default", ["pytest"], 1, "", 1, "project"),
    _s("pytest-integration-pin", ["pytest"], 1, "", 90, "project"),
    _s("a-lookup-default", ["lookup"], 1, "", 1, "project"),
    _s("runbook-lookup-pin", ["lookup"], 1, "", 85, "project"),
    _s("a-search-web", ["search"], 1, "", 10, "project"),
    _s("search-codebase", ["search"], 1, "", 10, "project"),
    _s("a-notes-wiki", ["notes"], 0, "", 5, "user-global"),
    _s("notes-journal", ["notes"], 0, "", 5, "user-global"),
    _s("sql-migrate-unique", ["migrate sql schema"], 1, "", 1, "project"),
    _s("sbom-generate-unique", ["generate sbom"], 1, "", 1, "project"),
)

TASKS: tuple[Task, ...] = (
    _t("A1", "specificity", "write a git commit message for this fix", "", "commit-msg-specific"),
    _t("A2", "specificity", "do a security review of this PR", "", "security-review-specific"),
    _t("A3", "specificity", "deploy kubernetes manifests to staging", "", "k8s-deploy-specific"),
    _t("A4", "specificity", "document the api endpoints", "", "api-document-specific"),
    _t("A5", "specificity", "commit message for the refactor", "", "commit-msg-specific"),
    _t("A6", "specificity", "apply the security patch to openssl", "", "security-patch-specific"),
    _t("A7", "specificity", "cut a hotfix release tonight", "", "hotfix-release-specific"),
    _t("A8", "specificity", "deploy k8s workers in eu-west", "", "k8s-deploy-specific"),
    _t("B1", "scope_depth", "lint this module", "python/app", "python-ruff-lint"),
    _t("B2", "scope_depth", "format this file", "src/pkg/util", "python-black-format"),
    _t("B3", "scope_depth", "run the test suite", "web/src", "web-jest-test"),
    _t("B4", "scope_depth", "build the project", "android/app", "android-gradle-build"),
    _t("C1", "explicit_priority", "run pytest", "repo", "pytest-integration-pin"),
    _t("C2", "explicit_priority", "lookup the error code", "repo", "runbook-lookup-pin"),
    _t("D1", "ask_the_user", "search for the token", "repo", ASK),
    _t("D2", "ask_the_user", "update the notes", "", ASK),
    _t("E1", "single-match-control", "migrate sql schema for billing", "repo", "sql-migrate-unique"),
    _t("E2", "single-match-control", "generate sbom for the artifact", "repo", "sbom-generate-unique"),
)


def skill_by_id() -> dict[str, Skill]:
    return {str(s["id"]): s for s in SKILLS}
