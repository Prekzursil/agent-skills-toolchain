"""
Tests for repo_map.py — the PageRank-over-symbol-references grounding-pack builder.

Standard library only (plus two OPTIONAL cross-check tests that skip when the
library is absent):

  * ``networkx`` — an independent PageRank implementation. When installed the
    suite asserts our pure-stdlib power iteration agrees with it to 1e-9.
    SKIPPED in CI (networkx is not a CI dependency), so CI green is NOT
    evidence for that agreement — see README "Measured, and where".
  * ``tiktoken`` — a real BPE tokenizer. When installed the suite asserts the
    ``len//4`` estimator does not UNDERCOUNT the true token count on the
    rendered digest (undercounting is the only direction that can blow a
    budget). Also SKIPPED in CI.

Fixture layout (created in a temp dir per test):

    core.py    defines central_helper (referenced by a,b,c,d)
                       rarely_used_helper (referenced by a only)
    a.py b.py c.py d.py   referencers
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

# ---------------------------------------------------------------------------
# Import repo_map from its sibling location regardless of PYTHONPATH.
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).parent
_MODULE_PATH = _THIS_DIR / "repo_map.py"

_spec = importlib.util.spec_from_file_location("repo_map", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
repo_map = importlib.util.module_from_spec(_spec)
# MUST be registered before exec_module: @dataclass resolves string annotations
# via sys.modules[cls.__module__], which is None for an unregistered module.
sys.modules["repo_map"] = repo_map
_spec.loader.exec_module(repo_map)

try:  # pragma: no cover -- optional cross-check dependency
    import networkx as nx

    HAS_NETWORKX = True
except ImportError:  # pragma: no cover -- optional cross-check dependency
    HAS_NETWORKX = False

try:  # pragma: no cover -- optional cross-check dependency
    import tiktoken

    HAS_TIKTOKEN = True
except ImportError:  # pragma: no cover -- optional cross-check dependency
    HAS_TIKTOKEN = False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body).lstrip("\n"), encoding="utf-8")


def make_fixture_tree(root: Path) -> None:
    """A tiny tree with one clearly-central symbol and one clear near-leaf."""
    _write(
        root,
        "core.py",
        """
        def central_helper(value):
            return value + 1


        def rarely_used_helper(value):
            return value - 1


        def _private_detail(value):
            return value
        """,
    )
    _write(
        root,
        "a.py",
        """
        from core import central_helper, rarely_used_helper


        def run_a():
            return central_helper(1) + rarely_used_helper(1)
        """,
    )
    for name, arg in (("b", 2), ("c", 3), ("d", 4)):
        _write(
            root,
            f"{name}.py",
            f"""
            from core import central_helper


            def run_{name}():
                return central_helper({arg})
            """,
        )


class FixtureTreeCase(unittest.TestCase):
    """Base class that materialises the fixture tree in a fresh temp dir."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        make_fixture_tree(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


class TestDiscovery(FixtureTreeCase):
    def test_discovers_all_python_files_sorted_and_slashed(self):
        files = repo_map.discover_files(self.root)
        self.assertEqual(files, ["a.py", "b.py", "c.py", "core.py", "d.py"])

    def test_discovery_is_deterministic(self):
        self.assertEqual(
            repo_map.discover_files(self.root), repo_map.discover_files(self.root)
        )

    def test_nested_paths_use_forward_slashes(self):
        _write(self.root, "pkg/sub/mod.py", "def nested_symbol():\n    return 1\n")
        files = repo_map.discover_files(self.root)
        self.assertIn("pkg/sub/mod.py", files)
        self.assertFalse(any("\\" in f for f in files))

    def test_excluded_directories_are_skipped(self):
        _write(self.root, "node_modules/pkg/index.js", "function junkSymbol() {}\n")
        _write(self.root, ".venv/lib/thing.py", "def junk_symbol():\n    return 1\n")
        files = repo_map.discover_files(self.root)
        self.assertNotIn("node_modules/pkg/index.js", files)
        self.assertNotIn(".venv/lib/thing.py", files)

    def test_unknown_extensions_are_skipped(self):
        _write(self.root, "notes.txt", "def not_code():\n    pass\n")
        self.assertNotIn("notes.txt", repo_map.discover_files(self.root))

    def test_undecodable_file_is_skipped_not_fatal(self):
        (self.root / "blob.py").write_bytes(b"\xff\xfe\x00\x01def broken(:\n")
        files = repo_map.discover_files(self.root)
        # Discovery lists it; reading must degrade to "no tags", never raise.
        self.assertIn("blob.py", files)
        result = repo_map.build_repo_map(self.root, budget_tokens=512)
        self.assertTrue(all(d.file != "blob.py" for d in result.definitions))


# ---------------------------------------------------------------------------
# Symbol extraction
# ---------------------------------------------------------------------------


class TestExtraction(unittest.TestCase):
    def test_python_defs_and_classes_with_line_numbers(self):
        src = "class Widget:\n    def render(self):\n        return 1\n\n\ndef top_level():\n    return 2\n"
        tags = repo_map.extract_tags("m.py", src)
        self.assertEqual(tags.definitions["Widget"], [1])
        self.assertEqual(tags.definitions["render"], [2])
        self.assertEqual(tags.definitions["top_level"], [6])

    def test_python_module_level_constant_is_a_definition(self):
        src = "MAX_DEPTH = 4\n\n\ndef go():\n    x = 1\n    return x\n"
        tags = repo_map.extract_tags("m.py", src)
        self.assertIn("MAX_DEPTH", tags.definitions)
        # An indented assignment is a local, not a module symbol.
        self.assertNotIn("x", tags.definitions)

    def test_javascript_function_and_class_and_const(self):
        src = "export function loadConfig() {}\nclass ConfigStore {}\nconst DEFAULT_PORT = 8812;\n"
        tags = repo_map.extract_tags("m.js", src)
        self.assertIn("loadConfig", tags.definitions)
        self.assertIn("ConfigStore", tags.definitions)
        self.assertIn("DEFAULT_PORT", tags.definitions)

    def test_indented_javascript_binding_is_a_local_not_a_definition(self):
        # Measured on the real tree: allowing leading whitespace here made every
        # `const timeoutMs = ...` inside a function a module symbol, and those
        # locals took the top of the ranking.
        src = "function run() {\n    const timeoutMs = 5;\n    return timeoutMs;\n}\n"
        tags = repo_map.extract_tags("m.js", src)
        self.assertIn("run", tags.definitions)
        self.assertNotIn("timeoutMs", tags.definitions)

    def test_shell_and_powershell_functions(self):
        sh = repo_map.extract_tags("s.sh", "deploy_thing() {\n  echo hi\n}\n")
        self.assertIn("deploy_thing", sh.definitions)
        ps = repo_map.extract_tags("s.ps1", "function Invoke-Thing {\n}\n")
        self.assertIn("Invoke-Thing", ps.definitions)

    def test_references_exclude_own_definition_occurrence(self):
        # `helper` is defined once and never used again -> zero references.
        tags = repo_map.extract_tags("m.py", "def helper():\n    return 1\n")
        self.assertEqual(tags.references.get("helper", 0), 0)

    def test_references_counted_for_uses(self):
        src = "def helper():\n    return 1\n\n\ndef caller():\n    return helper() + helper()\n"
        tags = repo_map.extract_tags("m.py", src)
        self.assertEqual(tags.references["helper"], 2)

    def test_attribute_access_is_recorded_as_a_reference_subset(self):
        src = "def go(thing):\n    return thing.render_widget()\n"
        tags = repo_map.extract_tags("m.py", src)
        self.assertEqual(tags.references["render_widget"], 1)
        self.assertEqual(tags.attribute_references["render_widget"], 1)

    def test_bare_call_is_not_attribute_access(self):
        tags = repo_map.extract_tags("m.py", "def go():\n    return render_widget()\n")
        self.assertEqual(tags.references["render_widget"], 1)
        self.assertEqual(tags.attribute_references.get("render_widget", 0), 0)

    def test_comment_only_mention_is_not_a_reference(self):
        tags = repo_map.extract_tags(
            "m.py", "# helper_symbol is deprecated\nVALUE = 1\n"
        )
        self.assertEqual(tags.references.get("helper_symbol", 0), 0)

    def test_language_keywords_are_not_references(self):
        tags = repo_map.extract_tags("m.py", "def go():\n    return None\n")
        for kw in ("def", "return", "None"):
            self.assertEqual(tags.references.get(kw, 0), 0)


# ---------------------------------------------------------------------------
# PageRank
# ---------------------------------------------------------------------------


class TestPageRank(unittest.TestCase):
    def test_ranks_sum_to_one(self):
        nodes = ["a", "b", "c"]
        edges = {"a": [("b", 1.0)], "b": [("c", 1.0)], "c": []}
        ranks = repo_map.pagerank(nodes, edges)
        self.assertAlmostEqual(sum(ranks.values()), 1.0, places=9)

    def test_empty_graph_returns_empty(self):
        self.assertEqual(repo_map.pagerank([], {}), {})

    def test_hub_outranks_spokes(self):
        nodes = ["hub", "s1", "s2", "s3"]
        edges = {
            "hub": [],
            "s1": [("hub", 1.0)],
            "s2": [("hub", 1.0)],
            "s3": [("hub", 1.0)],
        }
        ranks = repo_map.pagerank(nodes, edges)
        self.assertGreater(ranks["hub"], ranks["s1"])

    def test_personalization_shifts_mass(self):
        nodes = ["a", "b"]
        edges = {"a": [], "b": []}
        flat = repo_map.pagerank(nodes, edges)
        tilted = repo_map.pagerank(nodes, edges, personalization={"a": 1.0})
        self.assertAlmostEqual(flat["a"], flat["b"], places=9)
        self.assertGreater(tilted["a"], flat["a"])

    def test_node_order_does_not_change_ranks(self):
        edges = {"a": [("b", 1.0)], "b": [("c", 2.0)], "c": [("a", 1.0)]}
        forward = repo_map.pagerank(["a", "b", "c"], edges)
        reverse = repo_map.pagerank(["c", "b", "a"], edges)
        for key in forward:
            self.assertAlmostEqual(forward[key], reverse[key], places=12)

    @unittest.skipUnless(HAS_NETWORKX, "networkx not installed (skipped in CI)")
    def test_matches_networkx_reference_implementation(self):
        edges = {
            "a": [("b", 1.0), ("c", 3.0)],
            "b": [("c", 2.0)],
            "c": [("a", 1.0)],
            "d": [],
        }
        nodes = ["a", "b", "c", "d"]
        mine = repo_map.pagerank(nodes, edges)
        graph = nx.DiGraph()
        graph.add_nodes_from(nodes)
        for src, outs in edges.items():
            for dst, weight in outs:
                graph.add_edge(src, dst, weight=weight)
        theirs = nx.pagerank(graph, alpha=repo_map.DAMPING, weight="weight", tol=1e-12)
        for key in nodes:
            self.assertAlmostEqual(mine[key], theirs[key], places=9)


# ---------------------------------------------------------------------------
# Ranking end-to-end
# ---------------------------------------------------------------------------


class TestRanking(FixtureTreeCase):
    def test_central_symbol_outranks_near_leaf(self):
        result = repo_map.build_repo_map(self.root, budget_tokens=4096)
        ranks = {(d.file, d.name): d.rank for d in result.definitions}
        self.assertIn(("core.py", "central_helper"), ranks)
        self.assertIn(("core.py", "rarely_used_helper"), ranks)
        self.assertGreater(
            ranks[("core.py", "central_helper")],
            ranks[("core.py", "rarely_used_helper")],
        )

    def test_central_symbol_survives_a_tight_budget_and_leaf_does_not(self):
        # Self-calibrating: squeeze the budget to exactly what ONE definition
        # costs, then assert the one that survives is the central one. Pinning a
        # literal token number here would silently stop testing anything the
        # moment CHARS_PER_TOKEN or the render format changed.
        full = repo_map.build_repo_map(self.root, budget_tokens=4096)
        self.assertGreaterEqual(len(full.definitions), 2)
        budget = repo_map.estimate_tokens(repo_map.render(full.definitions[:1]))
        tight = repo_map.build_repo_map(self.root, budget_tokens=budget)
        self.assertEqual([d.name for d in tight.included], ["central_helper"])

    def test_focus_raises_the_focused_files_dependencies(self):
        base = repo_map.build_repo_map(self.root, budget_tokens=4096)
        focused = repo_map.build_repo_map(self.root, budget_tokens=4096, focus=["a.py"])

        def ratio(result):
            ranks = {d.name: d.rank for d in result.definitions}
            return ranks["rarely_used_helper"] / ranks["central_helper"]

        self.assertGreater(ratio(focused), ratio(base))

    def test_ranking_is_independent_of_dict_insertion_order(self):
        files = repo_map.discover_files(self.root)
        forward = {
            f: repo_map.extract_tags(f, (self.root / f).read_text(encoding="utf-8"))
            for f in files
        }
        backward = {
            f: repo_map.extract_tags(f, (self.root / f).read_text(encoding="utf-8"))
            for f in reversed(files)
        }
        self.assertEqual(
            [(d.file, d.name) for d in repo_map.rank_definitions(forward)],
            [(d.file, d.name) for d in repo_map.rank_definitions(backward)],
        )


# ---------------------------------------------------------------------------
# Import evidence + graph shaping
#
# Every case below locks in a behaviour that was CHANGED after measuring the
# ranking this tool produced on the real 1,386-file agent-skills-toolchain tree
# (see README "What measurement changed"). Without these, a later edit could
# quietly restore the noise.
# ---------------------------------------------------------------------------


def _tags(
    path: str,
    *,
    defines: Sequence[str] = (),
    references: Mapping[str, int] | None = None,
    attribute_references: Mapping[str, int] | None = None,
    imported_names: Sequence[str] = (),
    imported_modules: Sequence[str] = (),
) -> "repo_map.FileTags":
    return repo_map.FileTags(
        path=path,
        definitions={name: [1] for name in defines},
        references=Counter(references or {}),
        attribute_references=Counter(attribute_references or {}),
        signatures={1: "signature"},
        imported_names=set(imported_names),
        imported_modules=set(imported_modules),
    )


class TestImportEvidence(unittest.TestCase):
    def test_python_from_import_records_module_and_names(self):
        tags = repo_map.extract_tags("m.py", "from core.adapters import load_thing\n")
        self.assertIn("load_thing", tags.imported_names)
        self.assertIn("adapters", tags.imported_modules)
        self.assertIn("core", tags.imported_modules)

    def test_python_plain_import_records_module_components(self):
        tags = repo_map.extract_tags("m.py", "import json, core.registry\n")
        self.assertIn("json", tags.imported_modules)
        self.assertIn("registry", tags.imported_modules)
        self.assertEqual(tags.imported_names, set())

    def test_javascript_named_import_records_names_and_spec(self):
        tags = repo_map.extract_tags(
            "m.js", "import { loadConfig } from './config.js';\n"
        )
        self.assertIn("loadConfig", tags.imported_names)
        self.assertIn("config", tags.imported_modules)

    def test_javascript_require_binding_is_an_import_not_a_definition(self):
        tags = repo_map.extract_tags(
            "m.js", 'const layoutBuilders = require("./layout_builders");\n'
        )
        self.assertNotIn("layoutBuilders", tags.definitions)
        self.assertIn("layoutBuilders", tags.imported_names)
        self.assertIn("layout_builders", tags.imported_modules)

    def test_module_aliases_uses_stem_and_package_dir(self):
        self.assertEqual(repo_map.module_aliases("pkg/core.py"), {"core"})
        self.assertEqual(
            repo_map.module_aliases("pkg/__init__.py"), {"__init__", "pkg"}
        )

    def test_file_without_imports_has_no_import_evidence(self):
        self.assertFalse(
            repo_map.extract_tags("m.py", "VALUE = 1\n").has_import_evidence
        )


class TestGraphShaping(unittest.TestCase):
    def test_self_edges_are_excluded(self):
        tags = {
            "solo.py": _tags(
                "solo.py", defines=["local_helper"], references={"local_helper": 5}
            )
        }
        _nodes, edges = repo_map.build_graph(tags)
        self.assertEqual(edges, [])

    def test_short_identifiers_are_excluded(self):
        tags = {
            "core.py": _tags("core.py", defines=["ab"]),
            "user.py": _tags("user.py", references={"ab": 4}),
        }
        _nodes, edges = repo_map.build_graph(tags)
        self.assertEqual(edges, [])

    @staticmethod
    def _ubiquity_fixture(definer_count: int) -> dict[str, "repo_map.FileTags"]:
        tags = {
            f"m{i}.py": _tags(f"m{i}.py", defines=["ubiquitous_name"])
            for i in range(definer_count)
        }
        tags["user.py"] = _tags("user.py", references={"ubiquitous_name": 3})
        return tags

    def test_identifier_defined_in_eleven_files_is_dropped(self):
        # LITERAL 11, not MAX_DEFINER_FILES + 1: a threshold expressed in terms
        # of the constant under test moves with it and can never detect a change
        # to its value. (Measured: the relative form survived mutation.)
        _nodes, edges = repo_map.build_graph(self._ubiquity_fixture(11))
        self.assertEqual(edges, [])

    def test_identifier_defined_in_four_files_is_kept(self):
        _nodes, edges = repo_map.build_graph(self._ubiquity_fixture(4))
        self.assertEqual(len(edges), 4)

    def test_explicitly_mentioned_identifier_survives_the_ubiquity_cap(self):
        _nodes, edges = repo_map.build_graph(
            self._ubiquity_fixture(11), mentioned=["ubiquitous_name"]
        )
        self.assertTrue(edges)

    def test_build_graph_returns_nodes_in_sorted_order(self):
        tags = {
            "zeta.py": _tags("zeta.py", defines=["shared_helper"]),
            "alpha.py": _tags("alpha.py", references={"shared_helper": 1}),
        }
        nodes, _edges = repo_map.build_graph(tags)
        self.assertEqual(nodes, ["alpha.py", "zeta.py"])

    def test_equal_ranks_break_ties_by_file_then_name(self):
        # Both identifiers are the same length, same shape and equally
        # referenced, so their ranks are bitwise identical. The ORDER must then
        # come from the (file, name) tiebreak, not from accumulation order —
        # which here is the reverse, so a rank-only sort produces zeta first.
        tags = {
            "alpha.py": _tags("alpha.py", defines=["bbb_symbol_name"]),
            "zeta.py": _tags("zeta.py", defines=["aaa_symbol_name"]),
            "user.py": _tags(
                "user.py",
                references={"bbb_symbol_name": 4, "aaa_symbol_name": 4},
            ),
        }
        definitions = repo_map.rank_definitions(tags)
        self.assertEqual([d.rank for d in definitions][0], definitions[1].rank)
        self.assertEqual([d.file for d in definitions], ["alpha.py", "zeta.py"])

    def test_import_backed_edge_outweighs_a_bare_name_match(self):
        tags = {
            "core.py": _tags("core.py", defines=["shared_helper"]),
            "importer.py": _tags(
                "importer.py",
                references={"shared_helper": 1},
                imported_names=["shared_helper"],
                imported_modules=["core"],
            ),
            "stranger.py": _tags(
                "stranger.py",
                references={"shared_helper": 1},
                imported_modules=["os"],
            ),
        }
        _nodes, edges = repo_map.build_graph(tags)
        weights = {edge.source: edge.weight for edge in edges}
        self.assertGreater(weights["importer.py"], weights["stranger.py"])
        self.assertAlmostEqual(
            weights["stranger.py"],
            weights["importer.py"] * repo_map.WEAK_EDGE_FACTOR,
            places=12,
        )

    def test_attribute_dominated_use_does_not_qualify_via_a_module_import(self):
        # `import widgets` says nothing about whether `thing.render_widget()`
        # is widgets' symbol. Measured: without this, one-word `@property`
        # accessors (`name`, `key`, `text`) took the top of the real ranking.
        tags = {
            "widgets.py": _tags("widgets.py", defines=["render_widget"]),
            "attr_user.py": _tags(
                "attr_user.py",
                references={"render_widget": 4},
                attribute_references={"render_widget": 4},
                imported_modules=["widgets"],
            ),
            "call_user.py": _tags(
                "call_user.py",
                references={"render_widget": 4},
                imported_modules=["widgets"],
            ),
        }
        _nodes, edges = repo_map.build_graph(tags)
        weights = {edge.source: edge.weight for edge in edges}
        self.assertAlmostEqual(
            weights["attr_user.py"],
            weights["call_user.py"] * repo_map.WEAK_EDGE_FACTOR,
            places=12,
        )

    def test_explicit_by_name_import_beats_attribute_dominance(self):
        tags = {
            "widgets.py": _tags("widgets.py", defines=["render_widget"]),
            "attr_user.py": _tags(
                "attr_user.py",
                references={"render_widget": 4},
                attribute_references={"render_widget": 4},
                imported_names=["render_widget"],
            ),
        }
        _nodes, edges = repo_map.build_graph(tags)
        self.assertAlmostEqual(edges[0].weight, 10.0 * 2.0, places=12)

    def test_file_with_no_import_evidence_is_not_penalised(self):
        # A shell/PowerShell file has no import extraction at all; absence of a
        # strong signal there is a gap in the TOOL, not evidence against the edge.
        tags = {
            "core.py": _tags("core.py", defines=["shared_helper"]),
            "importer.py": _tags(
                "importer.py",
                references={"shared_helper": 1},
                imported_names=["shared_helper"],
            ),
            "silent.py": _tags("silent.py", references={"shared_helper": 1}),
        }
        _nodes, edges = repo_map.build_graph(tags)
        weights = {edge.source: edge.weight for edge in edges}
        self.assertAlmostEqual(weights["silent.py"], weights["importer.py"], places=12)


class TestIdentMultiplier(unittest.TestCase):
    def test_underscore_prefixed_is_downweighted(self):
        self.assertLess(
            repo_map.ident_multiplier("_shared_helper", 1, frozenset()),
            repo_map.ident_multiplier("shared_helper", 1, frozenset()),
        )

    def test_long_snake_case_is_upweighted_over_a_short_name(self):
        self.assertGreater(
            repo_map.ident_multiplier("load_registry", 1, frozenset()),
            repo_map.ident_multiplier("load", 1, frozenset()),
        )

    def test_mentioned_is_upweighted(self):
        self.assertGreater(
            repo_map.ident_multiplier("load", 1, frozenset({"load"})),
            repo_map.ident_multiplier("load", 1, frozenset()),
        )

    def test_widely_defined_is_downweighted(self):
        self.assertLess(
            repo_map.ident_multiplier("shared_helper", 9, frozenset()),
            repo_map.ident_multiplier("shared_helper", 2, frozenset()),
        )


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


class TestBudget(FixtureTreeCase):
    def test_budget_is_never_exceeded(self):
        for budget in (0, 1, 5, 12, 24, 60, 200, 4096):
            with self.subTest(budget=budget):
                result = repo_map.build_repo_map(self.root, budget_tokens=budget)
                self.assertLessEqual(repo_map.estimate_tokens(result.digest), budget)

    def test_zero_budget_yields_empty_digest(self):
        self.assertEqual(repo_map.build_repo_map(self.root, budget_tokens=0).digest, "")

    def test_budget_is_weakly_monotonic(self):
        counts = [
            len(repo_map.build_repo_map(self.root, budget_tokens=b).included)
            for b in (0, 10, 25, 60, 150, 4096)
        ]
        self.assertEqual(counts, sorted(counts))

    def test_binary_search_finds_the_largest_fitting_prefix(self):
        budget = 40
        result = repo_map.build_repo_map(self.root, budget_tokens=budget)
        n = len(result.included)
        self.assertLessEqual(repo_map.estimate_tokens(result.digest), budget)
        if n < len(result.definitions):
            one_more = repo_map.render(result.definitions[: n + 1])
            self.assertGreater(repo_map.estimate_tokens(one_more), budget)

    def test_estimate_tokens_is_monotonic_in_length(self):
        self.assertEqual(repo_map.estimate_tokens(""), 0)
        self.assertLessEqual(
            repo_map.estimate_tokens("abc"), repo_map.estimate_tokens("abcdefgh")
        )

    def test_chars_per_token_divisor_stays_conservative(self):
        # Regression guard for a MEASURED defect: the folklore divisor of 4
        # under-counted every sampled digest (3.03-3.57 real chars/token on this
        # repository), so a budget computed with it silently overran. Raising
        # this back above 3 must fail the suite, not ship quietly.
        self.assertLessEqual(repo_map.CHARS_PER_TOKEN, 3)

    def test_custom_token_counter_is_honoured(self):
        # A deliberately pessimistic counter must shrink the digest.
        default = repo_map.build_repo_map(self.root, budget_tokens=200)
        pessimistic = repo_map.build_repo_map(
            self.root, budget_tokens=200, token_counter=lambda text: len(text)
        )
        self.assertLessEqual(len(pessimistic.included), len(default.included))
        self.assertLessEqual(len(pessimistic.digest), 200)

    @unittest.skipUnless(HAS_TIKTOKEN, "tiktoken not installed (skipped in CI)")
    def test_estimator_does_not_undercount_a_real_tokenizer(self):
        digest = repo_map.build_repo_map(self.root, budget_tokens=4096).digest
        self.assertTrue(digest)
        real = len(tiktoken.get_encoding("cl100k_base").encode(digest))
        self.assertGreaterEqual(repo_map.estimate_tokens(digest), real)


# ---------------------------------------------------------------------------
# Determinism + rendering
# ---------------------------------------------------------------------------


class TestDeterminismAndRendering(FixtureTreeCase):
    def test_two_runs_are_byte_identical(self):
        first = repo_map.build_repo_map(self.root, budget_tokens=300).digest
        second = repo_map.build_repo_map(self.root, budget_tokens=300).digest
        self.assertEqual(first, second)

    def test_digest_carries_path_and_line_anchors(self):
        digest = repo_map.build_repo_map(self.root, budget_tokens=300).digest
        self.assertIn("core.py", digest)
        self.assertRegex(digest, r"\n\s*\d+: ")

    def test_digest_uses_lf_endings_only(self):
        self.assertNotIn(
            "\r", repo_map.build_repo_map(self.root, budget_tokens=300).digest
        )

    def test_empty_tree_is_not_fatal(self):
        with tempfile.TemporaryDirectory() as empty:
            result = repo_map.build_repo_map(Path(empty), budget_tokens=200)
            self.assertEqual(result.digest, "")
            self.assertEqual(result.definitions, [])


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli(FixtureTreeCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(_MODULE_PATH), "--root", str(self.root), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_cli_emits_a_digest(self):
        proc = self._run("--budget", "300")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("core.py", proc.stdout)

    def test_cli_json_is_valid_and_carries_ranks(self):
        proc = self._run("--budget", "300", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertIn("digest", payload)
        self.assertIn("definitions", payload)
        self.assertGreater(len(payload["definitions"]), 0)
        self.assertIn("rank", payload["definitions"][0])

    def test_cli_writes_out_file(self):
        out = self.root / "map.md"
        proc = self._run("--budget", "300", "--out", str(out))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("core.py", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
