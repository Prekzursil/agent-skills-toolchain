import assert from "node:assert/strict";
import { test } from "node:test";

import {
  createTools,
  expandTopic,
  finalizeOk,
  groupByPath,
  nearestHeading,
} from "../dist/tools.js";

const SSRF = [
  "# SSRF",
  "## Redirect to Gopher",
  "text a",
  "```",
  "curl gopher://x",
  "```",
  "## Detection",
  "det",
].join("\n");

const AMBIG = ["# Amb", "## Detection", "d1", "## Detection Extra", "d2"].join("\n");

const PAGES = {
  "/c/src/pentesting-web/ssrf.md": SSRF,
  "/c/src/windows/x.md": "# Win\n## Notes\nn",
  "/c/src/amb.md": AMBIG,
};

function baseCorpus() {
  return { ok: true, root: "/c", revision: "a".repeat(40), committedAt: "2026-01-01T00:00:00Z" };
}

function fsFromPages(pages, dirs = {}) {
  return {
    async pathExists() {
      return true;
    },
    async realpath(p) {
      return p;
    },
    async statFile(p) {
      const c = pages[p];
      if (c === undefined) {
        return null;
      }
      return { isDirectory: false, size: Buffer.byteLength(c) };
    },
    async readTextFile(p) {
      const c = pages[p];
      if (c === undefined) {
        throw new Error(`missing ${p}`);
      }
      return c;
    },
    async listDir(p) {
      return dirs[p] ?? [];
    },
  };
}

const THROW_FS = {
  async pathExists() {
    return true;
  },
  async realpath(p) {
    return p;
  },
  async statFile() {
    return { isDirectory: false, size: 10 };
  },
  async readTextFile() {
    throw new Error("boom");
  },
  async listDir() {
    return [];
  },
};

function rgExec(hits) {
  const stdout = hits
    .map((h) =>
      JSON.stringify({
        type: "match",
        data: { path: { text: h.path }, line_number: h.line, lines: { text: h.text } },
      }),
    )
    .join("\n");
  return async () => ({
    stdout,
    exitCode: hits.length > 0 ? 0 : 1,
    timedOut: false,
    bufferExceeded: false,
    spawnError: null,
  });
}
const RG_ERROR = async () => ({
  stdout: "",
  exitCode: null,
  timedOut: false,
  bufferExceeded: false,
  spawnError: "no rg",
});

const GIT_OK = async (_root, args) =>
  args[0] === "rev-parse"
    ? { ok: true, stdout: `${"b".repeat(40)}\n` }
    : { ok: true, stdout: "" };
const GIT_FAIL = async () => ({ ok: false, message: "x" });
const GIT_SHORT = async () => ({ ok: true, stdout: "short\n" });

function deps(over = {}) {
  return {
    corpus: over.corpus ?? baseCorpus(),
    exec: over.exec ?? rgExec([]),
    git: over.git ?? GIT_OK,
    fs: over.fs ?? fsFromPages(PAGES),
    now: over.now ?? (() => new Date("2026-01-02T00:00:00Z")),
    newId: over.newId ?? (() => "req-1"),
  };
}

function tools(over = {}) {
  return createTools(deps(over));
}

async function sc(promise) {
  const result = await promise;
  return { result, body: result.structuredContent };
}

// --- registry + helpers -----------------------------------------------------

test("createTools exposes exactly the seven tools", () => {
  const { handlers, defs } = tools();
  const names = Object.keys(handlers).sort();
  assert.equal(names.length, 7);
  assert.equal(defs.length, 7);
  assert.deepEqual(
    defs.map((d) => d.name).sort(),
    names,
  );
  for (const def of defs) {
    assert.equal(def.inputSchema.type, "object");
    assert.equal(def.outputSchema.type, "object");
  }
});

test("expandTopic expands aliases and passes through unknown topics", () => {
  assert.equal(expandTopic("SQLI"), "sql injection");
  assert.equal(expandTopic("weirdterm"), "weirdterm");
});

test("nearestHeading returns the nearest preceding heading or empty", () => {
  const headings = [
    { level: 1, text: "A", line: 1 },
    { level: 2, text: "B", line: 5 },
  ];
  assert.equal(nearestHeading(headings, 3), "A");
  assert.equal(nearestHeading(headings, 0), "");
});

test("groupByPath groups repeated paths and records the first hit", () => {
  const groups = groupByPath([
    { path: "src/a.md", line: 1, text: "x" },
    { path: "src/a.md", line: 4, text: "y" },
    { path: "src/b.md", line: 2, text: "z" },
  ]);
  assert.equal(groups.length, 2);
  assert.equal(groups[0].hits.length, 2);
  assert.equal(groups[0].first.line, 1);
});

test("finalizeOk returns ok within bounds and content_too_large when over", () => {
  const params = {
    operation: "op",
    requestId: "r",
    elapsedMs: 1,
    corpus: { root: "/c", revision: "a".repeat(40), committedAt: "t" },
    retrievedAt: "t2",
    data: { hello: "world" },
    warnings: [],
    truncated: false,
    maxBytes: 100000,
  };
  const ok = finalizeOk(params);
  assert.equal(ok.structuredContent.ok, true);
  assert.equal(ok.structuredContent.receipt.repository.length > 0, true);
  const over = finalizeOk({ ...params, maxBytes: 5 });
  assert.equal(over.structuredContent.ok, false);
  assert.equal(over.structuredContent.error.code, "content_too_large");
});

// --- guard ------------------------------------------------------------------

test("an unhealthy corpus fails every tool closed", async () => {
  const { handlers } = tools({
    corpus: {
      ok: false,
      code: "backend_unavailable",
      subcode: "corpus_missing",
      message: "corpus repository not found",
    },
  });
  const { body } = await sc(handlers.search_hacktricks({ query: "x" }));
  assert.equal(body.ok, false);
  assert.equal(body.error.code, "backend_unavailable");
  assert.equal(body.error.subcode, "corpus_missing");
});

test("an unexpected exception in a tool body becomes a structured error", async () => {
  const { handlers } = tools({ fs: THROW_FS });
  const { body } = await sc(handlers.get_hacktricks_page({ path: "src/pentesting-web/ssrf.md" }));
  assert.equal(body.ok, false);
  assert.equal(body.error.code, "retrieval_failed");
  assert.equal(body.error.subcode, "exception");
});

// --- search_hacktricks ------------------------------------------------------

test("search groups hits, enriches, and attaches provenance", async () => {
  const { handlers } = tools({
    exec: rgExec([
      { path: "src/pentesting-web/ssrf.md", line: 2, text: "Redirect" },
      { path: "src/pentesting-web/ssrf.md", line: 7, text: "Detection" },
      { path: "src/windows/x.md", line: 2, text: "Notes" },
    ]),
  });
  const { body } = await sc(handlers.search_hacktricks({ query: "ssrf" }));
  assert.equal(body.ok, true);
  assert.equal(body.data.match_count, 2);
  assert.equal(body.data.results[0].title, "SSRF");
  assert.equal(body.data.results[0].heading, "Redirect to Gopher");
  assert.equal(body.data.results[0].sampled_match_count, 2);
  assert.equal(body.data.results[0].source_blob, "b".repeat(40));
  assert.equal(body.data.results[0].canonical_url, "https://hacktricks.wiki/en/pentesting-web/ssrf.html");
});

test("search validates query, category and limit", async () => {
  const { handlers } = tools({
    exec: rgExec([{ path: "src/pentesting-web/ssrf.md", line: 2, text: "x" }]),
    fs: fsFromPages(PAGES, { "/c/src": [{ name: "pentesting-web", isDirectory: true }] }),
  });
  assert.equal((await sc(handlers.search_hacktricks({ query: 5 }))).body.error.code, "query_invalid");
  assert.equal(
    (await sc(handlers.search_hacktricks({ query: "x", category: "bogus" }))).body.error.code,
    "query_invalid",
  );
  assert.equal(
    (await sc(handlers.search_hacktricks({ query: "x", limit: "nope" }))).body.error.code,
    "query_invalid",
  );
  const okCat = await sc(handlers.search_hacktricks({ query: "x", category: "pentesting-web" }));
  assert.equal(okCat.body.data.category, "pentesting-web");
});

test("search reports backend errors and empty results", async () => {
  const err = await sc(tools({ exec: RG_ERROR }).handlers.search_hacktricks({ query: "x" }));
  assert.equal(err.body.error.code, "backend_unavailable");
  const empty = await sc(tools({ exec: rgExec([]) }).handlers.search_hacktricks({ query: "x" }));
  assert.equal(empty.body.data.results.length, 0);
  assert.deepEqual(empty.body.warnings, ["no matching pages"]);
});

test("search honors the limit and skips invalid returned paths", async () => {
  const limited = await sc(
    tools({
      exec: rgExec([
        { path: "src/pentesting-web/ssrf.md", line: 1, text: "a" },
        { path: "src/windows/x.md", line: 1, text: "b" },
        { path: "src/amb.md", line: 1, text: "c" },
      ]),
    }).handlers.search_hacktricks({ query: "x", limit: 2 }),
  );
  assert.equal(limited.body.data.results.length, 2);

  const skipped = await sc(
    tools({
      exec: rgExec([
        { path: "src/../evil.md", line: 1, text: "a" },
        { path: "src/ok.md", line: 1, text: "b" },
      ]),
    }).handlers.search_hacktricks({ query: "x" }),
  );
  assert.equal(skipped.body.data.results.length, 1);
  assert.equal(skipped.body.data.results[0].title, "src/ok.md");
});

// --- get_hacktricks_page ----------------------------------------------------

test("page returns a bounded receipt and handles bad/missing paths and blob failures", async () => {
  const okPage = await sc(
    tools().handlers.get_hacktricks_page({ path: "src/pentesting-web/ssrf.md" }),
  );
  assert.equal(okPage.body.ok, true);
  assert.equal(okPage.body.data.content, SSRF);
  assert.equal(okPage.body.data.source_blob, "b".repeat(40));
  assert.equal(okPage.body.data.title, "SSRF");

  assert.equal(
    (await sc(tools().handlers.get_hacktricks_page({ path: "/etc/passwd.md" }))).body.error.code,
    "query_invalid",
  );
  assert.equal(
    (await sc(tools().handlers.get_hacktricks_page({ path: "src/missing.md" }))).body.error.code,
    "retrieval_failed",
  );
  const noBlob = await sc(
    tools({ git: GIT_FAIL }).handlers.get_hacktricks_page({ path: "src/pentesting-web/ssrf.md" }),
  );
  assert.equal(noBlob.body.data.source_blob, null);
});

// --- get_hacktricks_outline -------------------------------------------------

test("outline returns headings and rejects a bad path", async () => {
  const ok = await sc(tools().handlers.get_hacktricks_outline({ path: "src/pentesting-web/ssrf.md" }));
  assert.equal(ok.body.data.outline[0].text, "SSRF");
  assert.equal(
    (await sc(tools().handlers.get_hacktricks_outline({ path: "bad" }))).body.error.code,
    "query_invalid",
  );
});

// --- get_hacktricks_section -------------------------------------------------

test("section returns the matched section with provenance", async () => {
  const ok = await sc(
    tools({ git: GIT_SHORT }).handlers.get_hacktricks_section({
      path: "src/pentesting-web/ssrf.md",
      section: "redirect",
    }),
  );
  assert.equal(ok.body.data.returned_heading, "Redirect to Gopher");
  assert.equal(ok.body.data.source_blob, null); // GIT_SHORT is not a 40-hex sha
  assert.ok(ok.body.data.content.includes("curl gopher"));
  assert.deepEqual(ok.body.warnings, []);
});

test("section validates its inputs, reports no_match and ambiguity", async () => {
  assert.equal(
    (await sc(tools().handlers.get_hacktricks_section({ path: "src/a.md", section: 5 }))).body.error
      .code,
    "query_invalid",
  );
  assert.equal(
    (await sc(tools().handlers.get_hacktricks_section({ path: "bad", section: "x" }))).body.error
      .code,
    "query_invalid",
  );
  assert.equal(
    (
      await sc(
        tools().handlers.get_hacktricks_section({
          path: "src/pentesting-web/ssrf.md",
          section: "zzz",
        }),
      )
    ).body.error.code,
    "no_match",
  );
  const ambiguous = await sc(
    tools().handlers.get_hacktricks_section({ path: "src/amb.md", section: "detection" }),
  );
  assert.equal(ambiguous.body.data.returned_heading, "Detection");
  assert.match(ambiguous.body.warnings[0], /2 headings matched/);
});

// --- get_hacktricks_cheatsheet ----------------------------------------------

test("cheatsheet returns code blocks and rejects a bad path", async () => {
  const ok = await sc(
    tools().handlers.get_hacktricks_cheatsheet({ path: "src/pentesting-web/ssrf.md" }),
  );
  assert.equal(ok.body.data.blocks.length, 1);
  assert.ok(ok.body.data.blocks[0].includes("curl gopher"));
  assert.equal(
    (await sc(tools().handlers.get_hacktricks_cheatsheet({ path: "bad" }))).body.error.code,
    "query_invalid",
  );
});

// --- list_hacktricks_categories ---------------------------------------------

test("categories lists top level, a bounded tree, and rejects unknown", async () => {
  const topFs = fsFromPages(PAGES, {
    "/c/src": [
      { name: "windows-hardening", isDirectory: true },
      { name: "readme.md", isDirectory: false },
      { name: "pentesting-web", isDirectory: true },
    ],
  });
  const top = await sc(tools({ fs: topFs }).handlers.list_hacktricks_categories({}));
  assert.deepEqual(top.body.data.categories, ["pentesting-web", "windows-hardening"]);

  const treeFs = fsFromPages(PAGES, {
    "/c/src": [{ name: "pentesting-web", isDirectory: true }],
    "/c/src/pentesting-web": [{ name: "sub", isDirectory: true }],
  });
  const tree = await sc(
    tools({ fs: treeFs }).handlers.list_hacktricks_categories({ category: "pentesting-web" }),
  );
  assert.equal(tree.body.data.category, "pentesting-web");
  assert.equal(tree.body.data.tree[0].name, "sub");

  const bad = await sc(
    tools({ fs: topFs }).handlers.list_hacktricks_categories({ category: "nope" }),
  );
  assert.equal(bad.body.error.code, "query_invalid");
});

// --- hacktricks_quick_lookup ------------------------------------------------

test("quick_lookup returns a candidate page with bounded code blocks", async () => {
  const ok = await sc(
    tools({
      exec: rgExec([{ path: "src/pentesting-web/ssrf.md", line: 2, text: "Redirect" }]),
    }).handlers.hacktricks_quick_lookup({ topic: "ssrf" }),
  );
  assert.equal(ok.body.data.candidate.path, "src/pentesting-web/ssrf.md");
  assert.equal(ok.body.data.candidate.title, "SSRF");
  assert.equal(ok.body.data.blocks.length, 1);
});

test("quick_lookup validates inputs and handles category, backend and empty results", async () => {
  assert.equal(
    (await sc(tools().handlers.hacktricks_quick_lookup({ topic: 5 }))).body.error.code,
    "query_invalid",
  );
  const catFs = fsFromPages(PAGES, { "/c/src": [{ name: "pentesting-web", isDirectory: true }] });
  const okCat = await sc(
    tools({
      fs: catFs,
      exec: rgExec([{ path: "src/pentesting-web/ssrf.md", line: 2, text: "R" }]),
    }).handlers.hacktricks_quick_lookup({ topic: "ssrf", category: "pentesting-web" }),
  );
  assert.equal(okCat.body.data.candidate.path, "src/pentesting-web/ssrf.md");
  assert.equal(
    (
      await sc(
        tools({ fs: catFs }).handlers.hacktricks_quick_lookup({ topic: "ssrf", category: "nope" }),
      )
    ).body.error.code,
    "query_invalid",
  );
  assert.equal(
    (await sc(tools({ exec: RG_ERROR }).handlers.hacktricks_quick_lookup({ topic: "ssrf" }))).body
      .error.code,
    "backend_unavailable",
  );
  const empty = await sc(
    tools({ exec: rgExec([]) }).handlers.hacktricks_quick_lookup({ topic: "ssrf" }),
  );
  assert.equal(empty.body.data.candidate, null);
});

test("quick_lookup tolerates a missing candidate page", async () => {
  const missing = await sc(
    tools({
      exec: rgExec([{ path: "src/gone.md", line: 1, text: "x" }]),
    }).handlers.hacktricks_quick_lookup({ topic: "ssrf" }),
  );
  assert.equal(missing.body.data.candidate.title, "src/gone.md");
  assert.deepEqual(missing.body.data.blocks, []);
});
