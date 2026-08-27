# ATS rules (2026) — for the SUBMITTED CV

Applicant Tracking Systems (Workday, Greenhouse, Lever, Ashby, iCIMS, Taleo, SuccessFactors)
parse your PDF into a database, then let recruiters keyword-search it. Optimise for the *parser*
first, the human second. cv-studio's `ats` path already enforces the mechanics; this file is the
*content* discipline.

## Layout (RenderCV handles most of this)
- **Single column.** Multi-column layouts parse into interleaved garbage — the extractor reads
  left-to-right across both columns.
- **No** tables, text boxes, images, icons, skill-bars, headers/footers with contact info, or
  graphics. Icons parse as `&%$#` or drop the whole line.
- Real selectable text, embedded standard fonts (Arial/Times/Source Sans), 10-12pt. 1-2 pages.
- Tagged PDF (structure tree) — RenderCV/Typst emit PDF/UA-1 + PDF/A. Do not "print to image".

## Section order (cv-studio default)
`contact → summary → skills → experience → education → certifications → publications → awards →
languages`. Skills sit high so keyword-search hits them fast.

## The file
- **PDF**, not .docx or .txt, unless the posting *demands* .docx (some old Taleo installs). PDF
  preserves layout to the human and parses cleanly in every modern ATS.
- Name the file `First_Last_Resume.pdf`.
- URLs **visible as text** (`linkedin.com/in/name`, `github.com/name`) — never "click here".

## Keywords (the 3-place rule)
- A tailored resume scores materially higher. Read the job description; extract required
  skills/tools/titles (`cvstudio.py tailor` does the mechanical pass).
- Place each **truly-applicable** missing keyword in **three** spots: the **Skills** block, the
  relevant **job title line**, and a **proving bullet**. Use the JD's *exact* wording — ATS
  keyword search is often literal ("Kubernetes" ≠ "container orchestration").
- **2026 caveat:** Workday/Greenhouse/iCIMS now do semantic + skills-graph matching. **Keyword
  stuffing is actively penalised**, not merely useless. Add real signal in real sentences; never
  a keyword soup. If it isn't true, don't add it.

## Technical / RE / security profiles (content beats tooling)
- Name exact tools literally: "Ghidra, Frida, IDA Pro, Qiling" — not "RE tools".
- Link evidence, don't assert it: CVEs → Mitre/NVD/Exploit-DB; shipped tools → GitHub; talks/CTFs
  named. Public artifacts are treated as verifiable skill evidence.
- Quantify with the Brag-Document discipline (see `bullets.md`).

## The myth to ignore
"75% of resumes are auto-rejected by ATS bots" is folklore — ATS filter/rank, they rarely
auto-reject, and a human reviews the shortlist. Optimise for *findability + readability*, not
fear. (Framing from dabydat/resume-builder-skill, MIT.)

---
Sources (paraphrased, not vendored): resumeadapter.com/blog/ats-resume-formatting-rules-2026 ·
passthescan.com/blog/ats-resume-keywords-2026-complete-guide ·
docs.rendercv.com/ats_compatibility · shashiworks.com/ats-workday-greenhouse-taleo.html ·
resumeworded.com/skills-and-keywords/security-researcher-skills.
