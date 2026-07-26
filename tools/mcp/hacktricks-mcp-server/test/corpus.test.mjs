import assert from "node:assert/strict";
import { test } from "node:test";

import {
  checkCorpusHealth,
  enumerateCategoryTree,
  listTopCategories,
  parseRgJson,
  readPage,
  runRipgrep,
} from "../dist/corpus.js";
import { PINNED_CORPUS_COMMIT } from "../dist/provenance.js";
import { MAX_FILE_BYTES } from "../dist/limits.js";

const ROOT = "/corpus";
const SRC = `${ROOT}/src`;
const SUMMARY = `${ROOT}/src/SUMMARY.md`;

function makeGit(overrides = {}) {
  return async (_root, args) => {
    let key = "other";
    if (args[0] === "remote") key = "origin";
    else if (args[0] === "rev-parse") key = "head";
    else if (args[0] === "status") key = "status";
    else if (args[0] === "show") key = "show";
    if (key in overrides) {
      return overrides[key];
    }
    if (key === "origin") {
      return { ok: true, stdout: "https://github.com/HackTricks-wiki/hacktricks.git\n" };
    }
    if (key === "head") {
      return { ok: true, stdout: `${PINNED_CORPUS_COMMIT}\n` };
    }
    if (key === "status") {
      return { ok: true, stdout: "" };
    }
    return { ok: true, stdout: "2026-01-01T00:00:00Z\n" };
  };
}

function makeFs(opts = {}) {
  return {
    async pathExists(p) {
      return (opts.exists ?? (() => true))(p);
    },
    async realpath(p) {
      return (opts.realpath ?? ((x) => x))(p);
    },
    async statFile(p) {
      return (opts.statFile ?? (() => ({ isDirectory: false, size: 10 })))(p);
    },
    async readTextFile(p) {
      return (opts.readText ?? (() => "content"))(p);
    },
    async listDir(p) {
      return (opts.listDir ?? (() => []))(p);
    },
  };
}

test("checkCorpusHealth passes for a clean pinned corpus", async () => {
  const status = await checkCorpusHealth(ROOT, makeGit(), makeFs());
  assert.equal(status.ok, true);
  assert.equal(status.revision, PINNED_CORPUS_COMMIT);
  assert.equal(status.committedAt, "2026-01-01T00:00:00Z");
});

test("checkCorpusHealth fails closed for each precondition", async () => {
  const missing = await checkCorpusHealth(ROOT, makeGit(), makeFs({ exists: (p) => p !== ROOT }));
  assert.equal(missing.subcode, "corpus_missing");

  const noSrc = await checkCorpusHealth(ROOT, makeGit(), makeFs({ exists: (p) => p === ROOT }));
  assert.equal(noSrc.subcode, "corpus_src_missing");

  const noSummary = await checkCorpusHealth(
    ROOT,
    makeGit(),
    makeFs({ exists: (p) => p !== SUMMARY }),
  );
  assert.equal(noSummary.subcode, "summary_missing");

  const originFail = await checkCorpusHealth(
    ROOT,
    makeGit({ origin: { ok: false, message: "x" } }),
    makeFs(),
  );
  assert.equal(originFail.subcode, "git_error");

  const originBad = await checkCorpusHealth(
    ROOT,
    makeGit({ origin: { ok: true, stdout: "https://github.com/evil/repo\n" } }),
    makeFs(),
  );
  assert.equal(originBad.subcode, "origin_mismatch");

  const headFail = await checkCorpusHealth(
    ROOT,
    makeGit({ head: { ok: false, message: "x" } }),
    makeFs(),
  );
  assert.equal(headFail.subcode, "git_error");

  const headBad = await checkCorpusHealth(
    ROOT,
    makeGit({ head: { ok: true, stdout: "deadbeef\n" } }),
    makeFs(),
  );
  assert.equal(headBad.subcode, "revision_mismatch");

  const statusFail = await checkCorpusHealth(
    ROOT,
    makeGit({ status: { ok: false, message: "x" } }),
    makeFs(),
  );
  assert.equal(statusFail.subcode, "git_error");

  const dirty = await checkCorpusHealth(
    ROOT,
    makeGit({ status: { ok: true, stdout: " M src/x.md\n" } }),
    makeFs(),
  );
  assert.equal(dirty.subcode, "dirty_tree");

  const showFail = await checkCorpusHealth(
    ROOT,
    makeGit({ show: { ok: false, message: "x" } }),
    makeFs(),
  );
  assert.equal(showFail.subcode, "git_error");

  const escape = await checkCorpusHealth(
    ROOT,
    makeGit(),
    makeFs({ realpath: (p) => (p === SRC ? "/elsewhere/src" : p) }),
  );
  assert.equal(escape.subcode, "src_escape");
});

test("parseRgJson keeps only well-formed match records", () => {
  const lines = [
    "",
    "{bad json",
    "123",
    '{"type":"begin"}',
    '{"type":"match","data":123}',
    '{"type":"match","data":{"path":"x","line_number":1,"lines":{"text":"t"}}}',
    '{"type":"match","data":{"path":{"text":"src/b.md"},"lines":{"text":"t"}}}',
    '{"type":"match","data":{"path":{"text":"src/a.md"},"line_number":3,"lines":{"text":"hello\\n"}}}',
    '{"type":"match","data":{"path":{"text":"src/c.md"},"line_number":5}}',
  ].join("\n");
  const hits = parseRgJson(lines);
  assert.deepEqual(hits, [
    { path: "src/a.md", line: 3, text: "hello" },
    { path: "src/c.md", line: 5, text: "" },
  ]);
});

function makeExec(outcome, capture) {
  return async (file, args, opts) => {
    if (capture) {
      capture.file = file;
      capture.args = args;
      capture.opts = opts;
    }
    return {
      stdout: "",
      exitCode: 0,
      timedOut: false,
      bufferExceeded: false,
      spawnError: null,
      ...outcome,
    };
  };
}

test("runRipgrep maps failures and parses success", async () => {
  const capture = {};
  const spawn = await runRipgrep("q", "src", ROOT, makeExec({ spawnError: "no rg" }, capture));
  assert.equal(spawn.subcode, "rg_unavailable");
  assert.deepEqual(capture.args.slice(0, 4), ["--json", "-n", "-i", "--type"]);
  assert.equal(capture.opts.cwd, ROOT);

  const timeout = await runRipgrep("q", "src", ROOT, makeExec({ timedOut: true }));
  assert.equal(timeout.subcode, "rg_timeout");

  const buffer = await runRipgrep("q", "src", ROOT, makeExec({ bufferExceeded: true }));
  assert.equal(buffer.subcode, "rg_buffer_exceeded");

  const failed = await runRipgrep("q", "src", ROOT, makeExec({ exitCode: 2 }));
  assert.equal(failed.subcode, "rg_failed");

  const noMatch = await runRipgrep("q", "src", ROOT, makeExec({ exitCode: 1 }));
  assert.equal(noMatch.ok, true);
  assert.deepEqual(noMatch.hits, []);

  const matched = await runRipgrep(
    "q",
    "src",
    ROOT,
    makeExec({
      exitCode: 0,
      stdout: '{"type":"match","data":{"path":{"text":"src/a.md"},"line_number":1,"lines":{"text":"m"}}}',
    }),
  );
  assert.equal(matched.ok, true);
  assert.equal(matched.hits.length, 1);
});

test("readPage enforces existence, type, bounds and containment", async () => {
  const notFound = await readPage(ROOT, "src/a.md", makeFs({ statFile: () => null }));
  assert.equal(notFound.code, "retrieval_failed");

  const dir = await readPage(
    ROOT,
    "src/a.md",
    makeFs({ statFile: () => ({ isDirectory: true, size: 1 }) }),
  );
  assert.equal(dir.code, "retrieval_failed");

  const big = await readPage(
    ROOT,
    "src/a.md",
    makeFs({ statFile: () => ({ isDirectory: false, size: MAX_FILE_BYTES + 1 }) }),
  );
  assert.equal(big.code, "content_too_large");

  const escape = await readPage(
    ROOT,
    "src/a.md",
    makeFs({ realpath: (p) => (p === ROOT ? ROOT : "/elsewhere/a.md") }),
  );
  assert.equal(escape.code, "query_invalid");

  const bigContent = await readPage(
    ROOT,
    "src/a.md",
    makeFs({ readText: () => "x".repeat(MAX_FILE_BYTES + 1) }),
  );
  assert.equal(bigContent.code, "content_too_large");

  const ok = await readPage(ROOT, "src/a.md", makeFs({ readText: () => "hello" }));
  assert.equal(ok.ok, true);
  assert.equal(ok.content, "hello");
  assert.equal(ok.absolutePath, `${ROOT}/src/a.md`);
});

test("listTopCategories returns sorted directory names only", async () => {
  const cats = await listTopCategories(
    ROOT,
    makeFs({
      listDir: () => [
        { name: "windows-hardening", isDirectory: true },
        { name: "readme.md", isDirectory: false },
        { name: "pentesting-web", isDirectory: true },
      ],
    }),
  );
  assert.deepEqual(cats, ["pentesting-web", "windows-hardening"]);
});

test("enumerateCategoryTree walks to depth and honors the node cap", async () => {
  const tree = await enumerateCategoryTree(
    ROOT,
    makeFs({
      listDir: (p) => {
        if (p === `${ROOT}/src/cat`) {
          return [
            { name: "sub1", isDirectory: true },
            { name: "file.md", isDirectory: false },
          ];
        }
        if (p === `${ROOT}/src/cat/sub1`) {
          return [{ name: "deep", isDirectory: true }];
        }
        return [{ name: "tooDeep", isDirectory: true }];
      },
    }),
    "cat",
    2,
    2000,
  );
  assert.equal(tree.truncated, false);
  assert.equal(tree.tree.length, 1);
  assert.equal(tree.tree[0].name, "sub1");
  assert.equal(tree.tree[0].path, "sub1");
  assert.equal(tree.tree[0].children[0].name, "deep");
  assert.equal(tree.tree[0].children[0].path, "sub1/deep");
  assert.deepEqual(tree.tree[0].children[0].children, []);

  const capped = await enumerateCategoryTree(
    ROOT,
    makeFs({
      listDir: () => [
        { name: "a", isDirectory: true },
        { name: "b", isDirectory: true },
      ],
    }),
    "cat",
    3,
    1,
  );
  assert.equal(capped.truncated, true);
  assert.equal(capped.tree.length, 1);
});
