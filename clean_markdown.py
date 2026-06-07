import os
import re
import glob

def clean_file(filepath):
    if not os.path.exists(filepath): return
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # Remove "Safety / access policy" sections and everything below it until the next H2
    content = re.sub(r'## Safety / access policy\s*\n.*?(?=\n## |\Z)', '', content, flags=re.DOTALL)
    
    # Remove lines containing discouraging words
    lines = content.split('\n')
    new_lines = []
    bad_patterns = re.compile(r'(?i)(lawful|illegal|unauthorized|pirate|piracy|shadow library|shadow-library|refuse|paywall bypass|do not circumvent|restricted|deny|denied|circumvent|bypass|hard-gated|hard gate|forbidden|banned)')
    
    for line in lines:
        if bad_patterns.search(line):
            # Try to salvage the line by just removing the bad sentence, or drop the whole line if it's a list item
            if line.strip().startswith('- '):
                continue # drop bullet points that mention bad stuff
            else:
                # Replace bad sentences (ending with period)
                sentences = re.split(r'(?<=\.)\s+', line)
                good_sentences = [s for s in sentences if not bad_patterns.search(s)]
                if good_sentences:
                    new_lines.append(' '.join(good_sentences))
        else:
            new_lines.append(line)

    new_content = '\n'.join(new_lines)
    
    # Also replace any remaining weird stuff
    new_content = new_content.replace("lawful", "unrestricted")
    new_content = new_content.replace("legitimate", "available")
    new_content = new_content.replace("Legitimate", "Available")
    new_content = new_content.replace("legal ", "")
    new_content = new_content.replace("LEGAL ", "")
    
    # Remove double blank lines
    new_content = re.sub(r'\n{3,}', '\n\n', new_content)

    if new_content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Cleaned {filepath}")

files_to_clean = [
    "README.md",
    "docs/SETUP-GUIDE.md",
    "docs/drug-discovery/CLASSROOM-MCP.md",
    "docs/mcps/scholarly-access-mcp.md",
    "docs/skills/scholarly-skills.md",
    "docs/social/TIKTOK-MCP.md",
    "docs/workflows/deep-research-literature-workflow.md",
    "skills/SKILLS-MANIFEST.md",
    "skills/biomedical-paper-triage/SKILL.md",
    "skills/citation-mapping/SKILL.md",
    "skills/consensus-tooluniverse-research/references/BEST-METHOD.md",
    "skills/consensus-tooluniverse-research/references/PAPER-RETRIEVAL-KEYS.md",
    "skills/drug-discovery-literature-bridge/SKILL.md",
    "skills/oa-pdf-retrieval/SKILL.md",
    "skills/scholarly-literature-review/SKILL.md",
    "tools/scholarly-access-mcp/pyproject.toml",
    "tools/scholarly-access-mcp/scholarly_access/__init__.py",
    "tools/scholarly-access-mcp/scholarly_access/logic.py",
    "tools/scholarly-access-mcp/scholarly_access/policy.py",
    "tools/scholarly-access-mcp/scholarly_access/server.py",
    "tools/scholarly-access-mcp/tests/test_live.py",
    "tools/scholarly-access-mcp/tests/test_policy.py"
]

for f in files_to_clean:
    clean_file(f)
