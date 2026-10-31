// Read-only corpus access: fail-closed health check, hardened ripgrep search,
// and bounded page reads. All process/filesystem primitives are INJECTED so the
// policy is fully unit-testable; the concrete Node primitives live in defaults.ts.

import { PINNED_CORPUS_COMMIT, normalizeOrigin, CORPUS_REPOSITORY_MAIN } from "./provenance.js";
import { MAX_FILE_BYTES, RG_MAX_BUFFER_BYTES, RG_MAX_COUNT, SEARCH_TIMEOUT_MS } from "./limits.js";
import { asRecord, byteLength, withinRoot } from "./util.js";

// --- injected primitive contracts -----------------------------------------

export interface ExecOutcome {
  stdout: string;
  exitCode: number | null;
  timedOut: boolean;
  bufferExceeded: boolean;
  spawnError: string | null;
}
export type ExecFn = (
  file: string,
  args: string[],
  opts: { timeout: number; maxBuffer: number; cwd: string },
) => Promise<ExecOutcome>;

export type GitFn = (
  root: string,
  args: string[],
) => Promise<{ ok: true; stdout: string } | { ok: false; message: string }>;

export interface DirEntry {
  name: string;
  isDirectory: boolean;
}

export interface CorpusFs {
  pathExists(path: string): Promise<boolean>;
  realpath(path: string): Promise<string>;
  statFile(path: string): Promise<{ isDirectory: boolean; size: number } | null>;
  readTextFile(path: string): Promise<string>;
  listDir(path: string): Promise<DirEntry[]>;
}

// --- health check -----------------------------------------------------------

export type CorpusStatus =
  | { ok: true; root: string; revision: string; committedAt: string }
  | {
      ok: false;
      code: "backend_unavailable";
      subcode: string;
      message: string;
    };

function unavailable(subcode: string, message: string): CorpusStatus {
  return { ok: false, code: "backend_unavailable", subcode, message };
}

function joinPath(root: string, rel: string): string {
  return `${root.replace(/[\\/]+$/, "")}/${rel}`;
}

export async function checkCorpusHealth(
  root: string,
  git: GitFn,
  fs: CorpusFs,
): Promise<CorpusStatus> {
  if (!(await fs.pathExists(root))) {
    return unavailable("corpus_missing", "corpus repository not found");
  }
  if (!(await fs.pathExists(joinPath(root, "src")))) {
    return unavailable("corpus_src_missing", "corpus src directory not found");
  }
  if (!(await fs.pathExists(joinPath(root, "src/SUMMARY.md")))) {
    return unavailable("summary_missing", "corpus src/SUMMARY.md not found");
  }

  const origin = await git(root, ["remote", "get-url", "origin"]);
  if (!origin.ok) {
    return unavailable("git_error", "failed to read corpus origin");
  }
  if (normalizeOrigin(origin.stdout) !== normalizeOrigin(CORPUS_REPOSITORY_MAIN)) {
    return unavailable("origin_mismatch", "corpus origin is not the official repository");
  }

  const head = await git(root, ["rev-parse", "HEAD"]);
  if (!head.ok) {
    return unavailable("git_error", "failed to read corpus HEAD");
  }
  const revision = head.stdout.trim();
  if (revision !== PINNED_CORPUS_COMMIT) {
    return unavailable("revision_mismatch", "corpus HEAD is not the pinned revision");
  }

  const status = await git(root, ["status", "--porcelain", "--untracked-files=no"]);
  if (!status.ok) {
    return unavailable("git_error", "failed to read corpus status");
  }
  if (status.stdout.trim().length > 0) {
    return unavailable("dirty_tree", "corpus working tree has tracked modifications");
  }

  const committed = await git(root, ["show", "-s", "--format=%cI", "HEAD"]);
  if (!committed.ok) {
    return unavailable("git_error", "failed to read corpus commit time");
  }

  const realRoot = await fs.realpath(root);
  const realSrc = await fs.realpath(joinPath(root, "src"));
  if (!withinRoot(realRoot, realSrc)) {
    return unavailable("src_escape", "resolved src escapes the corpus root");
  }

  return { ok: true, root, revision, committedAt: committed.stdout.trim() };
}

// --- ripgrep search ---------------------------------------------------------

export interface RgHit {
  path: string;
  line: number;
  text: string;
}
export type RgOutcome =
  | { ok: true; hits: RgHit[] }
  | { ok: false; code: "backend_unavailable"; subcode: string; message: string };

export function parseRgJson(stdout: string): RgHit[] {
  const hits: RgHit[] = [];
  for (const line of stdout.split("\n")) {
    if (line.trim() === "") {
      continue;
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(line);
    } catch {
      continue;
    }
    const rec = asRecord(parsed);
    if (rec === null || rec["type"] !== "match") {
      continue;
    }
    const data = asRecord(rec["data"]);
    if (data === null) {
      continue;
    }
    const pathRec = asRecord(data["path"]);
    const linesRec = asRecord(data["lines"]);
    const pathText = pathRec === null ? undefined : pathRec["text"];
    const lineNo = data["line_number"];
    const linesText = linesRec === null ? undefined : linesRec["text"];
    if (typeof pathText !== "string" || typeof lineNo !== "number") {
      continue;
    }
    const text = typeof linesText === "string" ? linesText : "";
    hits.push({ path: pathText, line: lineNo, text: text.replace(/\r?\n$/, "").slice(0, 240) });
  }
  return hits;
}

// Invoke ripgrep as an executable (no shell) with `-e <query> --` so a
// leading-dash query stays data, `--json` so Windows drive colons cannot corrupt
// fields, and bounded timeout/buffer. Timeout -> rg_timeout, max-buffer ->
// rg_buffer_exceeded; both are backend_unavailable.
export async function runRipgrep(
  query: string,
  searchRoot: string,
  cwd: string,
  exec: ExecFn,
): Promise<RgOutcome> {
  const args = [
    "--json",
    "-n",
    "-i",
    "--type",
    "md",
    "--max-count",
    String(RG_MAX_COUNT),
    "-e",
    query,
    "--",
    searchRoot,
  ];
  const result = await exec("rg", args, {
    timeout: SEARCH_TIMEOUT_MS,
    maxBuffer: RG_MAX_BUFFER_BYTES,
    cwd,
  });
  if (result.spawnError !== null) {
    return unavailableRg("rg_unavailable", "ripgrep could not be started");
  }
  if (result.timedOut) {
    return unavailableRg("rg_timeout", "search timed out");
  }
  if (result.bufferExceeded) {
    return unavailableRg("rg_buffer_exceeded", "search output exceeded the buffer");
  }
  // ripgrep exit 0 = matches, 1 = no matches (both fine); >=2 = real error.
  if (result.exitCode !== 0 && result.exitCode !== 1) {
    return unavailableRg("rg_failed", "search failed");
  }
  return { ok: true, hits: parseRgJson(result.stdout) };
}

function unavailableRg(subcode: string, message: string): RgOutcome {
  return { ok: false, code: "backend_unavailable", subcode, message };
}

// --- page read --------------------------------------------------------------

export type PageOutcome =
  | { ok: true; content: string; absolutePath: string }
  | {
      ok: false;
      code: "retrieval_failed" | "content_too_large" | "query_invalid";
      message: string;
    };

// `relPath` is already lexically validated (src-rooted, `.md`). This adds the
// realpath containment check and byte bounds; component boundaries, not string
// prefixes, decide containment.
export async function readPage(
  root: string,
  relPath: string,
  fs: CorpusFs,
): Promise<PageOutcome> {
  const abs = joinPath(root, relPath);
  const stat = await fs.statFile(abs);
  if (stat === null) {
    return { ok: false, code: "retrieval_failed", message: "page not found" };
  }
  if (stat.isDirectory) {
    return { ok: false, code: "retrieval_failed", message: "path is a directory" };
  }
  if (stat.size > MAX_FILE_BYTES) {
    return { ok: false, code: "content_too_large", message: "page exceeds the byte bound" };
  }
  const realRoot = await fs.realpath(root);
  const realFile = await fs.realpath(abs);
  if (!withinRoot(realRoot, realFile)) {
    return { ok: false, code: "query_invalid", message: "path escapes the corpus root" };
  }
  const content = await fs.readTextFile(abs);
  if (byteLength(content) > MAX_FILE_BYTES) {
    return { ok: false, code: "content_too_large", message: "page exceeds the byte bound" };
  }
  return { ok: true, content, absolutePath: realFile };
}

// --- category enumeration ---------------------------------------------------

export interface CategoryNode {
  name: string;
  path: string;
  children: CategoryNode[];
}

// Top-level main-book categories = directories directly under src/.
export async function listTopCategories(root: string, fs: CorpusFs): Promise<string[]> {
  const entries = await fs.listDir(joinPath(root, "src"));
  return entries
    .filter((entry) => entry.isDirectory)
    .map((entry) => entry.name)
    .sort();
}

interface Budget {
  count: number;
  max: number;
  truncated: boolean;
}

async function walkCategories(
  fs: CorpusFs,
  absDir: string,
  relDir: string,
  depth: number,
  maxDepth: number,
  budget: Budget,
): Promise<CategoryNode[]> {
  if (depth >= maxDepth) {
    return [];
  }
  const entries = await fs.listDir(absDir);
  const nodes: CategoryNode[] = [];
  for (const entry of entries) {
    if (!entry.isDirectory) {
      continue;
    }
    if (budget.count >= budget.max) {
      budget.truncated = true;
      break;
    }
    budget.count += 1;
    const childRel = relDir === "" ? entry.name : `${relDir}/${entry.name}`;
    const children = await walkCategories(
      fs,
      joinPath(absDir, entry.name),
      childRel,
      depth + 1,
      maxDepth,
      budget,
    );
    nodes.push({ name: entry.name, path: childRel, children });
  }
  return nodes;
}

// Enumerate the directory tree under src/<category> to `maxDepth`, capped at
// `maxNodes` directory nodes.
export async function enumerateCategoryTree(
  root: string,
  fs: CorpusFs,
  category: string,
  maxDepth: number,
  maxNodes: number,
): Promise<{ tree: CategoryNode[]; truncated: boolean }> {
  const budget: Budget = { count: 0, max: maxNodes, truncated: false };
  const tree = await walkCategories(
    fs,
    joinPath(root, `src/${category}`),
    "",
    0,
    maxDepth,
    budget,
  );
  return { tree, truncated: budget.truncated };
}
