import assert from "node:assert/strict";
import { test } from "node:test";

import { hasControlOrBidi, stripControlAndBidi } from "../dist/text.js";
import { asRecord, byteLength, matchGroup, withinRoot } from "../dist/util.js";
import {
  canonicalHostFor,
  canonicalUrl,
  immutablePermalink,
  normalizeLabel,
  normalizeOrigin,
  repositoryFor,
} from "../dist/provenance.js";
import {
  ERROR_CODES,
  boundedJson,
  buildFailure,
  toolError,
  toolOk,
} from "../dist/errors.js";
import {
  validateCategory,
  validateLimit,
  validatePath,
  validateQuery,
  validateSection,
  validateTopic,
} from "../dist/validation.js";
import {
  extractCodeBlocks,
  extractSection,
  firstH1,
  parseOutline,
  titleFor,
} from "../dist/markdown.js";
import { buildPageReceipt, buildSearchHit } from "../dist/citation.js";

const CTRL = String.fromCharCode(1);
const BIDI = String.fromCharCode(0x200e);
const FENCE = "```";

// --- text -------------------------------------------------------------------

test("hasControlOrBidi detects control, bidi, and clean", () => {
  assert.equal(hasControlOrBidi(`a${CTRL}b`), true);
  assert.equal(hasControlOrBidi(`a${BIDI}b`), true);
  assert.equal(hasControlOrBidi("clean text"), false);
});

test("stripControlAndBidi removes control+bidi but keeps normal chars", () => {
  assert.equal(stripControlAndBidi(`a${CTRL}b${BIDI}C`), "abC");
});

// --- util -------------------------------------------------------------------

test("byteLength counts utf8 bytes", () => {
  assert.equal(byteLength("ab"), 2);
  assert.equal(byteLength("\u00e9"), 2);
});

test("asRecord narrows objects only", () => {
  assert.deepEqual(asRecord({ a: 1 }), { a: 1 });
  assert.equal(asRecord("string"), null);
  assert.equal(asRecord(null), null);
});

test("matchGroup returns present group and empty for a missing optional group", () => {
  const present = /(x)/.exec("x");
  assert.equal(matchGroup(present, 1), "x");
  const missing = /(a)?b/.exec("b");
  assert.equal(matchGroup(missing, 1), "");
});

test("withinRoot handles equal, nested, non-nested and backslashes", () => {
  assert.equal(withinRoot("/a", "/a"), true);
  assert.equal(withinRoot("/a", "/a/b"), true);
  assert.equal(withinRoot("/a", "/ab"), false);
  assert.equal(withinRoot("C:\\a", "C:\\a\\b"), true);
});

// --- provenance -------------------------------------------------------------

test("normalizeOrigin strips .git and trailing slash", () => {
  assert.equal(
    normalizeOrigin("https://github.com/HackTricks-wiki/hacktricks.git"),
    "https://github.com/hacktricks-wiki/hacktricks",
  );
  assert.equal(
    normalizeOrigin("https://github.com/HackTricks-wiki/hacktricks/"),
    "https://github.com/hacktricks-wiki/hacktricks",
  );
  assert.equal(
    normalizeOrigin("https://github.com/HackTricks-wiki/hacktricks"),
    "https://github.com/hacktricks-wiki/hacktricks",
  );
});

test("repositoryFor and canonicalHostFor pick the right book", () => {
  assert.match(repositoryFor("main"), /\/hacktricks$/);
  assert.match(repositoryFor("cloud"), /hacktricks-cloud$/);
  assert.equal(canonicalHostFor("main"), "hacktricks.wiki");
  assert.equal(canonicalHostFor("cloud"), "cloud.hacktricks.wiki");
});

test("canonicalUrl maps README, nested and leaf pages, and encodes segments", () => {
  assert.equal(canonicalUrl("main", "src/README.md"), "https://hacktricks.wiki/en/index.html");
  assert.equal(
    canonicalUrl("main", "src/a/b/README.md"),
    "https://hacktricks.wiki/en/a/b/index.html",
  );
  assert.equal(canonicalUrl("main", "src/a/b.md"), "https://hacktricks.wiki/en/a/b.html");
  assert.equal(canonicalUrl("cloud", "src/x.md"), "https://cloud.hacktricks.wiki/en/x.html");
  assert.equal(
    canonicalUrl("main", "src/a b/c.md"),
    "https://hacktricks.wiki/en/a%20b/c.html",
  );
});

test("immutablePermalink builds a blob URL per book", () => {
  assert.equal(
    immutablePermalink("main", "f".repeat(40), "src/a.md"),
    `https://github.com/HackTricks-wiki/hacktricks/blob/${"f".repeat(40)}/src/a.md`,
  );
  assert.match(immutablePermalink("cloud", "0".repeat(40), "src/a.md"), /hacktricks-cloud\/blob\//);
});

test("normalizeLabel strips controls/bidi, escapes markdown, collapses ws, truncates", () => {
  assert.equal(normalizeLabel(`A${CTRL}${BIDI}B`), "AB");
  assert.equal(normalizeLabel("a*b_c`d"), "a\\*b\\_c\\`d");
  assert.equal(normalizeLabel("a   b   c"), "a b c");
  assert.equal(normalizeLabel("x".repeat(200)).length, 160);
});

// --- errors -----------------------------------------------------------------

test("ERROR_CODES is the documented set", () => {
  assert.ok(ERROR_CODES.includes("no_match"));
  assert.ok(ERROR_CODES.includes("provenance_mismatch"));
});

test("buildFailure assembles the envelope", () => {
  const f = buildFailure("op", "rid", 5, "query_invalid", "bad", "field", false, 1);
  assert.equal(f.ok, false);
  assert.equal(f.error.code, "query_invalid");
  assert.equal(f.error.subcode, "field");
  assert.equal(f.receipt.operation, "op");
});

test("boundedJson slices only when over the byte bound", () => {
  const short = boundedJson({ a: 1 }, 1000);
  assert.equal(short, JSON.stringify({ a: 1 }));
  const long = boundedJson({ a: "x".repeat(50) }, 10);
  assert.equal(long.length, 10);
});

test("toolError and toolOk build CallToolResults", () => {
  const err = toolError(buildFailure("op", "r", 0, "no_match", "m", null, false, 1));
  assert.equal(err.isError, true);
  assert.equal(err.content[0].type, "text");
  assert.equal(err.structuredContent.ok, false);
  const ok = toolOk({ ok: true, data: {} });
  assert.equal(ok.isError, undefined);
  assert.equal(ok.structuredContent.ok, true);
});

// --- validation -------------------------------------------------------------

test("validateQuery accepts and rejects", () => {
  assert.equal(validateQuery("ssrf").ok, true);
  assert.equal(validateQuery(5).ok, false);
  assert.equal(validateQuery(`a${CTRL}`).ok, false);
  assert.equal(validateQuery("   ").ok, false);
  assert.equal(validateQuery("x".repeat(513)).ok, false);
});

test("validateTopic and validateSection reuse the bounded validator", () => {
  assert.equal(validateTopic("privesc").ok, true);
  assert.equal(validateSection("Attack").ok, true);
  assert.equal(validateSection("x".repeat(513)).ok, false);
});

test("validatePath enforces every rule", () => {
  assert.equal(validatePath(5).ok, false);
  assert.equal(validatePath("").ok, false);
  assert.equal(validatePath(`src/${"x".repeat(1100)}.md`).ok, false);
  assert.equal(validatePath(`src/a${CTRL}.md`).ok, false);
  assert.equal(validatePath("src\\a.md").ok, false);
  assert.equal(validatePath("/etc/passwd.md").ok, false);
  assert.equal(validatePath("C:/a.md").ok, false);
  assert.equal(validatePath("http://x/a.md").ok, false);
  assert.equal(validatePath("src/%2e%2e/a.md").ok, false);
  assert.equal(validatePath("src/../a.md").ok, false);
  assert.equal(validatePath("src//a.md").ok, false);
  assert.equal(validatePath("docs/a.md").ok, false);
  assert.equal(validatePath("src/a.txt").ok, false);
  const good = validatePath("src/pentesting-web/ssrf.md");
  assert.equal(good.ok, true);
});

test("validateCategory checks type, emptiness, controls and allowlist", () => {
  const allow = ["pentesting-web", "linux-hardening"];
  assert.equal(validateCategory(5, allow).ok, false);
  assert.equal(validateCategory("", allow).ok, false);
  assert.equal(validateCategory(`a${CTRL}`, allow).ok, false);
  assert.equal(validateCategory("unknown", allow).ok, false);
  assert.equal(validateCategory("pentesting-web", allow).ok, true);
});

test("validateLimit defaults, rejects and clamps", () => {
  assert.deepEqual(validateLimit(undefined), { ok: true, value: 20 });
  assert.equal(validateLimit("5").ok, false);
  assert.equal(validateLimit(2.5).ok, false);
  assert.equal(validateLimit(0).ok, false);
  assert.deepEqual(validateLimit(60), { ok: true, value: 50 });
  assert.deepEqual(validateLimit(5), { ok: true, value: 5 });
});

// --- markdown ---------------------------------------------------------------

const OUTLINE_DOC = [
  "# H1",
  "## H2",
  FENCE,
  "# fenced heading not counted",
  FENCE,
  "####### too many hashes",
  "#nospace",
  "plain line",
  "### H3",
].join("\n");

test("parseOutline honors fences, hash count and required space", () => {
  const headings = parseOutline(OUTLINE_DOC);
  assert.deepEqual(
    headings.map((h) => `${h.level}:${h.text}`),
    ["1:H1", "2:H2", "3:H3"],
  );
});

test("firstH1 and titleFor", () => {
  assert.equal(firstH1("## only h2\n# real h1"), "real h1");
  assert.equal(firstH1("## no h1 here"), null);
  assert.equal(titleFor("# Page Title\ntext", "fallback"), "Page Title");
  assert.equal(titleFor("no heading", "fallback"), "fallback");
});

const SECTION_DOC = [
  "# T",
  "## Intro",
  "i",
  "## Attack",
  "a1",
  "### Detail",
  "d",
  "## Defense",
  "def",
].join("\n");

test("extractSection returns first match through the next equal/higher heading", () => {
  const hit = extractSection(SECTION_DOC, "attack");
  assert.equal(hit.returnedHeading, "Attack");
  assert.equal(hit.requestedHeading, "attack");
  assert.equal(hit.matchCount, 1);
  assert.ok(hit.content.includes("### Detail"));
  assert.ok(!hit.content.includes("## Defense"));
});

test("extractSection handles the last section (no following heading)", () => {
  const hit = extractSection(SECTION_DOC, "defense");
  assert.equal(hit.returnedHeading, "Defense");
  assert.ok(hit.content.includes("def"));
});

test("extractSection returns null when nothing matches", () => {
  assert.equal(extractSection(SECTION_DOC, "nonexistent"), null);
});

test("extractSection reports ambiguity via matchCount", () => {
  const doc = "## Attack\na\n## Attack Two\nb";
  const hit = extractSection(doc, "attack");
  assert.equal(hit.matchCount, 2);
  assert.equal(hit.returnedHeading, "Attack");
});

const CODE_DOC = [
  "intro",
  FENCE + "bash",
  "id",
  FENCE,
  "middle",
  FENCE,
  "whoami",
  FENCE,
  "tail",
  FENCE,
  "unterminated block",
].join("\n");

test("extractCodeBlocks returns terminated blocks, discards an open fence, honors max", () => {
  const all = extractCodeBlocks(CODE_DOC, Number.MAX_SAFE_INTEGER);
  assert.equal(all.length, 2);
  assert.ok(all[0].includes("id"));
  assert.ok(all[1].includes("whoami"));
  const capped = extractCodeBlocks(CODE_DOC, 1);
  assert.equal(capped.length, 1);
});

// --- citation ---------------------------------------------------------------

test("buildSearchHit normalizes labels and constructs the URL", () => {
  const hit = buildSearchHit({
    book: "main",
    path: "src/a.md",
    title: "Title*",
    heading: "Head",
    line: 12,
    snippet: "snip",
    revision: "a".repeat(40),
    sourceBlob: "b".repeat(40),
  });
  assert.equal(hit.title, "Title\\*");
  assert.equal(hit.canonical_url, "https://hacktricks.wiki/en/a.html");
  assert.equal(hit.line, 12);
});

test("buildPageReceipt handles both null and present headings", () => {
  const withHeadings = buildPageReceipt({
    book: "main",
    path: "src/a.md",
    content: "# Title\nbody",
    requestedHeading: "req",
    returnedHeading: "ret",
    revision: "a".repeat(40),
    sourceBlob: null,
    corpusCommittedAt: "2026-01-01T00:00:00Z",
    retrievedAt: "2026-01-02T00:00:00Z",
    truncated: false,
  });
  assert.equal(withHeadings.requested_heading, "req");
  assert.equal(withHeadings.returned_heading, "ret");
  assert.equal(withHeadings.title, "Title");
  assert.equal(withHeadings.content_bytes, byteLength("# Title\nbody"));

  const noHeadings = buildPageReceipt({
    book: "cloud",
    path: "src/a.md",
    content: "body only",
    requestedHeading: null,
    returnedHeading: null,
    revision: "a".repeat(40),
    sourceBlob: "c".repeat(40),
    corpusCommittedAt: "2026-01-01T00:00:00Z",
    retrievedAt: "2026-01-02T00:00:00Z",
    truncated: true,
  });
  assert.equal(noHeadings.requested_heading, null);
  assert.equal(noHeadings.returned_heading, null);
  assert.equal(noHeadings.title, "src/a.md");
  assert.equal(noHeadings.truncated, true);
});
