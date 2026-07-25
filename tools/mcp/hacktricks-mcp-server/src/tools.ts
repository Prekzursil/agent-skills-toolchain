// The seven read-only HackTricks tools. Every handler validates inputs before
// I/O, returns a canonical structured envelope with a bounded text projection,
// and converts every failure into a structured tool error (isError:true) with a
// stable reason code. All process/filesystem primitives are injected.

import type { CallToolResult, Tool } from "@modelcontextprotocol/sdk/types.js";
import { buildFailure, type ErrorCode, toolError, toolOk } from "./errors.js";
import {
  type CorpusStatus,
  type ExecFn,
  type GitFn,
  type CorpusFs,
  type RgHit,
  enumerateCategoryTree,
  listTopCategories,
  readPage,
  runRipgrep,
} from "./corpus.js";
import { buildPageReceipt, buildSearchHit } from "./citation.js";
import {
  extractCodeBlocks,
  extractSection,
  type Heading,
  parseOutline,
  titleFor,
} from "./markdown.js";
import { CORPUS_REPOSITORY_MAIN } from "./provenance.js";
import { byteLength } from "./util.js";
import {
  type Invalid,
  validateCategory,
  validateLimit,
  validatePath,
  validateQuery,
  validateSection,
  validateTopic,
} from "./validation.js";
import {
  MAX_CATEGORY_DEPTH,
  MAX_CATEGORY_TREE_NODES,
  MAX_CHEATSHEET_BYTES,
  MAX_FILE_BYTES,
  MAX_OUTLINE_BYTES,
  MAX_QUICK_LOOKUP_BLOCKS,
  MAX_QUICK_LOOKUP_BYTES,
  MAX_SECTION_BYTES,
  MAX_TOOL_RESPONSE_BYTES,
} from "./limits.js";

export interface ToolDeps {
  corpus: CorpusStatus;
  exec: ExecFn;
  git: GitFn;
  fs: CorpusFs;
  now: () => Date;
  newId: () => string;
}

export type ToolHandler = (args: Record<string, unknown>) => Promise<CallToolResult>;

interface OkCorpus {
  root: string;
  revision: string;
  committedAt: string;
}
interface Ctx {
  start: number;
  reqId: string;
  corpus: OkCorpus;
}

const ALIASES: Record<string, string> = {
  sqli: "sql injection",
  xss: "cross site scripting",
  rce: "remote code execution",
  lfi: "local file inclusion",
  rfi: "remote file inclusion",
  ssrf: "server side request forgery",
  csrf: "cross site request forgery",
  xxe: "xml external entity",
  ssti: "server side template injection",
  idor: "insecure direct object reference",
  jwt: "json web token",
  suid: "suid privilege escalation",
  privesc: "privilege escalation",
  deserialization: "insecure deserialization",
};

export function expandTopic(topic: string): string {
  const alias = ALIASES[topic.toLowerCase()];
  if (alias === undefined) {
    return topic;
  }
  return alias;
}

export function nearestHeading(headings: Heading[], line: number): string {
  let best = "";
  for (const heading of headings) {
    if (heading.line <= line) {
      best = heading.text;
    } else {
      break;
    }
  }
  return best;
}

interface Group {
  path: string;
  hits: RgHit[];
  first: RgHit;
}
export function groupByPath(hits: RgHit[]): Group[] {
  const map = new Map<string, Group>();
  for (const hit of hits) {
    const existing = map.get(hit.path);
    if (existing === undefined) {
      map.set(hit.path, { path: hit.path, hits: [hit], first: hit });
    } else {
      existing.hits.push(hit);
    }
  }
  return [...map.values()];
}

function elapsed(deps: ToolDeps, start: number): number {
  return deps.now().getTime() - start;
}

async function guarded(
  deps: ToolDeps,
  operation: string,
  body: (ctx: Ctx) => Promise<CallToolResult>,
): Promise<CallToolResult> {
  const start = deps.now().getTime();
  const reqId = deps.newId();
  const corpus = deps.corpus;
  if (!corpus.ok) {
    return toolError(
      buildFailure(
        operation,
        reqId,
        deps.now().getTime() - start,
        "backend_unavailable",
        corpus.message,
        corpus.subcode,
        true,
        1,
      ),
    );
  }
  try {
    return await body({ start, reqId, corpus });
  } catch {
    return toolError(
      buildFailure(
        operation,
        reqId,
        deps.now().getTime() - start,
        "retrieval_failed",
        "unexpected error during retrieval",
        "exception",
        false,
        1,
      ),
    );
  }
}

function invalidResult(
  deps: ToolDeps,
  ctx: Ctx,
  operation: string,
  inv: Invalid,
): CallToolResult {
  return toolError(
    buildFailure(
      operation,
      ctx.reqId,
      elapsed(deps, ctx.start),
      "query_invalid",
      `${inv.field}: ${inv.message}`,
      inv.field,
      false,
      1,
    ),
  );
}

function failResult(
  deps: ToolDeps,
  ctx: Ctx,
  operation: string,
  code: ErrorCode,
  message: string,
  subcode: string | null,
  retryable: boolean,
): CallToolResult {
  return toolError(
    buildFailure(
      operation,
      ctx.reqId,
      elapsed(deps, ctx.start),
      code,
      message,
      subcode,
      retryable,
      1,
    ),
  );
}

export function finalizeOk(params: {
  operation: string;
  requestId: string;
  elapsedMs: number;
  corpus: OkCorpus;
  retrievedAt: string;
  data: Record<string, unknown>;
  warnings: string[];
  truncated: boolean;
  maxBytes: number;
}): CallToolResult {
  const contentBytes = byteLength(JSON.stringify(params.data));
  const envelope = {
    ok: true,
    data: params.data,
    receipt: {
      operation: params.operation,
      request_id: params.requestId,
      repository: CORPUS_REPOSITORY_MAIN,
      revision: params.corpus.revision,
      corpus_committed_at: params.corpus.committedAt,
      retrieved_at: params.retrievedAt,
      elapsed_ms: params.elapsedMs,
      content_bytes: contentBytes,
      truncated: params.truncated,
    },
    warnings: params.warnings,
  };
  if (byteLength(JSON.stringify(envelope)) > params.maxBytes) {
    return toolError(
      buildFailure(
        params.operation,
        params.requestId,
        params.elapsedMs,
        "content_too_large",
        "response exceeds the byte bound",
        null,
        false,
        1,
      ),
    );
  }
  return toolOk(envelope as unknown as Record<string, unknown>);
}

async function blobSha(
  git: GitFn,
  root: string,
  relPath: string,
): Promise<string | null> {
  const res = await git(root, ["rev-parse", `HEAD:${relPath}`]);
  if (!res.ok) {
    return null;
  }
  const sha = res.stdout.trim();
  if (/^[0-9a-f]{40}$/.test(sha)) {
    return sha;
  }
  return null;
}

async function enrichHit(
  deps: ToolDeps,
  corpus: OkCorpus,
  group: Group,
): Promise<Record<string, unknown>> {
  const page = await readPage(corpus.root, group.path, deps.fs);
  let title = group.path;
  let heading = "";
  if (page.ok) {
    title = titleFor(page.content, group.path);
    heading = nearestHeading(parseOutline(page.content), group.first.line);
  }
  const sourceBlob = await blobSha(deps.git, corpus.root, group.path);
  const hit = buildSearchHit({
    book: "main",
    path: group.path,
    title,
    heading,
    line: group.first.line,
    snippet: group.first.text,
    revision: corpus.revision,
    sourceBlob,
  });
  return { ...hit, sampled_match_count: group.hits.length };
}

// --- individual tools -------------------------------------------------------

function searchTool(deps: ToolDeps): ToolHandler {
  return (args) =>
    guarded(deps, "search_hacktricks", async (ctx) => {
      const query = validateQuery(args["query"]);
      if (!query.ok) {
        return invalidResult(deps, ctx, "search_hacktricks", query);
      }
      let searchRoot = "src";
      let category: string | null = null;
      if (args["category"] !== undefined) {
        const cats = await listTopCategories(ctx.corpus.root, deps.fs);
        const cat = validateCategory(args["category"], cats);
        if (!cat.ok) {
          return invalidResult(deps, ctx, "search_hacktricks", cat);
        }
        category = cat.value;
        searchRoot = `src/${cat.value}`;
      }
      const limit = validateLimit(args["limit"]);
      if (!limit.ok) {
        return invalidResult(deps, ctx, "search_hacktricks", limit);
      }
      const rg = await runRipgrep(query.value, searchRoot, ctx.corpus.root, deps.exec);
      if (!rg.ok) {
        return failResult(deps, ctx, "search_hacktricks", rg.code, rg.message, rg.subcode, true);
      }
      const groups = groupByPath(rg.hits);
      const results: Record<string, unknown>[] = [];
      for (const group of groups) {
        if (results.length >= limit.value) {
          break;
        }
        if (!validatePath(group.path).ok) {
          continue;
        }
        results.push(await enrichHit(deps, ctx.corpus, group));
      }
      const warnings = results.length === 0 ? ["no matching pages"] : [];
      return finalizeOk({
        operation: "search_hacktricks",
        requestId: ctx.reqId,
        elapsedMs: elapsed(deps, ctx.start),
        corpus: ctx.corpus,
        retrievedAt: deps.now().toISOString(),
        data: { query: query.value, category, match_count: groups.length, results },
        warnings,
        truncated: false,
        maxBytes: MAX_TOOL_RESPONSE_BYTES,
      });
    });
}

async function readValidatedPage(
  deps: ToolDeps,
  ctx: Ctx,
  operation: string,
  rawPath: unknown,
): Promise<
  | { ok: true; path: string; content: string }
  | { ok: false; result: CallToolResult }
> {
  const path = validatePath(rawPath);
  if (!path.ok) {
    return { ok: false, result: invalidResult(deps, ctx, operation, path) };
  }
  const page = await readPage(ctx.corpus.root, path.value, deps.fs);
  if (!page.ok) {
    return {
      ok: false,
      result: failResult(deps, ctx, operation, page.code, page.message, null, false),
    };
  }
  return { ok: true, path: path.value, content: page.content };
}

function pageTool(deps: ToolDeps): ToolHandler {
  return (args) =>
    guarded(deps, "get_hacktricks_page", async (ctx) => {
      const read = await readValidatedPage(deps, ctx, "get_hacktricks_page", args["path"]);
      if (!read.ok) {
        return read.result;
      }
      const blob = await blobSha(deps.git, ctx.corpus.root, read.path);
      const receipt = buildPageReceipt({
        book: "main",
        path: read.path,
        content: read.content,
        requestedHeading: null,
        returnedHeading: null,
        revision: ctx.corpus.revision,
        sourceBlob: blob,
        corpusCommittedAt: ctx.corpus.committedAt,
        retrievedAt: deps.now().toISOString(),
        truncated: false,
      });
      return finalizeOk({
        operation: "get_hacktricks_page",
        requestId: ctx.reqId,
        elapsedMs: elapsed(deps, ctx.start),
        corpus: ctx.corpus,
        retrievedAt: receipt.retrieved_at,
        data: { ...receipt },
        warnings: [],
        truncated: false,
        maxBytes: MAX_FILE_BYTES,
      });
    });
}

function outlineTool(deps: ToolDeps): ToolHandler {
  return (args) =>
    guarded(deps, "get_hacktricks_outline", async (ctx) => {
      const read = await readValidatedPage(deps, ctx, "get_hacktricks_outline", args["path"]);
      if (!read.ok) {
        return read.result;
      }
      const outline = parseOutline(read.content).map((h) => ({
        level: h.level,
        text: h.text,
        line: h.line,
      }));
      return finalizeOk({
        operation: "get_hacktricks_outline",
        requestId: ctx.reqId,
        elapsedMs: elapsed(deps, ctx.start),
        corpus: ctx.corpus,
        retrievedAt: deps.now().toISOString(),
        data: { path: read.path, outline },
        warnings: [],
        truncated: false,
        maxBytes: MAX_OUTLINE_BYTES,
      });
    });
}

function sectionTool(deps: ToolDeps): ToolHandler {
  return (args) =>
    guarded(deps, "get_hacktricks_section", async (ctx) => {
      const section = validateSection(args["section"]);
      if (!section.ok) {
        return invalidResult(deps, ctx, "get_hacktricks_section", section);
      }
      const read = await readValidatedPage(deps, ctx, "get_hacktricks_section", args["path"]);
      if (!read.ok) {
        return read.result;
      }
      const hit = extractSection(read.content, section.value);
      if (hit === null) {
        return failResult(
          deps,
          ctx,
          "get_hacktricks_section",
          "no_match",
          "no heading matched the requested section",
          null,
          false,
        );
      }
      const blob = await blobSha(deps.git, ctx.corpus.root, read.path);
      const receipt = buildPageReceipt({
        book: "main",
        path: read.path,
        content: hit.content,
        requestedHeading: hit.requestedHeading,
        returnedHeading: hit.returnedHeading,
        revision: ctx.corpus.revision,
        sourceBlob: blob,
        corpusCommittedAt: ctx.corpus.committedAt,
        retrievedAt: deps.now().toISOString(),
        truncated: false,
      });
      const warnings =
        hit.matchCount > 1
          ? [`${hit.matchCount} headings matched; returned the first`]
          : [];
      return finalizeOk({
        operation: "get_hacktricks_section",
        requestId: ctx.reqId,
        elapsedMs: elapsed(deps, ctx.start),
        corpus: ctx.corpus,
        retrievedAt: receipt.retrieved_at,
        data: { ...receipt },
        warnings,
        truncated: false,
        maxBytes: MAX_SECTION_BYTES,
      });
    });
}

function cheatsheetTool(deps: ToolDeps): ToolHandler {
  return (args) =>
    guarded(deps, "get_hacktricks_cheatsheet", async (ctx) => {
      const read = await readValidatedPage(deps, ctx, "get_hacktricks_cheatsheet", args["path"]);
      if (!read.ok) {
        return read.result;
      }
      const blocks = extractCodeBlocks(read.content, Number.MAX_SAFE_INTEGER);
      return finalizeOk({
        operation: "get_hacktricks_cheatsheet",
        requestId: ctx.reqId,
        elapsedMs: elapsed(deps, ctx.start),
        corpus: ctx.corpus,
        retrievedAt: deps.now().toISOString(),
        data: {
          path: read.path,
          blocks,
          note: "discovery/convenience output; verify with the explanatory sections",
        },
        warnings: [],
        truncated: false,
        maxBytes: MAX_CHEATSHEET_BYTES,
      });
    });
}

function categoriesTool(deps: ToolDeps): ToolHandler {
  return (args) =>
    guarded(deps, "list_hacktricks_categories", async (ctx) => {
      const top = await listTopCategories(ctx.corpus.root, deps.fs);
      if (args["category"] === undefined) {
        return finalizeOk({
          operation: "list_hacktricks_categories",
          requestId: ctx.reqId,
          elapsedMs: elapsed(deps, ctx.start),
          corpus: ctx.corpus,
          retrievedAt: deps.now().toISOString(),
          data: { categories: top },
          warnings: [],
          truncated: false,
          maxBytes: MAX_TOOL_RESPONSE_BYTES,
        });
      }
      const cat = validateCategory(args["category"], top);
      if (!cat.ok) {
        return invalidResult(deps, ctx, "list_hacktricks_categories", cat);
      }
      const tree = await enumerateCategoryTree(
        ctx.corpus.root,
        deps.fs,
        cat.value,
        MAX_CATEGORY_DEPTH,
        MAX_CATEGORY_TREE_NODES,
      );
      return finalizeOk({
        operation: "list_hacktricks_categories",
        requestId: ctx.reqId,
        elapsedMs: elapsed(deps, ctx.start),
        corpus: ctx.corpus,
        retrievedAt: deps.now().toISOString(),
        data: { category: cat.value, tree: tree.tree },
        warnings: [],
        truncated: tree.truncated,
        maxBytes: MAX_TOOL_RESPONSE_BYTES,
      });
    });
}

function quickLookupTool(deps: ToolDeps): ToolHandler {
  return (args) =>
    guarded(deps, "hacktricks_quick_lookup", async (ctx) => {
      const topic = validateTopic(args["topic"]);
      if (!topic.ok) {
        return invalidResult(deps, ctx, "hacktricks_quick_lookup", topic);
      }
      let searchRoot = "src";
      if (args["category"] !== undefined) {
        const cats = await listTopCategories(ctx.corpus.root, deps.fs);
        const cat = validateCategory(args["category"], cats);
        if (!cat.ok) {
          return invalidResult(deps, ctx, "hacktricks_quick_lookup", cat);
        }
        searchRoot = `src/${cat.value}`;
      }
      const rg = await runRipgrep(expandTopic(topic.value), searchRoot, ctx.corpus.root, deps.exec);
      if (!rg.ok) {
        return failResult(deps, ctx, "hacktricks_quick_lookup", rg.code, rg.message, rg.subcode, true);
      }
      const groups = groupByPath(rg.hits);
      const best = groups[0];
      if (best === undefined) {
        return finalizeOk({
          operation: "hacktricks_quick_lookup",
          requestId: ctx.reqId,
          elapsedMs: elapsed(deps, ctx.start),
          corpus: ctx.corpus,
          retrievedAt: deps.now().toISOString(),
          data: { topic: topic.value, candidate: null, blocks: [] },
          warnings: ["no candidate page; candidate discovery only"],
          truncated: false,
          maxBytes: MAX_QUICK_LOOKUP_BYTES,
        });
      }
      const page = await readPage(ctx.corpus.root, best.path, deps.fs);
      let title = best.path;
      let blocks: string[] = [];
      if (page.ok) {
        title = titleFor(page.content, best.path);
        blocks = extractCodeBlocks(page.content, MAX_QUICK_LOOKUP_BLOCKS);
      }
      return finalizeOk({
        operation: "hacktricks_quick_lookup",
        requestId: ctx.reqId,
        elapsedMs: elapsed(deps, ctx.start),
        corpus: ctx.corpus,
        retrievedAt: deps.now().toISOString(),
        data: {
          topic: topic.value,
          candidate: { path: best.path, title, line: best.first.line },
          blocks,
          note: "candidate discovery only; verify with outline plus section or page",
        },
        warnings: [],
        truncated: false,
        maxBytes: MAX_QUICK_LOOKUP_BYTES,
      });
    });
}

// --- registry ---------------------------------------------------------------

const ENVELOPE_OUTPUT_SCHEMA: Tool["outputSchema"] = {
  type: "object",
  properties: {
    ok: { type: "boolean" },
    data: { type: "object" },
    receipt: { type: "object" },
    warnings: { type: "array" },
    error: { type: "object" },
  },
  required: ["ok"],
};

function objectSchema(
  properties: Record<string, object>,
  required: string[],
): Tool["inputSchema"] {
  return { type: "object", properties, required };
}

export function createTools(deps: ToolDeps): {
  handlers: Record<string, ToolHandler>;
  defs: Tool[];
} {
  const handlers: Record<string, ToolHandler> = {
    search_hacktricks: searchTool(deps),
    get_hacktricks_page: pageTool(deps),
    get_hacktricks_outline: outlineTool(deps),
    get_hacktricks_section: sectionTool(deps),
    get_hacktricks_cheatsheet: cheatsheetTool(deps),
    list_hacktricks_categories: categoriesTool(deps),
    hacktricks_quick_lookup: quickLookupTool(deps),
  };
  const readOnly = { readOnlyHint: true, openWorldHint: false };
  const defs: Tool[] = [
    {
      name: "search_hacktricks",
      description:
        "Case-insensitive ripgrep discovery over the pinned HackTricks main-book corpus, grouped by file.",
      inputSchema: objectSchema(
        {
          query: { type: "string" },
          category: { type: "string" },
          limit: { type: "number" },
        },
        ["query"],
      ),
      outputSchema: ENVELOPE_OUTPUT_SCHEMA,
      annotations: readOnly,
    },
    {
      name: "get_hacktricks_page",
      description: "Return a bounded complete Markdown page from the pinned corpus.",
      inputSchema: objectSchema({ path: { type: "string" } }, ["path"]),
      outputSchema: ENVELOPE_OUTPUT_SCHEMA,
      annotations: readOnly,
    },
    {
      name: "get_hacktricks_outline",
      description: "Return the Markdown heading outline of a page.",
      inputSchema: objectSchema({ path: { type: "string" } }, ["path"]),
      outputSchema: ENVELOPE_OUTPUT_SCHEMA,
      annotations: readOnly,
    },
    {
      name: "get_hacktricks_section",
      description:
        "Return the first heading matching a partial name through the next equal/higher heading.",
      inputSchema: objectSchema(
        { path: { type: "string" }, section: { type: "string" } },
        ["path", "section"],
      ),
      outputSchema: ENVELOPE_OUTPUT_SCHEMA,
      annotations: readOnly,
    },
    {
      name: "get_hacktricks_cheatsheet",
      description: "Return bounded ordinary triple-backtick code blocks from a page.",
      inputSchema: objectSchema({ path: { type: "string" } }, ["path"]),
      outputSchema: ENVELOPE_OUTPUT_SCHEMA,
      annotations: readOnly,
    },
    {
      name: "list_hacktricks_categories",
      description:
        "List top-level main-book categories, or a bounded category tree for one enumerated category.",
      inputSchema: objectSchema({ category: { type: "string" } }, []),
      outputSchema: ENVELOPE_OUTPUT_SCHEMA,
      annotations: readOnly,
    },
    {
      name: "hacktricks_quick_lookup",
      description:
        "Candidate discovery for a common technique: best page plus up to five code blocks.",
      inputSchema: objectSchema(
        { topic: { type: "string" }, category: { type: "string" } },
        ["topic"],
      ),
      outputSchema: ENVELOPE_OUTPUT_SCHEMA,
      annotations: readOnly,
    },
  ];
  return { handlers, defs };
}
