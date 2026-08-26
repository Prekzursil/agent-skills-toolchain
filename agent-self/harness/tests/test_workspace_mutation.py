from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import harness.workspace_mutation as workspace_mutation
from harness.workspace_mutation import (
    MutationPlanningError,
    ResolvedTarget,
    build_mutation_plan,
)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    return repo


def _real_resolver(raw_target: str, base_dir: Path, repo_root: Path) -> ResolvedTarget:
    candidate = Path(raw_target)
    absolute = candidate if candidate.is_absolute() else base_dir / candidate
    physical = absolute.resolve(strict=False)
    return ResolvedTarget(
        relative_path=physical.relative_to(repo_root.resolve(strict=True)),
        absolute_path=absolute,
        exists=physical.exists(),
    )


def _payload_sha(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_write_plan_keeps_exact_semantics_and_python_symbols(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    payload = {
        "file_path": str(repo / "src" / "worker.py"),
        "content": (
            "def outer():\n"
            "    def inner():\n"
            "        return 'nested'\n"
            "    return inner()\n\n"
            "class Service:\n"
            "    pass\n\n"
            "TEXT = 'def fake():\\n    pass'\n"
        ),
    }

    plan = build_mutation_plan(
        tool_name="Write",
        payload=payload,
        owner="session-123",
        tool_use_id="tool-123",
        repo_root=repo,
        base_dir=repo,
        resolve_target=_real_resolver,
    )

    assert plan.operation_id == "tool-123"
    assert plan.payload_sha256 == _payload_sha(payload)
    assert plan.targets == ("src/worker.py",)
    mutation = plan.mutations[0]
    assert mutation.kind == "add"
    assert mutation.target_relative_path == "src/worker.py"
    assert mutation.source_relative_path is None
    assert mutation.target_exists_before is False
    assert mutation.postimage_bytes == payload["content"].encode("utf-8")
    assert (
        mutation.postimage_sha256
        == hashlib.sha256(mutation.postimage_bytes).hexdigest()
    )
    assert mutation.source_basename == "worker.py"
    assert mutation.top_level_symbols == ("outer", "Service")
    assert mutation.line_ending == "lf"
    assert mutation.has_final_newline is True


def test_write_empty_content_hashes_empty_bytes(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    plan = build_mutation_plan(
        tool_name="Write",
        payload={"file_path": str(repo / "docs" / "empty.txt"), "content": ""},
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=repo,
        resolve_target=_real_resolver,
    )

    mutation = plan.mutations[0]
    assert mutation.postimage_bytes == b""
    assert mutation.postimage_sha256 == hashlib.sha256(b"").hexdigest()


@pytest.mark.parametrize("replace_all", [None, 0, 1, "true"])
def test_replace_all_must_be_explicit_bool(tmp_path: Path, replace_all: object) -> None:
    repo = _repo(tmp_path)
    target = repo / "src" / "edit.py"
    target.parent.mkdir(parents=True)
    target.write_text("value = 1\n", encoding="utf-8")

    with pytest.raises(
        MutationPlanningError, match="replace_all must be an explicit boolean"
    ):
        build_mutation_plan(
            tool_name="Edit",
            payload={
                "file_path": str(target),
                "old_string": "1",
                "new_string": "2",
                "replace_all": replace_all,
            },
            owner="session-123",
            tool_use_id=None,
            repo_root=repo,
            base_dir=repo,
            resolve_target=_real_resolver,
        )


def test_multiedit_produces_update_semantics(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    target = repo / "src" / "service.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "def first():\n    return 1\n\ndef second():\n    return 2\n",
        encoding="utf-8",
        newline="\n",
    )

    plan = build_mutation_plan(
        tool_name="MultiEdit",
        payload={
            "file_path": str(target),
            "edits": [
                {"old_string": "return 1", "new_string": "return 10"},
                {"old_string": "return 2", "new_string": "return 20"},
            ],
        },
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=repo,
        resolve_target=_real_resolver,
    )

    mutation = plan.mutations[0]
    assert mutation.kind == "update"
    assert mutation.target_exists_before is True
    assert mutation.source_relative_path is None
    assert mutation.postimage_bytes == (
        "def first():\n    return 10\n\ndef second():\n    return 20\n".encode("utf-8")
    )
    assert mutation.top_level_symbols == ("first", "second")


def test_structured_edit_preserves_mixed_line_endings_using_first_style(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    target = repo / "src" / "mixed_edit.py"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"first = 1\r\nsecond = 2\nthird = 3\r")

    plan = build_mutation_plan(
        tool_name="Edit",
        payload={
            "file_path": str(target),
            "old_string": "second = 2",
            "new_string": "second = 20\ninserted = 5",
        },
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=repo,
        resolve_target=_real_resolver,
        line_ending_mode="preserve",
    )

    mutation = plan.mutations[0]
    assert mutation.postimage_bytes == (
        b"first = 1\r\nsecond = 20\r\ninserted = 5\nthird = 3\r"
    )
    assert mutation.line_ending == "mixed"


def test_unsupported_source_extension_fails_closed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    with pytest.raises(MutationPlanningError, match="no syntax-aware symbol parser"):
        build_mutation_plan(
            tool_name="Write",
            payload={
                "file_path": str(repo / "src" / "worker.js"),
                "content": "export function worker() {}\n",
            },
            owner="session-123",
            tool_use_id=None,
            repo_root=repo,
            base_dir=repo,
            resolve_target=_real_resolver,
        )


def test_doc_family_keeps_numeric_identifiers_and_strips_version_marker(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)

    plan = build_mutation_plan(
        tool_name="Write",
        payload={
            "file_path": str(repo / "docs" / "report-2026-v2.md"),
            "content": "content\n",
        },
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=repo,
        resolve_target=_real_resolver,
    )

    assert plan.mutations[0].doc_family == "report-2026"


def test_forged_resolver_outputs_are_rejected(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    target = repo / "src" / "worker.py"
    target.parent.mkdir(parents=True)
    target.write_text("def worker():\n    return 1\n", encoding="utf-8")

    resolvers = [
        lambda raw, base, root: ResolvedTarget(
            relative_path=Path("../escape.py"),
            absolute_path=target,
            exists=True,
        ),
        lambda raw, base, root: ResolvedTarget(
            relative_path=Path("src/worker.py"),
            absolute_path=repo.parent / "worker.py",
            exists=False,
        ),
        lambda raw, base, root: ResolvedTarget(
            relative_path=Path("src/other.py"),
            absolute_path=target,
            exists=True,
        ),
        lambda raw, base, root: ResolvedTarget(
            relative_path=Path("src/worker.py"),
            absolute_path=target,
            exists=False,
        ),
        lambda raw, base, root: ResolvedTarget(
            relative_path=Path("src/ads:stream.py"),
            absolute_path=target,
            exists=True,
        ),
    ]

    for resolver in resolvers:
        with pytest.raises(MutationPlanningError):
            build_mutation_plan(
                tool_name="Edit",
                payload={
                    "file_path": str(target),
                    "old_string": "return 1",
                    "new_string": "return 2",
                },
                owner="session-123",
                tool_use_id=None,
                repo_root=repo,
                base_dir=repo,
                resolve_target=resolver,
            )


def test_move_rejects_same_path_and_case_alias(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    source = repo / "src" / "Worker.py"
    source.parent.mkdir(parents=True)
    source.write_text("def worker():\n    return 1\n", encoding="utf-8", newline="\n")
    patch = """*** Begin Patch
*** Update File: src/Worker.py
*** Move to: src/worker.py
@@
-def worker():
+def worker():
     return 1
*** End Patch
"""

    def forged_resolver(
        raw_target: str, base_dir: Path, repo_root: Path
    ) -> ResolvedTarget:
        if raw_target == "src/worker.py":
            return ResolvedTarget(
                relative_path=Path("src/worker.py"),
                absolute_path=source,
                exists=True,
            )
        return _real_resolver(raw_target, base_dir, repo_root)

    with pytest.raises(MutationPlanningError, match="same physical file"):
        build_mutation_plan(
            tool_name="apply_patch",
            payload=patch,
            owner="session-123",
            tool_use_id=None,
            repo_root=repo,
            base_dir=repo,
            resolve_target=forged_resolver,
        )


def test_move_rejects_reparse_alias(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    source = repo / "src" / "worker.py"
    source.parent.mkdir(parents=True)
    source.write_text("def worker():\n    return 1\n", encoding="utf-8")
    alias = repo / "src" / "worker-alias.py"
    try:
        alias.symlink_to(source)
    except OSError:
        pytest.skip("symlink creation is unavailable in this environment")
    patch = """*** Begin Patch
*** Update File: src/worker.py
*** Move to: src/worker-alias.py
@@
-def worker():
+def worker():
     return 1
*** End Patch
"""

    with pytest.raises(MutationPlanningError, match="same physical file"):
        build_mutation_plan(
            tool_name="apply_patch",
            payload=patch,
            owner="session-123",
            tool_use_id=None,
            repo_root=repo,
            base_dir=repo,
            resolve_target=_real_resolver,
        )


def test_apply_patch_accepts_environment_id_and_unheaded_plus_only_update_at_eof(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    target = repo / "src" / "greeter.py"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"class Greeter:\r\n    pass\r\n")

    plan = build_mutation_plan(
        tool_name="apply_patch",
        payload={
            "patch": """*** Begin Patch
*** Environment ID: env-123
*** Update File: src/greeter.py
+def tail():
+    return "tail"
*** End of File
*** End Patch
""",
            "environment_id": "env-123",
        },
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=repo,
        resolve_target=_real_resolver,
        line_ending_mode="preserve",
    )

    mutation = plan.mutations[0]
    assert mutation.kind == "update"
    assert mutation.source_relative_path is None
    assert mutation.source_exists_before is None
    assert mutation.line_ending == "crlf"
    assert mutation.postimage_bytes == (
        b'class Greeter:\r\n    pass\r\ndef tail():\r\n    return "tail"\r\n'
    )
    assert mutation.top_level_symbols == ("Greeter", "tail")


def test_apply_patch_add_file_without_hunk_header_is_valid(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    plan = build_mutation_plan(
        tool_name="apply_patch",
        payload="""*** Begin Patch
*** Add File: src/new_file.py
+def created():
+    return 1
*** End Patch
""",
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=repo,
        resolve_target=_real_resolver,
    )

    mutation = plan.mutations[0]
    assert mutation.kind == "add"
    assert mutation.target_relative_path == "src/new_file.py"
    assert mutation.postimage_bytes == b"def created():\n    return 1\n"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("@@\n+def created():\n", "patch add body must contain only direct additions"),
        (" context\n+def created():\n", "patch add body must contain only additions"),
        ("-removed\n+def created():\n", "patch add body must contain only additions"),
        (
            "+def created():\n*** End of File\n",
            "patch add body must contain only direct additions",
        ),
    ],
)
def test_apply_patch_add_file_rejects_non_direct_add_bodies(
    tmp_path: Path, body: str, message: str
) -> None:
    repo = _repo(tmp_path)

    with pytest.raises(MutationPlanningError, match=message):
        build_mutation_plan(
            tool_name="apply_patch",
            payload=(
                f"*** Begin Patch\n*** Add File: src/new_file.py\n{body}*** End Patch\n"
            ),
            owner="session-123",
            tool_use_id=None,
            repo_root=repo,
            base_dir=repo,
            resolve_target=_real_resolver,
        )


def test_apply_patch_workspace_strict_blocks_add_over_existing_path(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    target = repo / "src" / "existing.py"
    target.parent.mkdir(parents=True)
    target.write_text("value = 1\n", encoding="utf-8", newline="\n")

    with pytest.raises(
        MutationPlanningError,
        match="workspace_strict policy blocks Add File over existing path: src/existing.py",
    ):
        build_mutation_plan(
            tool_name="apply_patch",
            payload="""*** Begin Patch
*** Add File: src/existing.py
+value = 2
*** End Patch
""",
            owner="session-123",
            tool_use_id=None,
            repo_root=repo,
            base_dir=repo,
            resolve_target=_real_resolver,
        )


def test_write_rejects_existing_regular_file_ancestor(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    parent_file = repo / "src" / "existing.py"
    parent_file.parent.mkdir(parents=True)
    parent_file.write_text("value = 1\n", encoding="utf-8", newline="\n")

    with pytest.raises(
        MutationPlanningError,
        match=r"resolver target ancestor is not a directory: src/existing\.py",
    ):
        build_mutation_plan(
            tool_name="Write",
            payload={
                "file_path": str(parent_file / "child.py"),
                "content": "value = 2\n",
            },
            owner="session-123",
            tool_use_id=None,
            repo_root=repo,
            base_dir=repo,
            resolve_target=_real_resolver,
        )


def test_apply_patch_add_rejects_symlink_ancestor(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    real_dir = repo / "src" / "real"
    real_dir.mkdir(parents=True)
    alias_dir = repo / "src" / "alias"
    try:
        alias_dir.symlink_to(real_dir, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable in this environment")

    with pytest.raises(
        MutationPlanningError,
        match="resolver target ancestor is not a directory: src/alias",
    ):
        build_mutation_plan(
            tool_name="apply_patch",
            payload="""*** Begin Patch
*** Add File: src/alias/new_file.py
+value = 1
*** End Patch
""",
            owner="session-123",
            tool_use_id=None,
            repo_root=repo,
            base_dir=repo,
            resolve_target=_real_resolver,
        )


def test_apply_patch_preserves_cr_line_endings(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    target = repo / "src" / "legacy.py"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"def worker():\r    return 1\r")

    plan = build_mutation_plan(
        tool_name="apply_patch",
        payload="""*** Begin Patch
*** Update File: src/legacy.py
@@ def worker():
-    return 1
+    return 2
*** End Patch
""",
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=repo,
        resolve_target=_real_resolver,
    )

    assert plan.mutations[0].postimage_bytes == b"def worker():\r    return 2\r"
    assert plan.mutations[0].line_ending == "cr"


def test_apply_patch_preserves_mixed_line_endings(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    target = repo / "src" / "mixed.py"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"first = 1\r\nsecond = 2\nthird = 3\r")

    plan = build_mutation_plan(
        tool_name="apply_patch",
        payload="""*** Begin Patch
*** Update File: src/mixed.py
@@
 first = 1
-second = 2
+second = 20
 third = 3
*** End Patch
""",
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=repo,
        resolve_target=_real_resolver,
    )

    assert (
        plan.mutations[0].postimage_bytes == b"first = 1\r\nsecond = 20\r\nthird = 3\r"
    )
    assert plan.mutations[0].line_ending == "mixed"


def test_apply_patch_insertion_after_unterminated_final_context_separates_lines(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    target = repo / "src" / "tail_insert.py"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"value = 1")

    plan = build_mutation_plan(
        tool_name="apply_patch",
        payload="""*** Begin Patch
*** Update File: src/tail_insert.py
@@
 value = 1
+value = 2
*** End Patch
""",
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=repo,
        resolve_target=_real_resolver,
        line_ending_mode="preserve",
    )

    mutation = plan.mutations[0]
    assert mutation.postimage_bytes == b"value = 1\nvalue = 2\n"
    assert mutation.has_final_newline is True


def test_apply_patch_end_of_file_only_constrains_placement(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    target = repo / "src" / "tail.py"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"value = 1\n")

    plan = build_mutation_plan(
        tool_name="apply_patch",
        payload="""*** Begin Patch
*** Update File: src/tail.py
@@
-value = 1
+value = 2
*** End of File
*** End Patch
""",
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=repo,
        resolve_target=_real_resolver,
    )

    mutation = plan.mutations[0]
    assert mutation.postimage_bytes == b"value = 2\n"
    assert mutation.has_final_newline is True


def test_apply_patch_move_semantics_keep_exact_postimage(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    source = repo / "src" / "move_me.py"
    source.parent.mkdir(parents=True)
    source.write_text("def old_name():\n    return 1\n", encoding="utf-8", newline="\n")

    plan = build_mutation_plan(
        tool_name="apply_patch",
        payload="""*** Begin Patch
*** Update File: src/move_me.py
*** Move to: src/renamed.py
@@
-def old_name():
+def new_name():
     return 1
*** End Patch
""",
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=repo,
        resolve_target=_real_resolver,
    )

    mutation = plan.mutations[0]
    assert plan.targets == ("src/move_me.py", "src/renamed.py")
    assert mutation.kind == "move"
    assert mutation.source_relative_path == "src/move_me.py"
    assert mutation.target_relative_path == "src/renamed.py"
    assert mutation.source_exists_before is True
    assert mutation.target_exists_before is False
    assert mutation.postimage_bytes == b"def new_name():\n    return 1\n"
    assert mutation.top_level_symbols == ("new_name",)


def test_apply_patch_rejects_move_target_that_already_exists(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    source = repo / "src" / "move_me.py"
    target = repo / "src" / "renamed.py"
    source.parent.mkdir(parents=True)
    source.write_text("def old_name():\n    return 1\n", encoding="utf-8", newline="\n")
    target.write_text("def existing():\n    return 2\n", encoding="utf-8", newline="\n")

    with pytest.raises(
        MutationPlanningError,
        match="workspace_strict policy blocks Move over existing path: src/renamed.py",
    ):
        build_mutation_plan(
            tool_name="apply_patch",
            payload="""*** Begin Patch
*** Update File: src/move_me.py
*** Move to: src/renamed.py
@@
-def old_name():
+def new_name():
     return 1
*** End Patch
""",
            owner="session-123",
            tool_use_id=None,
            repo_root=repo,
            base_dir=repo,
            resolve_target=_real_resolver,
        )


def test_apply_patch_rejects_duplicate_add_targets(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    with pytest.raises(
        MutationPlanningError,
        match="duplicate patch path collision: src/repeat.py conflicts with src/repeat.py",
    ):
        build_mutation_plan(
            tool_name="apply_patch",
            payload="""*** Begin Patch
*** Add File: src/repeat.py
+value = 1
*** Add File: src/repeat.py
+value = 2
*** End Patch
""",
            owner="session-123",
            tool_use_id=None,
            repo_root=repo,
            base_dir=repo,
            resolve_target=_real_resolver,
        )


def test_apply_patch_rejects_duplicate_move_destinations(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    src_a = repo / "src" / "a.py"
    src_b = repo / "src" / "b.py"
    src_a.parent.mkdir(parents=True)
    src_a.write_text("def a():\n    return 1\n", encoding="utf-8", newline="\n")
    src_b.write_text("def b():\n    return 2\n", encoding="utf-8", newline="\n")

    with pytest.raises(
        MutationPlanningError,
        match="duplicate patch path collision: src/target.py conflicts with src/target.py",
    ):
        build_mutation_plan(
            tool_name="apply_patch",
            payload="""*** Begin Patch
*** Update File: src/a.py
*** Move to: src/target.py
@@
-def a():
+def moved_a():
     return 1
*** Update File: src/b.py
*** Move to: src/target.py
@@
-def b():
+def moved_b():
     return 2
*** End Patch
""",
            owner="session-123",
            tool_use_id=None,
            repo_root=repo,
            base_dir=repo,
            resolve_target=_real_resolver,
        )


def test_apply_patch_uses_runtime_base_dir_for_nested_cwd_resolution(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    root_file = repo / "file.py"
    subdir = repo / "sub"
    subdir.mkdir()
    nested_file = subdir / "file.py"
    root_file.write_text(
        "def root_version():\n    return 1\n", encoding="utf-8", newline="\n"
    )
    nested_file.write_text(
        "def nested_version():\n    return 2\n", encoding="utf-8", newline="\n"
    )

    nested_plan = build_mutation_plan(
        tool_name="apply_patch",
        payload="""*** Begin Patch
*** Update File: file.py
@@
-def nested_version():
+def nested_version_patched():
     return 2
*** End Patch
""",
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=subdir,
        resolve_target=_real_resolver,
    )
    root_plan = build_mutation_plan(
        tool_name="apply_patch",
        payload="""*** Begin Patch
*** Update File: ../file.py
@@
-def root_version():
+def root_version_patched():
     return 1
*** End Patch
""",
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=subdir,
        resolve_target=_real_resolver,
    )

    assert nested_plan.targets == ("sub/file.py",)
    assert nested_plan.mutations[0].postimage_bytes == (
        b"def nested_version_patched():\n    return 2\n"
    )
    assert root_plan.targets == ("file.py",)
    assert root_plan.mutations[0].postimage_bytes == (
        b"def root_version_patched():\n    return 1\n"
    )


@pytest.mark.parametrize(
    ("tool_name", "payload"),
    [
        ("Write", {"file_path": "src/folder", "content": "value = 1\n"}),
        (
            "Edit",
            {"file_path": "src/folder", "old_string": "value", "new_string": "other"},
        ),
        (
            "apply_patch",
            """*** Begin Patch
*** Update File: src/folder
@@
-value
+other
*** End Patch
""",
        ),
    ],
)
def test_existing_non_regular_targets_are_rejected(
    tmp_path: Path, tool_name: str, payload: object
) -> None:
    repo = _repo(tmp_path)
    directory = repo / "src" / "folder"
    directory.mkdir(parents=True)

    with pytest.raises(
        MutationPlanningError, match="resolver returned a non-regular file target"
    ):
        build_mutation_plan(
            tool_name=tool_name,
            payload=payload,
            owner="session-123",
            tool_use_id=None,
            repo_root=repo,
            base_dir=repo,
            resolve_target=_real_resolver,
        )


def test_line_ending_mode_must_be_preserve(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    with pytest.raises(MutationPlanningError, match="unsupported line ending mode"):
        build_mutation_plan(
            tool_name="Write",
            payload={"file_path": str(repo / "src" / "worker.py"), "content": "pass\n"},
            owner="session-123",
            tool_use_id=None,
            repo_root=repo,
            base_dir=repo,
            resolve_target=_real_resolver,
            line_ending_mode="normalize",  # type: ignore[arg-type]
        )


def test_apply_patch_chooses_first_body_match_after_cursor(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    target = repo / "src" / "repeat.py"
    target.parent.mkdir(parents=True)
    target.write_text("keep\nmatch\nkeep\nmatch\n", encoding="utf-8", newline="\n")

    plan = build_mutation_plan(
        tool_name="apply_patch",
        payload="""*** Begin Patch
*** Update File: src/repeat.py
@@
 keep
-match
+fresh
*** End Patch
""",
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=repo,
        resolve_target=_real_resolver,
    )

    assert plan.mutations[0].postimage_bytes == b"keep\nfresh\nkeep\nmatch\n"


def test_apply_patch_accepts_blank_unprefixed_context_line(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    target = repo / "src" / "blank_context.py"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"\nvalue = 1\n")

    plan = build_mutation_plan(
        tool_name="apply_patch",
        payload="""*** Begin Patch
*** Update File: src/blank_context.py
@@

+value = 0
 value = 1
*** End Patch
""",
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=repo,
        resolve_target=_real_resolver,
    )

    assert plan.mutations[0].postimage_bytes == b"\nvalue = 0\nvalue = 1\n"


def test_apply_patch_header_anchored_pure_add_validates_anchor_but_still_inserts_at_eof(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    anchored_target = repo / "src" / "anchored_add.py"
    anchored_target.parent.mkdir(parents=True)
    anchored_target.write_text("anchor\nend\n", encoding="utf-8", newline="\n")
    eof_target = repo / "src" / "eof_add.py"
    eof_target.write_text("anchor\nend\n", encoding="utf-8", newline="\n")

    anchored_plan = build_mutation_plan(
        tool_name="apply_patch",
        payload="""*** Begin Patch
*** Update File: src/anchored_add.py
@@ anchor
+inserted
*** End Patch
""",
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=repo,
        resolve_target=_real_resolver,
    )
    eof_plan = build_mutation_plan(
        tool_name="apply_patch",
        payload="""*** Begin Patch
*** Update File: src/eof_add.py
@@
+inserted
*** End Patch
""",
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=repo,
        resolve_target=_real_resolver,
    )

    assert anchored_plan.mutations[0].postimage_bytes == b"anchor\nend\ninserted\n"
    assert eof_plan.mutations[0].postimage_bytes == b"anchor\nend\ninserted\n"


def test_apply_patch_pure_add_keeps_search_cursor_separate_from_eof_insertion(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    target = repo / "src" / "pure_add_cursor.txt"
    target.parent.mkdir(parents=True)
    target.write_text(
        "anchor\nbefore\nanchor\nreplace\nend\n", encoding="utf-8", newline="\n"
    )

    plan = build_mutation_plan(
        tool_name="apply_patch",
        payload="""*** Begin Patch
*** Update File: src/pure_add_cursor.txt
@@ anchor
+inserted
@@
-replace
+done
*** End Patch
""",
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=repo,
        resolve_target=_real_resolver,
    )

    assert plan.mutations[0].postimage_bytes == (
        b"anchor\nbefore\nanchor\ndone\nend\ninserted\n"
    )


def test_apply_patch_sequential_cursor_uses_postimage_coordinates_for_nonempty_hunks(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    target = repo / "src" / "postimage_cursor.txt"
    target.parent.mkdir(parents=True)
    target.write_text("a\nb\nc\n", encoding="utf-8", newline="\n")

    plan = build_mutation_plan(
        tool_name="apply_patch",
        payload="""*** Begin Patch
*** Update File: src/postimage_cursor.txt
@@
-a
@@
-b
+B
*** End Patch
""",
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=repo,
        resolve_target=_real_resolver,
    )

    assert plan.mutations[0].postimage_bytes == b"B\nc\n"


def test_apply_patch_later_hunks_do_not_match_newly_inserted_text(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    target = repo / "src" / "inserted_text_cursor.txt"
    target.parent.mkdir(parents=True)
    target.write_text("x\ny\nc\n", encoding="utf-8", newline="\n")

    with pytest.raises(MutationPlanningError, match="missing patch context"):
        build_mutation_plan(
            tool_name="apply_patch",
            payload="""*** Begin Patch
*** Update File: src/inserted_text_cursor.txt
@@
-x
+a
+b
@@
-b
+B
*** End Patch
""",
            owner="session-123",
            tool_use_id=None,
            repo_root=repo,
            base_dir=repo,
            resolve_target=_real_resolver,
        )


def test_existing_target_metadata_uses_single_stat_and_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    target = repo / "src" / "tracked.py"
    target.parent.mkdir(parents=True)
    target.write_text("value = 1\n", encoding="utf-8", newline="\n")

    baseline_plan = build_mutation_plan(
        tool_name="Edit",
        payload={
            "file_path": str(target),
            "old_string": "value = 1",
            "new_string": "value = 2",
        },
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=repo,
        resolve_target=_real_resolver,
    )
    assert baseline_plan.mutations[0].target_file_identity is not None

    original_stat = workspace_mutation.Path.stat

    def guarded_stat(self: Path) -> object:
        if self == target.resolve(strict=False):
            raise PermissionError("blocked for test")
        return original_stat(self)

    monkeypatch.setattr(workspace_mutation.Path, "stat", guarded_stat)

    with pytest.raises(MutationPlanningError, match="resolver target is unreadable"):
        build_mutation_plan(
            tool_name="Edit",
            payload={
                "file_path": str(target),
                "old_string": "value = 1",
                "new_string": "value = 2",
            },
            owner="session-123",
            tool_use_id=None,
            repo_root=repo,
            base_dir=repo,
            resolve_target=_real_resolver,
        )


def test_apply_patch_body_match_uses_upstream_precedence_and_cursor(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    target = repo / "src" / "precedence_body.txt"
    target.parent.mkdir(parents=True)
    target.write_text(
        " one \none\none   \n  spaced\nsmart \u2014 quote\n",
        encoding="utf-8",
        newline="\n",
    )

    plan = build_mutation_plan(
        tool_name="apply_patch",
        payload="""*** Begin Patch
*** Update File: src/precedence_body.txt
@@
-one
+exact
@@
-one
+rstrip
@@
-spaced
+trim
@@
-smart - quote
+normalized
*** End Patch
""",
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=repo,
        resolve_target=_real_resolver,
    )

    assert plan.mutations[0].postimage_bytes == (
        b" one \nexact\nrstrip\ntrim\nnormalized\n"
    )


def test_apply_patch_anchor_match_uses_upstream_precedence_and_cursor(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    target = repo / "src" / "precedence_anchor.txt"
    target.parent.mkdir(parents=True)
    target.write_text(
        "  def alpha():\n"
        "return 1\n"
        "def alpha():\n"
        "return 2\n"
        "section \u2014 1\n"
        "value = 3\n"
        "section - 1\n"
        "value = 4\n"
        "  section \u2014 2  \n"
        "value = 5\n",
        encoding="utf-8",
        newline="\n",
    )

    plan = build_mutation_plan(
        tool_name="apply_patch",
        payload="""*** Begin Patch
*** Update File: src/precedence_anchor.txt
@@ def alpha():
-return 2
+return 20
@@ section - 1
-value = 4
+value = 40
@@ section - 2
-value = 5
+value = 50
*** End Patch
""",
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=repo,
        resolve_target=_real_resolver,
    )

    assert plan.mutations[0].postimage_bytes == (
        b"  def alpha():\n"
        b"return 1\n"
        b"def alpha():\n"
        b"return 20\n"
        b"section \xe2\x80\x94 1\n"
        b"value = 3\n"
        b"section - 1\n"
        b"value = 40\n"
        b"  section \xe2\x80\x94 2  \n"
        b"value = 50\n"
    )


@pytest.mark.parametrize(
    ("patch_text", "expected_bytes"),
    [
        (
            """*** Begin Patch
  *** Update File: src/padded.py
@@
-one
+two
*** End Patch
""",
            b"two\n",
        ),
        (
            """
 *** Begin Patch
*** Update File: src/padded.py
@@
-one
+two
*** End Patch 

""",
            b"two\n",
        ),
        (
            """*** Begin Patch 
*** Update File: src/padded.py
@@
-one
+two
 *** End Patch
""",
            b"two\n",
        ),
    ],
)
def test_apply_patch_accepts_upstream_whitespace_padded_markers_and_directives(
    tmp_path: Path, patch_text: str, expected_bytes: bytes
) -> None:
    repo = _repo(tmp_path)
    target = repo / "src" / "padded.py"
    target.parent.mkdir(parents=True)
    target.write_text("one\n", encoding="utf-8", newline="\n")

    plan = build_mutation_plan(
        tool_name="apply_patch",
        payload=patch_text,
        owner="session-123",
        tool_use_id=None,
        repo_root=repo,
        base_dir=repo,
        resolve_target=_real_resolver,
    )

    assert plan.mutations[0].postimage_bytes == expected_bytes


@pytest.mark.parametrize(
    ("patch_text", "message"),
    [
        (
            """*** Begin Patch
*** Update File: src/bad_header.py
@@value = 1
-value = 1
+value = 2
*** End Patch
""",
            "patch hunk header is malformed",
        ),
        (
            """*** Begin Patch
*** Update File: src/bad_header.py
@@
@@ value = 1
-value = 1
+value = 2
*** End Patch
""",
            "patch hunk header is malformed",
        ),
        (
            """*** Begin Patch
*** Update File: src/bad_header.py
@@
-value = 1
+value = 2
*** End of File
+tail = 3
*** End Patch
""",
            "patch hunk body cannot follow end of file",
        ),
        (
            """*** Begin Patch
*** Update File: src/bad_header.py
@@ missing = 9
+value = 2
*** End Patch
""",
            "missing patch header anchor",
        ),
        (
            """*** Begin Patch
*** Update File: src/bad_header.py
@@ value = 1
-value = 1
+value = 2
*** End Patch
""",
            "missing patch context",
        ),
    ],
)
def test_apply_patch_rejects_alpha_invalid_headers_and_anchor_reuse(
    tmp_path: Path, patch_text: str, message: str
) -> None:
    repo = _repo(tmp_path)
    target = repo / "src" / "bad_header.py"
    target.parent.mkdir(parents=True)
    target.write_text("value = 1\n", encoding="utf-8", newline="\n")

    with pytest.raises(MutationPlanningError, match=message):
        build_mutation_plan(
            tool_name="apply_patch",
            payload=patch_text,
            owner="session-123",
            tool_use_id=None,
            repo_root=repo,
            base_dir=repo,
            resolve_target=_real_resolver,
        )
