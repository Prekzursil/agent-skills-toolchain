"""Curated dev-intent -> skill table (precision patch for the handful of high-frequency
paraphrases that body-embeddings provably fumble).

The semantic lane handles broad recall across ~360 units, but a 137M embedding model on a
short prompt mis-ranks a few ultra-common engineering intents: "the app crashes" pulls in
deploy/platform skills on the word "app" (systematic-debugging sinks to rank ~23), and
"confusing cluttered UI" leaves make-interfaces-feel-better just under the similarity floor.
These ~8 regex rules surface the right skill with high precision and are MERGED ahead of the
semantic suggestions. Kept intentionally small — this complements embeddings, it does not
replace them (that was the old lexical router). Every name here is verified to exist in
~/.agents/skills; assemble() additionally drops any that are missing from the live index.

Data-only, pure regex, no I/O.
"""

import re

_RAW = [
    # symptom-language bug reports (embeddings miss "crash/broken/hangs" -> debugging)
    (
        r"\b(crash(e[sd]|ing)?|segfault|stack ?trace|traceback|throw(s|n|ing)?|exception|"
        r"null ?pointer|undefined is not|errors? (out|when)|broken|does(n'?t| not) work|"
        r"not working|stopped working|unexpected (behavio|result|output)|freezes?|hangs?|"
        r"infinite loop|wrong (output|result|answer)|fails? (when|with|on|to)|\bregression\b)",
        ["systematic-debugging"],
    ),
    # performance
    (
        r"\b((too|very|really|so) slow|slow(ness|er)?|laggy|\blag\b|speed (it|this|things) up|"
        r"optimi[sz]e (the |its )?(speed|performance|latency|runtime)|performance (issue|problem|"
        r"bottleneck)|make (it|this|.{1,20}) faster|runs? slow|high latency)\b",
        ["benchmark-optimization-loop", "parallel-execution-optimizer"],
    ),
    # UI/UX quality (NOT empty flashy frontends — usability + taste)
    (
        r"\b(confus(ing|ed)|cluttered|clunky|ugly|messy|dated|hard to (use|read|navigate|find)|"
        r"bad (ui|ux|layout|design)|improve (the )?(ui|ux|interface|design|usability)|polish (the )?"
        r"(ui|ux|interface)|too many buttons|user experience|feels? (off|clunky|cheap)|"
        r"looks? (bad|off|dated|cheap))\b",
        ["make-interfaces-feel-better", "ui-ux-pro-max", "design-system"],
    ),
    # flaky tests
    (
        r"\b(flak[ey]+|intermittent(ly)?|sometimes fail|randomly fail|test (fails|failing) "
        r"(sometimes|randomly|intermittently)|non[- ]?deterministic test)\b",
        ["systematic-debugging", "ai-regression-testing"],
    ),
    # TDD
    (
        r"\b(write (the )?tests? first|test[- ]driven|\btdd\b|red[- ]green[- ]refactor|"
        r"tests? before (the )?(code|implementation))\b",
        ["test-driven-development", "tdd-workflow"],
    ),
    # security
    (
        r"\b(security (review|audit|vuln|issue|hole)|vulnerab|sql ?injection|\bxss\b|\bcsrf\b|"
        r"hardcoded (secret|password|key|token)|\bowasp\b|insecure|exploit(able)?)\b",
        ["security-review", "security-best-practices"],
    ),
    # planning / decomposition
    (
        r"\b(plan (this|the|a|out) (feature|build|project|work)|implementation plan|roadmap|"
        r"break (this|it|the work) (down|into)|construction plan|multi[- ](step|session|pr) plan)\b",
        ["writing-plans", "blueprint"],
    ),
    # accessibility
    (
        r"\b(accessibilit|\ba11y\b|screen ?reader|wcag|color ?contrast|keyboard nav|aria\b)\b",
        ["frontend-a11y"],
    ),
]

_RULES = [(re.compile(rx, re.IGNORECASE), skills) for rx, skills in _RAW]

# Deliberation shapes (decision-shaped prompts -> the right deliberation skill/command). Owned
# here now that the semantic router supersedes the lexical one; mirrors the lexical router's
# _DECISION_SHAPES so that high-precision lane is preserved without exec-importing route.py.
_DELIB_RAW = [
    (
        r"\b(go[ -]?no[ -]?go|should (we|i) (use|pick|choose|go with|adopt)|which (approach|option|"
        r"one|way|design)|worth (it|doing|the)|trade[ -]?offs?|decide between|pros and cons|"
        r"either .{1,40}\bor\b)",
        "/council (structured go/no-go + tradeoffs)",
    ),
    (
        r"\b(stress[ -]?test|grill me|poke holes|what could go wrong|red[ -]?team|am i missing|"
        r"suggest more|what else (should|could)|find (the )?flaws)\b",
        "/grill-me-extensive (adversarial stress-test + expansion)",
    ),
    (
        r"\b(multi[ -]?(pr|session|step|phase)|roadmap|break (this|it) (down|into)|construction plan|"
        r"implementation plan for|step[ -]?by[ -]?step plan)\b",
        "/blueprint (multi-session construction plan)",
    ),
    (
        r"\b(brainstorm|ideate|generate (ideas|options|approaches)|explore (options|directions|"
        r"approaches)|what are (the|some) ways)\b",
        "/brainstorm (divergent ideation)",
    ),
    (
        r"\b(ambiguous|unclear (what|which|how|whether)|not sure what you (mean|want)|"
        r"clarify (the|my) (requirement|goal|scope))\b",
        "/clarify-requirements (pre-exec disambiguation)",
    ),
]
_DELIB = [(re.compile(rx, re.IGNORECASE), label) for rx, label in _DELIB_RAW]


def match(text):
    """Ordered, de-duplicated list of intent-matched skill names for `text`."""
    out, seen = [], set()
    for rx, skills in _RULES:
        if rx.search(text):
            for s in skills:
                if s not in seen:
                    seen.add(s)
                    out.append(s)
    return out


def match_delib(text):
    """Ordered deliberation labels for decision-shaped prompts."""
    out = []
    for rx, label in _DELIB:
        if rx.search(text) and label not in out:
            out.append(label)
    return out
