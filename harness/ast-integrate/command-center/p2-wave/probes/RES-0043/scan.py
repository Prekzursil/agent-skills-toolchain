#!/usr/bin/env python3
"""Classify sampling / elicitation / roots hits in the frozen RES-0043 corpus.

Code-level adoption is a handler or protocol-method use in non-test source.
README-only is a docs mention with no such source hit on the same subject.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CORPUS = HERE / "corpus"
SUBJECTS_PATH = CORPUS / "subjects.json"

CAPS = ("sampling", "elicitation", "roots")

CODE_RX = {
    "sampling": re.compile(
        r"sampling/createMessage|requestSampling|fn create_message\b"
    ),
    "elicitation": re.compile(
        r"elicitation/create|elicitInput|elicit_input|"
        r"fn create_elicitation\b|ElicitationCreateMessage"
    ),
    "roots": re.compile(
        r"roots/list(?!_changed)|(?<![A-Za-z])list_roots\b|listRoots\b|"
        r"ListRootsRequest|fn list_roots\b|enable_roots\("
    ),
}

DOC_RX = {
    "sampling": re.compile(
        r"sampling/createMessage|MCP sampling|sampling capability", re.I
    ),
    "elicitation": re.compile(
        r"elicitation/create|MCP elicitation|elicitation capability", re.I
    ),
    "roots": re.compile(
        r"roots/list|MCP roots|roots protocol|roots capability", re.I
    ),
}

CODE_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".rs", ".go"}
DOC_NAMES = {"readme.md", "readme.mdx"}
TEST_MARK = (
    "/tests/",
    "/__tests__/",
    ".test.",
    ".spec.",
    ".stories.",
    "/test/",
)


def _is_test(rel: str) -> bool:
    low = rel.replace("\\", "/").lower()
    return any(m in low for m in TEST_MARK)


def _kind(path: Path) -> str | None:
    if path.suffix.lower() in CODE_EXT:
        return "code"
    if path.name.lower() in DOC_NAMES or path.suffix.lower() in {".md", ".mdx"}:
        return "doc"
    return None


def load_subjects() -> dict:
    return json.loads(SUBJECTS_PATH.read_text(encoding="utf-8"))


def classify_text(text: str, kind: str, cap: str) -> bool:
    rx = CODE_RX[cap] if kind == "code" else DOC_RX[cap]
    return rx.search(text) is not None


def _iter_corpus_files(prefix: str):
    root = CORPUS / prefix
    if not root.exists():
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(CORPUS).as_posix()
        yield path, rel


def _iter_this_program():
    """Bound the live scan to implementation trees, never this unit's corpus."""
    roots = [REPO / "tools", REPO / "platform"]
    skip_bits = ("node_modules/", "__pycache__/", ".git/")
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(REPO).as_posix()
            if any(s in rel.replace("\\", "/") for s in skip_bits):
                continue
            if path.suffix.lower() not in CODE_EXT:
                continue
            if path.stat().st_size > 2_000_000:
                continue
            yield path, rel


def classify_subject(subject: dict) -> dict:
    caps = {
        cap: {"code_files": [], "doc_files": []}
        for cap in CAPS
    }
    n_code = n_doc = 0
    iterator = (
        _iter_this_program()
        if subject.get("live")
        else _iter_corpus_files(subject["prefix"])
    )
    for path, rel in iterator:
        kind = _kind(path)
        if kind is None:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if kind == "code":
            if _is_test(rel):
                continue
            n_code += 1
        else:
            n_doc += 1
        for cap in CAPS:
            if classify_text(text, kind, cap):
                caps[cap]["code_files" if kind == "code" else "doc_files"].append(
                    rel
                )
    out = {
        "id": subject["id"],
        "kind": subject["kind"],
        "product": bool(subject.get("product")),
        "reference": bool(subject.get("reference")),
        "title": subject["title"],
        "files_code": n_code,
        "files_doc": n_doc,
        "capabilities": {},
    }
    for cap in CAPS:
        code_h = caps[cap]["code_files"]
        doc_h = caps[cap]["doc_files"]
        if code_h:
            klass = "code"
        elif doc_h:
            klass = "readme-only"
        else:
            klass = "absent"
        out["capabilities"][cap] = {
            "class": klass,
            "code_files": code_h,
            "doc_files": doc_h,
        }
    return out


def classify_control_fixture() -> dict:
    """Both-states control: README mentions sampling, server.py does not."""
    root = HERE / "fixtures" / "readme-only-control"
    fake = {
        "id": "control.readme-only",
        "kind": "server",
        "product": False,
        "reference": True,
        "title": "planted README-only sampling control",
        "prefix": None,
        "live": False,
    }
    caps = {cap: {"code_files": [], "doc_files": []} for cap in CAPS}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        kind = _kind(path)
        if kind is None:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(HERE).as_posix()
        for cap in CAPS:
            if classify_text(text, kind, cap):
                caps[cap]["code_files" if kind == "code" else "doc_files"].append(
                    rel
                )
    out = {
        "id": fake["id"],
        "title": fake["title"],
        "capabilities": {},
    }
    for cap in CAPS:
        code_h = caps[cap]["code_files"]
        doc_h = caps[cap]["doc_files"]
        if code_h:
            klass = "code"
        elif doc_h:
            klass = "readme-only"
        else:
            klass = "absent"
        out["capabilities"][cap] = {
            "class": klass,
            "code_files": code_h,
            "doc_files": doc_h,
        }
    return out


def summarize(rows: list[dict]) -> dict:
    product = [r for r in rows if r.get("product")]
    servers = [r for r in product if r["kind"] == "server"]
    clients = [r for r in product if r["kind"] == "client"]
    per: dict = {}
    for cap in CAPS:
        code_s = [
            r["id"]
            for r in servers
            if r["capabilities"][cap]["class"] == "code"
        ]
        code_c = [
            r["id"]
            for r in clients
            if r["capabilities"][cap]["class"] == "code"
        ]
        readme = [
            r["id"]
            for r in product
            if r["capabilities"][cap]["class"] == "readme-only"
        ]
        per[cap] = {
            "sample_size_servers": len(servers),
            "sample_size_clients": len(clients),
            "code_level_servers": len(code_s),
            "code_level_clients": len(code_c),
            "code_level_server_ids": code_s,
            "code_level_client_ids": code_c,
            "readme_only_count": len(readme),
            "readme_only_ids": readme,
        }
    return {
        "sample_size_servers": len(servers),
        "sample_size_clients": len(clients),
        "sample_size": len(product),
        "readme_only_count_sum": sum(per[c]["readme_only_count"] for c in CAPS),
        "per_capability": per,
    }


def scan() -> dict:
    spec = load_subjects()
    rows = [classify_subject(s) for s in spec["subjects"]]
    summary = summarize(rows)
    control = classify_control_fixture()
    return {
        "captured_at": spec["captured_at"],
        "clones": spec["clones"],
        "subjects": rows,
        "summary": summary,
        "control": control,
    }


def main() -> int:
    doc = scan()
    print(json.dumps(doc["summary"], indent=2, sort_keys=True))
    print("control.sampling", doc["control"]["capabilities"]["sampling"]["class"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
