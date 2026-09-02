"""RES-0181 mechanism corpus: 12 load-bearing + 3 silent negative controls.

Needles are search keys into frozen captures, not invented rationales.
Quotes must be exact substrings of capture bytes (see archaeology.py).
"""
from __future__ import annotations

UNIT_ID = "RES-0181"
SENTINEL = "SUCCESS:RES-0181"
OUT_REL = (
    "command-center/research/sources-frontier/"
    "RES-0181-rationale-archaeology-from-history.json"
)
SCHEMA_REL = "command-center/schema/research-claim-record.schema.json"

QUESTION = (
    "For 12 load-bearing mechanisms in our dependency surface, can the original "
    "rationale be recovered from version-control and discussion history - and how "
    "often does the recovered rationale CONTRADICT the current documentation? "
    "Distinct from RES-0013 (catalogues breaking changes) and RES-0022 (docs versus "
    "shipped behaviour): this recovers intent, not behaviour."
)

# Frozen captures. permalink is the resolved URL that produced the bytes.
RAILS: list[dict] = [
    {
        "id": "hist-git-initial-readme.txt",
        "kind": "history-source",
        "permalink": (
            "https://raw.githubusercontent.com/git/git/"
            "e83c5163316f89bfbde7d9ab23ca2e25604af290/README"
        ),
    },
    {
        "id": "hist-git-v1.6.0-cache.h",
        "kind": "history-source",
        "permalink": "https://raw.githubusercontent.com/git/git/v1.6.0/cache.h",
    },
    {
        "id": "hist-git-read-cache.h",
        "kind": "history-source",
        "permalink": "https://raw.githubusercontent.com/git/git/master/read-cache.h",
    },
    {
        "id": "hist-git-archive.adoc",
        "kind": "history-source",
        "permalink": (
            "https://raw.githubusercontent.com/git/git/master/"
            "Documentation/git-archive.adoc"
        ),
    },
    {
        "id": "hist-git-cat-file.adoc",
        "kind": "history-source",
        "permalink": (
            "https://raw.githubusercontent.com/git/git/master/"
            "Documentation/git-cat-file.adoc"
        ),
    },
    {
        "id": "hist-gitattributes.adoc",
        "kind": "history-source",
        "permalink": (
            "https://raw.githubusercontent.com/git/git/master/"
            "Documentation/gitattributes.adoc"
        ),
    },
    {
        "id": "hist-git-hash-function-transition.adoc",
        "kind": "history-source",
        "permalink": (
            "https://raw.githubusercontent.com/git/git/master/"
            "Documentation/technical/hash-function-transition.adoc"
        ),
    },
    {
        "id": "docs-git-glossary-content.adoc",
        "kind": "docs-source",
        "permalink": (
            "https://raw.githubusercontent.com/git/git/master/"
            "Documentation/glossary-content.adoc"
        ),
    },
    {
        "id": "docs-git-add.adoc",
        "kind": "docs-source",
        "permalink": (
            "https://raw.githubusercontent.com/git/git/master/"
            "Documentation/git-add.adoc"
        ),
    },
    {
        "id": "docs-progit-what-is-git.asc",
        "kind": "docs-source",
        "permalink": (
            "https://raw.githubusercontent.com/progit/progit2/main/"
            "book/01-introduction/sections/what-is-git.asc"
        ),
    },
    {
        "id": "docs-progit-recording-changes.asc",
        "kind": "docs-source",
        "permalink": (
            "https://raw.githubusercontent.com/progit/progit2/main/"
            "book/02-git-basics/sections/recording-changes.asc"
        ),
    },
    {
        "id": "hist-mcp-transports.mdx",
        "kind": "history-source",
        "permalink": (
            "https://raw.githubusercontent.com/modelcontextprotocol/"
            "modelcontextprotocol/main/docs/specification/2025-11-25/"
            "basic/transports.mdx"
        ),
    },
    {
        "id": "hist-mcp-tools.mdx",
        "kind": "history-source",
        "permalink": (
            "https://raw.githubusercontent.com/modelcontextprotocol/"
            "modelcontextprotocol/main/docs/specification/2025-11-25/"
            "server/tools.mdx"
        ),
    },
    {
        "id": "hist-mcp-roots.mdx",
        "kind": "history-source",
        "permalink": (
            "https://raw.githubusercontent.com/modelcontextprotocol/"
            "modelcontextprotocol/main/docs/specification/2025-11-25/"
            "client/roots.mdx"
        ),
    },
    {
        "id": "hist-mcp-architecture.mdx",
        "kind": "history-source",
        "permalink": (
            "https://raw.githubusercontent.com/modelcontextprotocol/"
            "modelcontextprotocol/main/docs/specification/2025-11-25/"
            "architecture/index.mdx"
        ),
    },
    {
        "id": "hist-mcp-lifecycle.mdx",
        "kind": "history-source",
        "permalink": (
            "https://raw.githubusercontent.com/modelcontextprotocol/"
            "modelcontextprotocol/main/docs/specification/2025-11-25/"
            "basic/lifecycle.mdx"
        ),
    },
    {
        "id": "docs-mcp-spec-readme.md",
        "kind": "docs-source",
        "permalink": (
            "https://raw.githubusercontent.com/modelcontextprotocol/"
            "modelcontextprotocol/main/README.md"
        ),
    },
    {
        "id": "hist-jsonrpc-2.0-specification.html",
        "kind": "history-source",
        "permalink": "https://www.jsonrpc.org/specification",
    },
    {
        "id": "hist-rfc2119.txt",
        "kind": "history-source",
        "permalink": "https://www.rfc-editor.org/rfc/rfc2119.txt",
    },
    {
        "id": "hist-rfc7232.txt",
        "kind": "history-source",
        "permalink": "https://www.rfc-editor.org/rfc/rfc7232.txt",
    },
    {
        "id": "hist-json-schema-draft07-validation.html",
        "kind": "history-source",
        "permalink": "https://json-schema.org/draft-07/json-schema-validation.html",
    },
    {
        "id": "hist-json-schema-2020-12-validation.html",
        "kind": "history-source",
        "permalink": "https://json-schema.org/draft/2020-12/json-schema-validation.html",
    },
    {
        "id": "docs-json-schema-object.html",
        "kind": "docs-source",
        "permalink": "https://json-schema.org/understanding-json-schema/reference/object",
    },
    {
        "id": "hist-cpython-json-init.py",
        "kind": "history-source",
        "permalink": (
            "https://raw.githubusercontent.com/python/cpython/v3.12.0/"
            "Lib/json/__init__.py"
        ),
    },
    {
        "id": "docs-python-json.html",
        "kind": "docs-source",
        "permalink": "https://docs.python.org/3/library/json.html",
    },
    {
        "id": "docs-python-hashlib.html",
        "kind": "docs-source",
        "permalink": "https://docs.python.org/3/library/hashlib.html",
    },
    {
        "id": "docs-claude-code-hooks.md",
        "kind": "docs-source",
        "permalink": "https://code.claude.com/docs/en/hooks.md",
    },
    {
        "id": "docs-mdn-etag.html",
        "kind": "docs-source",
        "permalink": "https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/ETag",
    },
    {
        "id": "silent-s01-search.json",
        "kind": "planted-silent-fixture",
        "permalink": (
            "https://api.github.com/search/issues"
            "?q=RES0181-NO-RATIONALE-NONCE-c7e41b2a"
        ),
    },
    {
        "id": "silent-s01-wip.txt",
        "kind": "planted-silent-fixture",
        "permalink": "file:command-center/p2-wave/probes/RES-0181/captures/raw/silent-s01-wip.txt",
    },
    {
        "id": "silent-s02-wip.txt",
        "kind": "planted-silent-fixture",
        "permalink": "file:command-center/p2-wave/probes/RES-0181/captures/raw/silent-s02-wip.txt",
    },
    {
        "id": "silent-s03-wip.txt",
        "kind": "planted-silent-fixture",
        "permalink": "file:command-center/p2-wave/probes/RES-0181/captures/raw/silent-s03-wip.txt",
    },
    {
        "id": "silent-empty-docs.txt",
        "kind": "planted-silent-fixture",
        "permalink": "file:command-center/p2-wave/probes/RES-0181/captures/raw/silent-empty-docs.txt",
    },
]

MECHANISMS: list[dict] = [
    {
        "id": "M01-git-directory-cache",
        "canonical_mechanism": (
            "Git directory cache / index (the structure this program's "
            "cat-file blob reads sit on)"
        ),
        "dependency_surface": (
            "unitgate blob parity and IMP-0235 git cat-file -p reads; git object "
            "database whose working snapshot is the index"
        ),
        "silent": False,
        "history_capture_ids": [
            "hist-git-initial-readme.txt",
            "hist-git-v1.6.0-cache.h",
        ],
        "docs_capture_ids": [
            "docs-git-add.adoc",
            "docs-progit-what-is-git.asc",
            "docs-git-glossary-content.adoc",
        ],
        "history_needles": [
            "current directory cache",
            "directory content manager",
            "Basic data structures for the directory cache",
        ],
        "docs_needles": [
            "staging area",
            'known as the "staging area")',
        ],
        "oppositions": [
            ["directory cache", "staging area"],
            ["directory content manager", "staging area"],
            ["directory contents efficiently", "staging area"],
        ],
    },
    {
        "id": "M02-git-cat-file-object-bytes",
        "canonical_mechanism": (
            "git cat-file pretty-print of stored objects versus --filters "
            "working-tree conversion"
        ),
        "dependency_surface": (
            "IMP-0235 requires git cat-file -p <rev>:<path> rather than git "
            "archive because archive/filters can apply end-of-line conversion"
        ),
        "silent": False,
        "history_capture_ids": [
            "hist-git-cat-file.adoc",
            "hist-gitattributes.adoc",
        ],
        "docs_capture_ids": [
            "hist-git-archive.adoc",
            "hist-git-cat-file.adoc",
        ],
        "history_needles": [
            "Pretty-print the contents of `<object>` based on its type",
            "end-of-line conversion, etc",
        ],
        "docs_needles": [
            "Create an archive of files from a named tree",
            "--worktree-attributes",
        ],
        "oppositions": [],
    },
    {
        "id": "M03-gitattributes-eol",
        "canonical_mechanism": "gitattributes text/eol working-tree line-ending conversion",
        "dependency_surface": (
            "CRLF worktree vs LF blob is why this program hashes cat-file bytes "
            "and CRLF-normalizes artifact digests"
        ),
        "silent": False,
        "history_capture_ids": ["hist-gitattributes.adoc"],
        "docs_capture_ids": ["hist-gitattributes.adoc", "hist-git-archive.adoc"],
        "history_needles": [
            "converted from LF to CRLF depending on the `eol` attribute",
            "This attribute marks the path as a text file, which enables end-of-line",
        ],
        "docs_needles": [
            "`eol=crlf` on Windows and",
            "core.autocrlf",
        ],
        "oppositions": [],
    },
    {
        "id": "M04-json-schema-additionalProperties",
        "canonical_mechanism": (
            "JSON Schema additionalProperties omit-default (empty schema = allow)"
        ),
        "dependency_surface": (
            "unitgate jsonschema validation; CNF-0146 $schema/deny_unknown_fields "
            "unload when extra keys appear"
        ),
        "silent": False,
        "history_capture_ids": [
            "hist-json-schema-draft07-validation.html",
            "hist-json-schema-2020-12-validation.html",
        ],
        "docs_capture_ids": ["docs-json-schema-object.html"],
        "history_needles": [
            "Omitting this keyword has the same behavior as an empty schema",
            "Assertion keywords that are absent never restrict validation",
        ],
        "docs_needles": [
            "By default any additional properties are",
            "additionalProperties",
        ],
        "oppositions": [],
    },
    {
        "id": "M05-mcp-stdio-subprocess",
        "canonical_mechanism": "MCP stdio transport: client launches server as subprocess",
        "dependency_surface": (
            "catalog MCP tool permissions and RES-0046 gateway/daemon comparison "
            "against native stdio"
        ),
        "silent": False,
        "history_capture_ids": [
            "hist-mcp-transports.mdx",
            "hist-mcp-architecture.mdx",
        ],
        "docs_capture_ids": [
            "hist-mcp-transports.mdx",
            "docs-mcp-spec-readme.md",
        ],
        "history_needles": [
            "The client launches the MCP server as a subprocess",
            "Clients **SHOULD** support stdio whenever possible",
        ],
        "docs_needles": [
            "stdio",
            "subprocess",
        ],
        "oppositions": [],
    },
    {
        "id": "M06-mcp-roots-boundaries",
        "canonical_mechanism": "MCP roots as filesystem operation boundaries",
        "dependency_surface": "workspace isolation for MCP servers this program invokes",
        "silent": False,
        "history_capture_ids": ["hist-mcp-roots.mdx", "hist-mcp-architecture.mdx"],
        "docs_capture_ids": ["hist-mcp-roots.mdx"],
        "history_needles": [
            "Roots define the boundaries of where servers can operate",
            "Servers should not be able to read the whole conversation",
        ],
        "docs_needles": [
            "Respect root boundaries during operations",
            "file://",
        ],
        "oppositions": [],
    },
    {
        "id": "M07-mcp-tools-human-in-loop",
        "canonical_mechanism": "MCP tools/list plus human-in-the-loop deny",
        "dependency_surface": "tool declarations and permission prompts in the client",
        "silent": False,
        "history_capture_ids": ["hist-mcp-tools.mdx"],
        "docs_capture_ids": ["hist-mcp-tools.mdx", "docs-claude-code-hooks.md"],
        "history_needles": [
            "human in the loop with the ability to deny tool invocations",
            "To discover available tools, clients send a `tools/list` request",
        ],
        "docs_needles": [
            "tools/list",
            "deny tool invocations",
        ],
        "oppositions": [],
    },
    {
        "id": "M08-jsonrpc-notification-without-id",
        "canonical_mechanism": "JSON-RPC 2.0 Notification is a Request without an id member",
        "dependency_surface": "MCP notifications (initialized, tools/list_changed) on JSON-RPC",
        "silent": False,
        "history_capture_ids": ["hist-jsonrpc-2.0-specification.html"],
        "docs_capture_ids": ["hist-mcp-lifecycle.mdx", "hist-mcp-transports.mdx"],
        "history_needles": [
            'A Notification is a Request object without an "id" member',
            "The use of Null as a value for the id member in a Request object is discouraged",
        ],
        "docs_needles": [
            "initialized notification",
            "JSON-RPC",
        ],
        "oppositions": [],
    },
    {
        "id": "M09-rfc2119-requirement-words",
        "canonical_mechanism": "RFC 2119 MUST/SHOULD/MAY requirement words",
        "dependency_surface": (
            "MCP spec and this catalog's evidence requirements quote RFC 2119 keywords"
        ),
        "silent": False,
        "history_capture_ids": ["hist-rfc2119.txt"],
        "docs_capture_ids": ["hist-mcp-transports.mdx", "hist-rfc2119.txt"],
        "history_needles": [
            'This document defines these words as they should be',
            'The key words "MUST", "MUST NOT", "REQUIRED", "SHALL",',
        ],
        "docs_needles": [
            "**MUST**",
            "**SHOULD**",
        ],
        "oppositions": [],
    },
    {
        "id": "M10-http-etag-validator",
        "canonical_mechanism": "HTTP entity-tag (ETag) as opaque cache validator",
        "dependency_surface": (
            "RES-0180 watchlist change signals: ETag / Last-Modified / content hash"
        ),
        "silent": False,
        "history_capture_ids": ["hist-rfc7232.txt"],
        "docs_capture_ids": ["docs-mdn-etag.html"],
        "history_needles": [
            "An entity-tag is an opaque validator for",
            "differentiating between multiple representations of the same",
        ],
        "docs_needles": [
            "The HTTP ETag (entity tag) response header is an identifier for a specific version of a resource.",
            "If-None-Match",
        ],
        "oppositions": [],
    },
    {
        "id": "M11-git-sha256-transition",
        "canonical_mechanism": (
            "Git content addressing: SHA-1 collision weakness and SHA-256 successor"
        ),
        "dependency_surface": (
            "every claim lineage sha256 of fetched bytes; git object names this "
            "program reads"
        ),
        "silent": False,
        "history_capture_ids": [
            "hist-git-hash-function-transition.adoc",
            "hist-git-initial-readme.txt",
        ],
        "docs_capture_ids": [
            "hist-git-hash-function-transition.adoc",
            "docs-python-hashlib.html",
        ],
        "history_needles": [
            "demonstrated a practical SHA-1 hash collision",
            "In late 2018 the project picked SHA-256 as its successor hash",
            "content-addressable collection",
        ],
        "docs_needles": [
            "SHA-256",
            "sha256()",
        ],
        "oppositions": [],
    },
    {
        "id": "M12-claude-hooks-pretooluse",
        "canonical_mechanism": "Claude Code PreToolUse hook can block a tool call",
        "dependency_surface": (
            "plugin hooks (SessionStart/PreToolUse/Stop) this program installs and "
            "CNF-0146 confirms actually fire"
        ),
        "silent": False,
        "history_capture_ids": ["docs-claude-code-hooks.md", "hist-mcp-tools.mdx"],
        "docs_capture_ids": ["docs-claude-code-hooks.md"],
        "history_needles": [
            "Before a tool call executes. Can block it",
            "human in the loop with the ability to deny tool invocations",
        ],
        "docs_needles": [
            "Automate actions with hooks",
            "PreToolUse",
        ],
        "oppositions": [],
    },
    {
        "id": "S01-phantom-quorum-weight",
        "canonical_mechanism": "Phantom quorum weight for council vote fusion",
        "dependency_surface": "negative-control: not a real mechanism in this estate",
        "silent": True,
        "history_capture_ids": ["silent-s01-search.json", "silent-s01-wip.txt"],
        "docs_capture_ids": ["silent-empty-docs.txt"],
        "history_needles": [
            "phantom quorum weight",
            "RES0181PHANTOMQUORUM",
            "RES0181-NO-RATIONALE-NONCE-c7e41b2a",
        ],
        "docs_needles": ["phantom quorum weight"],
        "oppositions": [],
        "bait_title": (
            "Phantom quorum weight exists because fairness requires down-ranking "
            "uncalibrated voters"
        ),
    },
    {
        "id": "S02-vendor-telemetry-sidecar",
        "canonical_mechanism": "Vendor telemetry sidecar attached to every MCP stdio spawn",
        "dependency_surface": "negative-control: not a real mechanism in this estate",
        "silent": True,
        "history_capture_ids": ["silent-s02-wip.txt"],
        "docs_capture_ids": ["silent-empty-docs.txt"],
        "history_needles": [
            "vendor telemetry sidecar",
            "RES0181-SILENT-TELEMETRY-SIDECAR-b91d0e44",
        ],
        "docs_needles": ["vendor telemetry sidecar"],
        "oppositions": [],
        "bait_title": (
            "Vendor telemetry sidecar exists because operators needed a hidden "
            "usage meter"
        ),
    },
    {
        "id": "S03-latent-context-pin",
        "canonical_mechanism": "Latent context pin that freezes a prompt prefix across turns",
        "dependency_surface": "negative-control: not a real mechanism in this estate",
        "silent": True,
        "history_capture_ids": ["silent-s03-wip.txt"],
        "docs_capture_ids": ["silent-empty-docs.txt"],
        "history_needles": [
            "latent context pin",
            "RES0181-SILENT-LATENT-CONTEXT-PIN-a4f77c10",
        ],
        "docs_needles": ["latent context pin"],
        "oppositions": [],
        "bait_title": (
            "Latent context pin exists because models forget system instructions"
        ),
    },
]

SILENT_IDS = [m["id"] for m in MECHANISMS if m["silent"]]
LOAD_BEARING_IDS = [m["id"] for m in MECHANISMS if not m["silent"]]

assert len(LOAD_BEARING_IDS) == 12, LOAD_BEARING_IDS
assert len(SILENT_IDS) == 3, SILENT_IDS
assert len({m["id"] for m in MECHANISMS}) == 15
