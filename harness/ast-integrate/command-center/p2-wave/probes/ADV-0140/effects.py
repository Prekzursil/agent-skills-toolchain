"""Effect-based owner-action classification.

Sinks are identified by EFFECT (mutating HTTP to a publish host, spend-incurring
API, destructive user-data filesystem, permission-widening write, public
repo/org create) never by function name. A rename of the callee must not drop
the sink. Gate nodes may be named: they are the checkpoint, not the action.
"""
from __future__ import annotations

import ast
import re
from typing import Iterable
from urllib.parse import urlparse

ACTION_CLASSES = (
    "public_publishing",
    "unbounded_or_paid_external_spend",
    "deleting_user_data",
    "changing_security_posture",
    "creating_public_repositories_or_organizations",
)

PUBLISH_HOSTS = frozenset(
    {
        "pypi.org",
        "upload.pypi.org",
        "test.pypi.org",
        "upload.pypi.io",
        "registry.npmjs.org",
        "registry.yarnpkg.com",
        "npm.pkg.github.com",
        "rubygems.org",
        "crates.io",
        "marketplace.visualstudio.com",
    }
)
PUBLISH_PATH_MARKERS = ("/legacy/", "/simple/", "/api/v1/wheels")
PUBLISH_ARGV = frozenset({"twine", "npm", "pnpm", "yarn", "poetry", "vsce", "cargo", "flit"})
PUBLISH_SUB = frozenset({"publish", "upload", "release"})

SPEND_HOSTS = frozenset(
    {
        "api.openai.com",
        "api.anthropic.com",
        "api.stripe.com",
        "generativelanguage.googleapis.com",
        "api.cohere.ai",
        "api.groq.com",
        "api.mistral.ai",
        "api.together.xyz",
        "api.fireworks.ai",
    }
)

GITHUB_HOSTS = frozenset({"api.github.com", "github.com"})
REPO_PATH_MARKERS = ("/user/repos", "/orgs/", "/organizations")
REPO_ARGV = (("gh", "repo", "create"), ("gh", "org", "create"), ("hub", "create"))

MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})
DESTRUCTIVE_LEAVES = frozenset(
    {"rmtree", "unlink", "remove", "removedirs", "rmdir", "replace"}
)
USER_DATA_MARKERS = (
    "user-data",
    "user_data",
    "user-owned",
    "purge-user",
    "purge_user",
    "--purge-user-data",
    "USERPROFILE",
    "HOME",
    "home_dir",
    "userdata",
)
POSTURE_FILES = (
    "net-allowlist.json",
    "net_allowlist",
    "permissions.json",
    "allowlist",
    "hooks.json",
    "consent",
)
GATE_LEAVES = frozenset(
    {
        "human_checkpoint",
        "HumanCheckpoint",
        "require_owner_approval",
        "owner_approval_required",
        "gated_request",
        "gated_request",
        "try_egress",
        "refuse_lifecycle",
        "refuse_lifecycle_operation",
        "pause_for_owner",
        "emit_checkpoint_and_exit",
        "parse_consent",
        "load_consent",
    }
)

URL_RE = re.compile(r"https?://[^\s\"']+", re.I)


def _qual(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _qual(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def _const_str(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _host(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower().split("@")[-1].split(":")[0]
    except Exception:
        return ""


def _path(url: str) -> str:
    try:
        return (urlparse(url).path or "").lower()
    except Exception:
        return ""


def strings_in(node: ast.AST) -> list[str]:
    out: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            out.append(child.value)
    return out


def argv_tokens(call: ast.Call) -> list[str]:
    tokens: list[str] = []
    if not call.args:
        return tokens
    arg0 = call.args[0]
    if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
        tokens.extend(arg0.value.split())
        return tokens
    if isinstance(arg0, (ast.List, ast.Tuple)):
        for elt in arg0.elts:
            s = _const_str(elt)
            if s:
                tokens.append(s)
    return tokens


class FunctionBag:
    def __init__(self, name: str, lineno: int, rel: str) -> None:
        self.name = name
        self.lineno = lineno
        self.rel = rel
        self.urls: list[str] = []
        self.methods: set[str] = set()
        self.argv: list[str] = []
        self.leaves: set[str] = set()
        self.calls: set[str] = set()
        self.has_data_kw: bool = False
        self.writes_posture: bool = False
        self.owner_gated_false: bool = False
        self.gate_hits: set[str] = set()
        self.destructive: bool = False
        self.user_data_text: bool = False
        self.public_flag: bool = False

    def effects(self) -> set[str]:
        found: set[str] = set()
        hosts = [_host(u) for u in self.urls]
        paths = [_path(u) for u in self.urls]
        mutating = bool(self.methods & MUTATING) or self.has_data_kw
        if mutating:
            for h, p in zip(hosts, paths):
                if h in PUBLISH_HOSTS or any(m in p for m in PUBLISH_PATH_MARKERS):
                    found.add("public_publishing")
                if h in SPEND_HOSTS:
                    found.add("unbounded_or_paid_external_spend")
                if h in GITHUB_HOSTS and any(m in p for m in REPO_PATH_MARKERS):
                    found.add("creating_public_repositories_or_organizations")
        argv_l = [t.lower() for t in self.argv]
        if argv_l:
            head = argv_l[0].split("/")[-1]
            if head in PUBLISH_ARGV and any(s in argv_l for s in PUBLISH_SUB):
                found.add("public_publishing")
            joined = " ".join(argv_l)
            if "gh repo create" in joined or "gh org create" in joined:
                found.add("creating_public_repositories_or_organizations")
            if "--public" in argv_l or "visibility=public" in joined:
                self.public_flag = True
        for seq in REPO_ARGV:
            if all(p in argv_l for p in seq):
                found.add("creating_public_repositories_or_organizations")
        if self.destructive and self.user_data_text:
            found.add("deleting_user_data")
        if self.writes_posture or self.owner_gated_false:
            found.add("changing_security_posture")
        if "gated_request" in self.calls or "gated_request" in self.calls or "try_egress" in self.calls:
            found.add("changing_security_posture")
        if self.public_flag and (
            any(h in GITHUB_HOSTS for h in hosts)
            or any(t.lower() in {"gh", "hub"} for t in self.argv)
        ):
            found.add("creating_public_repositories_or_organizations")
        return found

    def gated(self) -> bool:
        return bool(self.gate_hits)

    def as_row(self) -> dict:
        return {
            "symbol": self.name,
            "file": self.rel,
            "line": self.lineno,
            "effects": sorted(self.effects()),
            "gated": self.gated(),
            "gates": sorted(self.gate_hits),
            "identification": "effect (hosts/methods/argv/fs), not function name",
            "urls": sorted(set(self.urls)),
            "methods": sorted(self.methods),
        }


FunctionBag.as_row = FunctionBag.as_row


def _looks_user_data(texts: Iterable[str]) -> bool:
    blob = " ".join(texts).lower()
    return any(m.lower() in blob for m in USER_DATA_MARKERS)


def _looks_posture_write(texts: Iterable[str]) -> bool:
    blob = " ".join(texts).lower()
    return any(m.lower() in blob for m in POSTURE_FILES)


def module_string_constants(tree: ast.AST) -> dict[str, str]:
    env: dict[str, str] = {}
    body = getattr(tree, "body", [])
    for node in body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            s = _const_str(node.value)
            if isinstance(target, ast.Name) and s:
                env[target.id] = s
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            s = _const_str(node.value)
            if s:
                env[node.target.id] = s
    return env


def classify_function(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
    rel: str,
    const_env: dict[str, str] | None = None,
) -> FunctionBag:
    env = dict(const_env or {})
    for arg, default in zip(
        reversed(list(fn.args.args)), reversed(list(fn.args.defaults or []))
    ):
        s = _const_str(default)
        if s:
            env[arg.arg] = s
    bag = FunctionBag(fn.name, getattr(fn, "lineno", 0), rel)
    texts = strings_in(fn)
    bag.user_data_text = _looks_user_data(texts)
    for s in texts:
        if s.lower().startswith("http://") or s.lower().startswith("https://"):
            bag.urls.append(s)
        for m in URL_RE.findall(s):
            if m not in bag.urls:
                bag.urls.append(m)
        up = s.upper()
        if up in MUTATING or up == "GET":
            bag.methods.add(up)
        if s in {"--public", "public"}:
            bag.public_flag = True

    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            qual = _qual(node.func)
            leaf = qual.split(".")[-1] if qual else ""
            bag.leaves.add(leaf)
            bag.calls.add(leaf)
            if leaf in GATE_LEAVES or qual in GATE_LEAVES:
                bag.gate_hits.add(leaf or qual)
            if leaf in DESTRUCTIVE_LEAVES:
                bag.destructive = True
            if leaf in {"run", "Popen", "call", "check_output", "check_call", "system"}:
                bag.argv.extend(argv_tokens(node))
            if leaf in {"Request", "urlopen", "urlretrieve"}:
                for kw in node.keywords:
                    if kw.arg == "method":
                        m = _const_str(kw.value)
                        if m:
                            bag.methods.add(m.upper())
                    if kw.arg in {"data", "json", "body", "content"}:
                        bag.has_data_kw = True
                for arg in node.args:
                    s = _const_str(arg)
                    if s is None and isinstance(arg, ast.Name):
                        s = env.get(arg.id)
                    if s and (s.startswith("http://") or s.startswith("https://")):
                        bag.urls.append(s)
            if leaf in {"open", "write_text", "write_bytes", "dump"}:
                call_text = strings_in(node)
                for arg in node.args:
                    if isinstance(arg, ast.Name) and arg.id in env:
                        call_text.append(env[arg.id])
                    s = _const_str(arg)
                    if s:
                        call_text.append(s)
                if _looks_posture_write(call_text):
                    bag.writes_posture = True
        if isinstance(node, ast.Compare):
            left = _qual(node.left) if hasattr(node, "left") else ""
            if "owner_gated" in left or "owner_approval_required" in left:
                for comp in node.comparators:
                    if isinstance(comp, ast.Constant) and comp.value is False:
                        bag.owner_gated_false = True
                    if isinstance(comp, ast.Constant) and comp.value is True:
                        bag.gate_hits.add("owner_gated_true_check")
        if isinstance(node, ast.keyword) and node.arg == "owner_gated":
            if isinstance(node.value, ast.Constant) and node.value is False:
                bag.owner_gated_false = True
            if isinstance(node.value, ast.Constant) and node.value is True:
                bag.gate_hits.add("owner_gated_true_kw")
    return bag


def classify_module(source: str, rel: str) -> list[FunctionBag]:
    tree = ast.parse(source)
    env = module_string_constants(tree)
    bags: list[FunctionBag] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bags.append(classify_function(node, rel, env))
    return bags


classify_module = classify_module


classify_module = classify_module


def name_based_would_hit(fn_name: str) -> bool:
    """Naive detector used only as the rename-control foil. Not used for findings."""
    n = fn_name.lower()
    return any(
        k in n
        for k in (
            "publish",
            "upload",
            "pypi",
            "twine",
            "spend",
            "purge",
            "delete_user",
            "repo_create",
            "org_create",
        )
    )


name_based_would_hit = name_based_would_hit
