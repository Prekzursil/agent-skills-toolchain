from backends import base
from backends.github_actions import GithubActionsVerifyBackend


class FakeGH:
    """Mixed matrix: ubuntu+macos green, windows red, plus a non-platform job."""

    def head_sha(self, repo, branch):
        return "deadbeef"

    def check_runs(self, repo, sha):
        assert sha == "deadbeef"  # correlation is by the branch's exact HEAD SHA
        return [
            {"name": "ci (ubuntu-latest)", "conclusion": "success"},
            {"name": "ci (windows-latest)", "conclusion": "failure"},
            {"name": "ci (macos-latest)", "conclusion": "success"},
            {"name": "lint", "conclusion": "success"},  # non-platform -> if m: FALSE
        ]


def test_is_a_verify_backend():
    assert isinstance(GithubActionsVerifyBackend(FakeGH()), base.VerifyBackend)


def test_verdict_maps_platforms_ignores_nonplatform_and_derives_all_green():
    v = GithubActionsVerifyBackend(FakeGH()).verify(
        "Prekzursil/env-inspector", "agent/E-x"
    )
    assert v.head_sha == "deadbeef"
    assert v.platforms == {
        "ubuntu-latest": True,
        "windows-latest": False,
        "macos-latest": True,
    }
    assert v.all_green is False  # windows red -> exactly the gap #145 caught


class EmptyGH:
    def head_sha(self, r, b):
        return "s"

    def check_runs(self, r, s):
        return []


def test_no_platform_runs_is_not_green():  # covers all_green empty-dict branch
    assert GithubActionsVerifyBackend(EmptyGH()).verify("o/r", "b").all_green is False


class GreenGH:
    """Full green matrix, plus a malformed run with no ``name`` key."""

    def head_sha(self, repo, branch):
        return "cafe1234"

    def check_runs(self, repo, sha):
        return [
            {"conclusion": "success"},  # no "name" -> .get("name", "") default arm
            {"name": "ci (ubuntu-latest)", "conclusion": "success"},
            {"name": "ci (windows-latest)", "conclusion": "success"},
            {"name": "ci (macos-latest)", "conclusion": "success"},
        ]


def test_full_green_matrix_echoes_repo_branch_and_tolerates_nameless_run():
    v = GithubActionsVerifyBackend(GreenGH()).verify("o/r", "agent/E-y")
    assert isinstance(v, base.MatrixVerdict)
    assert (v.repo, v.branch, v.head_sha) == ("o/r", "agent/E-y", "cafe1234")
    assert v.platforms == {
        "ubuntu-latest": True,
        "windows-latest": True,
        "macos-latest": True,
    }
    assert v.all_green is True  # the only all-green assertion in the file


class OrderedGH:
    """Two check-runs matching the SAME platform token, in a caller-chosen order."""

    def __init__(self, runs):
        self.runs = runs

    def head_sha(self, repo, branch):
        return "dup1234"

    def check_runs(self, repo, sha):
        return self.runs


_RED = {"name": "test (ubuntu-latest, 3.11)", "conclusion": "failure"}
_GREEN = {"name": "lint (ubuntu-latest)", "conclusion": "success"}
_GREEN2 = {"name": "test (ubuntu-latest, 3.12)", "conclusion": "success"}


def test_same_platform_legs_fold_any_red_wins_order_independently():
    red_last = GithubActionsVerifyBackend(OrderedGH([_GREEN, _RED])).verify("o/r", "b")
    red_first = GithubActionsVerifyBackend(OrderedGH([_RED, _GREEN])).verify("o/r", "b")
    # a red leg is never erased by a later green one -> not fail-OPEN on check_runs order
    assert red_last.platforms == {"ubuntu-latest": False}
    assert red_first.platforms == {"ubuntu-latest": False}
    assert (red_last.all_green, red_first.all_green) == (False, False)
    # ...and duplicates alone do NOT imply red: two green legs stay green
    both = GithubActionsVerifyBackend(OrderedGH([_GREEN, _GREEN2])).verify("o/r", "b")
    assert both.platforms == {"ubuntu-latest": True}
    assert both.all_green is True


_MIXED_PINNED = [
    {"name": "test (ubuntu-latest)", "conclusion": "success"},
    {"name": "test (windows-2022)", "conclusion": "failure"},  # PINNED runner, RED
]


def test_pinned_runner_red_leg_is_counted_not_dropped():
    v = GithubActionsVerifyBackend(OrderedGH(_MIXED_PINNED)).verify("o/r", "b")
    # was FAIL-OPEN: the unmatched red leg vanished and all_green read True
    assert v.platforms == {"ubuntu-latest": True, "windows-2022": False}
    assert v.all_green is False


_ALL_PINNED_GREEN = [
    {"name": "test (ubuntu-24.04)", "conclusion": "success"},
    {"name": "test (windows-2022)", "conclusion": "success"},
    {"name": "test (macos-14)", "conclusion": "success"},
]


def test_all_pinned_green_matrix_is_visible_and_green():
    v = GithubActionsVerifyBackend(OrderedGH(_ALL_PINNED_GREEN)).verify("o/r", "b")
    assert v.platforms == {"ubuntu-24.04": True, "windows-2022": True, "macos-14": True}
    assert v.all_green is True  # pinned runners are no longer invisible


_NON_PLATFORM = [
    {"name": "lint", "conclusion": "failure"},  # non-platform job, RED
    {"conclusion": "failure"},  # nameless run, RED
    {"name": "deploy (windows-)", "conclusion": "failure"},  # empty tail -> no match
    {"name": "test (macos-14)", "conclusion": "success"},
]


def test_non_platform_nameless_and_empty_tail_names_stay_ignored():
    v = GithubActionsVerifyBackend(OrderedGH(_NON_PLATFORM)).verify("o/r", "b")
    # widening the pattern must not start counting non-platform jobs
    assert v.platforms == {"macos-14": True}
    assert v.all_green is True  # all_green is the PLATFORM matrix, not all of CI
