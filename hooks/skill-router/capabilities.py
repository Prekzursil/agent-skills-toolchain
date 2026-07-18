"""Shared capability map — keyword / hand-roll signature -> MCP-server family.

SINGLE SOURCE OF TRUTH for MCP routing, read by BOTH the skill-router (route.py, prompt-time) and the
strong-tool-nudge (PreToolUse, command-time). Replaces route.py's 8-entry MCP_HINTS and covers all ~48
connected MCP servers (today ~40 are invisible to routing). DRY: one table, two readers (harmony F1).

Each row = (compiled_regex, label, is_hand_roll). is_hand_roll=True rows ALSO fire the strong-tool-nudge
when the agent is about to DO that thing via Bash/Write (e.g. `pip install rdkit`) — the moment the
prompt-time router misses. Pure library, no I/O, importable, dependency-free.
"""
import re

# (regex, route_label, is_hand_roll_signature)
_RAW = [
    # --- cheminformatics / computational chemistry ---
    (r"\b(smiles|molecul|descriptor|tanimoto|cheminform|rdkit|scaffold|fingerprint|tpsa|logp|morgan|substructure)\b",
     "mcp__rdkit__* (cheminformatics / descriptors)", False),
    (r"(pip install rdkit|from rdkit|import rdkit|conda install[^\n]*rdkit)",
     "mcp__rdkit__* — call the rdkit MCP, don't pip-install/import rdkit locally", True),
    (r"\b(dock|docking|glide|\bfep\b|schrod|binding affinity|prepwiz|ligprep|admet|pymol|mmgbsa|\bpka\b|maestro|forcefield)\b",
     "mcp__schrodinger__* (docking / FEP / ADMET / structure prep)", False),
    (r"\b(pharmacolog|drug target|affinity|ic50|\bki\b|agonist|antagonist|clinical trial|tooluniverse|gene[- ]disease|mechanism of action)\b",
     "mcp__tooluniverse__* (2500+ pharmacology / bio tools)", False),
    # --- literature / research / web ---
    (r"\b(paper|papers|citation|pubmed|scholar|\bdoi\b|preprint|literature review|arxiv|open[- ]access pdf)\b",
     "mcp__scholarly-access__* (papers / citations / OA PDFs)", False),
    (r"\b(deep research|cited report|literature synthesis)\b",
     "mcp__firecrawl__ / exa / tavily (deep web research)", False),
    (r"\b(scrape|crawl|web search|search online|fetch (the )?url|firecrawl|tavily)\b",
     "mcp__firecrawl__* / tavily / scrapegraph (scrape / crawl / search)", False),
    (r"(requests\.get|urllib\.request|httpx\.get|curl https?://)[^\n]*(scrape|html|parse|soup|beautifulsoup)",
     "mcp__firecrawl_scrape / tavily — use the scrape MCP, don't hand-roll HTTP scraping", True),
    # --- reverse engineering / low-level ---
    (r"\b(reverse engineer|disassembl|decompil|binary analysis|function offset|x64dbg|\baob\b|signature scan|ghidra|\bida\b)\b",
     "mcp__ghidra-mcp__ / ida-pro-mcp / binary-ninja-mcp (RE)", False),
    (r"\b(cheat engine|memory scan|pointer chain|game trainer|read process memory)\b",
     "mcp__cheatengine__* (memory scan / RE)", False),
    (r"\b(frida|hook (the )?function|instrument (the )?process|runtime hook)\b",
     "mcp__frida-mcp__* (dynamic instrumentation)", False),
    # --- memory ---
    (r"\b(remember|recall|prior work|earlier session|decision log|what did we (decide|do)|past notes)\b",
     "mcp__basic-memory__* (semantic memory vault)", False),
    # --- code intelligence / repo ---
    (r"\b(find symbol|references to|rename symbol|go to definition|find implementations|semantic code search|lsp)\b",
     "mcp__plugin_serena_serena__* (LSP code intelligence)", False),
    (r"(git grep|grep -r[^\n]*\bdef |manual symbol walk|ctags|cscope)",
     "mcp__serena find_symbol — use serena LSP, not manual symbol grepping", True),
    (r"\b(pack (the )?codebase|repomix|consolidate (the )?repo|whole[- ]repo context)\b",
     "mcp__repomix__* (codebase packing)", False),
    (r"\b(library docs|api reference|how to use (the )?(library|framework|sdk)|context7|latest docs for)\b",
     "mcp__context7__* (live library docs)", False),
    # --- data / files / docs ---
    (r"\b(excel|xlsx|spreadsheet|pivot table|workbook|worksheet)\b",
     "mcp__excel__* (Excel ops)", False),
    (r"(pandas[^\n]*read_csv|csv\.reader|openpyxl|xlsxwriter)",
     "mcp__excel__* — use the excel MCP for spreadsheet ops", True),
    (r"\b(\bpdf\b|extract.*pdf|read (the )?pdf|pdf table)\b",
     "mcp__pdf-reader__* / mcp__ocr-suite__* (PDF / OCR)", False),
    (r"(pdfplumber|PyPDF2|fitz\.open|pdfminer)",
     "mcp__pdf-reader__* — use the pdf-reader MCP, don't hand-parse PDFs", True),
    (r"\b(ocr|optical character|scanned (image|doc) text|tesseract)\b",
     "mcp__ocr-suite__* (OCR engines)", False),
    (r"\b(markitdown|convert.*to markdown|docx to|pptx to)\b",
     "mcp__markitdown__* (document -> markdown)", False),
    # --- database ---
    (r"\b(postgres|sql query|database schema|\bpsql\b|similarity search|pgvector|generate embedding)\b",
     "mcp__postgres__* (Postgres / pgvector / embeddings)", False),
    (r"\b(graphql|introspect (the )?schema|graphql query)\b",
     "mcp__mcp-graphql__* (GraphQL)", False),
    # --- code quality / CI / security ---
    (r"\b(sonar|sonarqube|code smell|quality gate)\b",
     "mcp__sonarqube__* (code quality)", False),
    (r"\b(codacy|deepsource|deepscan|\bqlty\b|coverage report|codecov)\b",
     "mcp__codacy__ / deepsource / qlty / codecov (quality / coverage)", False),
    (r"\b(semgrep|\bsast\b|static analysis security)\b",
     "mcp__semgrep__* (SAST)", False),
    (r"\b(sentry|error tracking|issue triage|analyze (the )?stack trace)\b",
     "mcp__sentry__* (error monitoring)", False),
    # --- browser / e2e ---
    (r"\b(playwright|browser automation|e2e test|headless browser|fill (the )?form online)\b",
     "mcp__playwright__* / chrome-devtools (browser automation)", False),
    (r"\b(chrome devtools|lighthouse|web perf|network requests panel|console messages)\b",
     "mcp__chrome-devtools__* (Chrome DevTools)", False),
    # --- devops / cloud / vcs ---
    (r"\b(docker|container|docker-compose|deploy (a )?container)\b",
     "mcp__docker__* (Docker)", False),
    (r"\b(digitalocean|droplet|app platform)\b",
     "mcp__digitalocean__* (DigitalOcean)", False),
    (r"\b(github (issue|pr|pull request|release|workflow)|\bgh pr\b|\bgh issue\b)\b",
     "mcp__github_cli__* (GitHub CLI)", False),
    # --- media generation ---
    (r"\b(text[- ]to[- ]speech|voice clone|\btts\b|elevenlabs|audio generation|sound effect)\b",
     "mcp__elevenlabs__* (voice / audio)", False),
    (r"\b(huggingface|\bhf\b model|\bhf\b dataset|image generation model|diffusion model)\b",
     "mcp__huggingface__* (HF Hub)", False),
    # --- bio / science connectors ---
    (r"\b(gene expression|rna[- ]seq|protein[- ]protein interaction|string db|biorender|consensus search)\b",
     "mcp__claude_ai_* (Synthesize Bio / protein-interaction / BioRender / Consensus)", False),
    # --- social (rare, but routable) ---
    (r"\b(tiktok|instagram post|messenger thread)\b",
     "mcp__tiktok__ / insta-mcp / fb-messenger (social)", False),
]

CAPABILITIES = [(re.compile(rx, re.IGNORECASE), label, hand) for rx, label, hand in _RAW]


def match(text, hand_roll_only=False):
    """Return [(label, is_hand_roll)] for capabilities matching `text` (a prompt, or a command/content string).
    hand_roll_only=True -> only return rows flagged as hand-roll signatures (for the PreToolUse nudge)."""
    out, seen = [], set()
    for rx, label, hand in CAPABILITIES:
        if hand_roll_only and not hand:
            continue
        if rx.search(text) and label not in seen:
            seen.add(label)
            out.append((label, hand))
    return out
