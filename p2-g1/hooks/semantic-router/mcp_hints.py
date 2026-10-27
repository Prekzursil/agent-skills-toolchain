"""Curated per-server enrichment for the semantic MCP index (data-only, no I/O).

build_index.py embeds, for each server in ~/.mcp.json, a short natural-language
purpose plus representative TOOL-NAME keywords. Tool names are a strong semantic
signal ("decompile_function", "glide_dock", "tavily_search") that a regex table
cannot capture, and they let the embedding fire on tasks whose wording never
mentions the server. Keys are the exact server names from ~/.mcp.json; a server
missing here still gets indexed from its name + any capabilities.py label that
references it (graceful degradation).

This is a maintained snapshot of tool families, NOT a live introspection — when a
server's tools change materially, refresh the relevant line. It only affects
ranking, never correctness (fail-open everywhere downstream).
"""

MCP_HINTS = {
    # --- reverse engineering / low-level ---
    "ghidra-mcp": "Ghidra reverse engineering: decompile and disassemble functions, list imports exports strings classes namespaces, cross references xrefs, rename functions and variables, set prototypes and comments on a native binary.",
    "ida-pro-mcp": "IDA Pro reverse engineering: open binary files, manage IDA instances, decompile and analyze native executables.",
    "binary-ninja-mcp": "Binary Ninja reverse engineering: decompile functions, intermediate language IL, list imports exports strings types, cross references, patch bytes, rename symbols, generate signatures, version diffing for trainers and hooks.",
    "radare2": "radare2 r2 reverse engineering: disassemble, analyze and explore a native binary from the command line.",
    "cheatengine": "Cheat Engine runtime game memory analysis: scan memory, AOB array-of-bytes scan, pointer chains, read and write process memory, set breakpoints, disassemble, structures, build trainers.",
    "frida-mcp": "Frida dynamic instrumentation: attach to or spawn a process, hook and intercept functions at runtime, enumerate processes and devices, instrument apps live.",
    "apktool-mcp": "Apktool Android reverse engineering: decode an APK, read and edit smali code, resources and AndroidManifest, search and rebuild the APK.",
    "jadx-mcp": "JADX Android decompiler: decompile an APK to Java, browse classes methods fields, read smali, manifest, strings and cross references from dex.",
    "hexstrike-ai": "HexStrike offensive security and penetration testing automation: orchestrate authorized security engagement tooling.",
    "cve-mcp": "CVE vulnerability lookup: query the CVE database for security advisories and vulnerability details.",
    # --- cheminformatics / computational chemistry / bio ---
    "rdkit": "RDKit cheminformatics (license-free): SMILES to molecule, molecular descriptors, TPSA logP molecular weight, Morgan fingerprints, Tanimoto similarity, substructure search, Murcko scaffolds, 2D and 3D coordinates.",
    "schrodinger": "Schrodinger computational drug discovery: Glide docking and grids, LigPrep, protein PrepWizard, Prime MMGBSA binding free energy, QikProp ADMET, Jaguar pKa, FEP, Maestro, PyMOL rendering, structure-based screening.",
    "tooluniverse": "ToolUniverse 2500+ biomedical tools: drug targets, drug-drug interactions, ADMET prediction, CYP450 enzymes, gene-disease associations, FDA drug labels, pharmacology, drug repurposing, pharmacovigilance.",
    # --- literature / research / web ---
    "scholarly-access": "Scholarly access: resolve papers, fetch metadata, find and download open-access PDFs, citation graphs, summarize papers by DOI.",
    "paper-search": "Academic paper search and download across arXiv, PubMed, bioRxiv, medRxiv, Crossref, OpenAlex, Semantic Scholar, DBLP, DOAJ, Zenodo; read full text.",
    "firecrawl": "Firecrawl web data: scrape, crawl, map, search and extract structured data from websites; deep research over the web.",
    "tavily": "Tavily web search, crawl, map and extract for research and current information.",
    "searxng": "SearXNG metasearch: privacy-respecting web search across many engines.",
    "perplexity": "Perplexity web research: ask a question and get a synthesized answer with sources.",
    # --- code intelligence / docs / repo ---
    "context7": "Context7 live library documentation: resolve a library and fetch current API reference and usage docs for frameworks and SDKs.",
    "repomix": "Repomix codebase packing: consolidate a whole repository into one AI-friendly file for review and analysis.",
    # --- data / files / docs ---
    "excel": "Excel spreadsheet operations: read and write workbooks and worksheets, formulas, pivot tables, charts, formatting.",
    "pdf-reader": "PDF intelligence: read, search and extract text, tables and evidence from PDF documents.",
    "ocr-suite": "OCR optical character recognition: extract text from scanned images and PDFs across multiple engines.",
    "markitdown": "MarkItDown document conversion: convert docx, pptx, xlsx, html and other documents to Markdown.",
    # --- code quality / CI / coverage / vcs / cloud ---
    "qlty": "Qlty code quality: lint checks, code smells, metrics and coverage transforms.",
    "codecov": "Codecov coverage: repo, commit, pull-request and per-file coverage reports.",
    "github": "GitHub: issues, pull requests, releases, workflows and repositories via the GitHub API.",
    "github_cli": "GitHub CLI: create and view issues, pull requests, releases, workflows, projects and repos.",
    "docker": "Docker: create and list containers, deploy compose stacks, read container logs.",
    # --- memory / orchestration ---
    "basic-memory": "Basic Memory semantic vault: search notes, build context, recall prior work, decisions and project facts from past sessions.",
    "mem0-secondary": "Mem0 memory: store and recall durable facts and preferences.",
    "ralph-orchestrator": "Ralph orchestrator: inspect and manage autonomous agent loop control-plane state.",
    # --- media / social ---
    "huggingface": "Hugging Face Hub: search models datasets and spaces, image generation, papers, file management.",
    "insta-mcp": "Instagram: timeline, posts, followers, stories, direct messages, search, upload photos reels and videos.",
    "tiktok": "TikTok public research: trending videos, hashtags, user info and posts, video details and comments.",
    "fb-messenger": "Facebook Messenger: list and read threads, search messages.",
}
