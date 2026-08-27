#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const MODES = new Set(["readable", "audit", "dialogue"]);

function usage(exitCode = 0) {
  const text = [
    "Usage:",
    "  node render_codex_session.mjs --input <session.jsonl> [--output <transcript.md>] [--mode readable|audit|dialogue]",
    "",
    "Defaults:",
    "  --mode readable",
    "  --output stdout",
  ].join("\n");
  const stream = exitCode === 0 ? process.stdout : process.stderr;
  stream.write(`${text}\n`);
  process.exit(exitCode);
}

function parseArgs(argv) {
  const args = { mode: "readable" };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--help" || arg === "-h") usage(0);
    if (arg === "--input") {
      args.input = argv[++i];
      continue;
    }
    if (arg === "--output") {
      args.output = argv[++i];
      continue;
    }
    if (arg === "--mode") {
      args.mode = argv[++i];
      continue;
    }
    throw new Error(`Unknown argument: ${arg}`);
  }
  if (!args.input) throw new Error("--input is required");
  if (!MODES.has(args.mode)) throw new Error(`Unsupported mode: ${args.mode}`);
  return args;
}

function safeJsonParse(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function normalizePath(filePath) {
  return filePath.replace(/^\\\\\?\\/, "");
}

function readJsonl(filePath) {
  const raw = fs.readFileSync(normalizePath(filePath), "utf8");
  return raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => safeJsonParse(line))
    .filter(Boolean);
}

function redactText(text) {
  if (!text) return "";
  const patterns = [
    [/(access_token|refresh_token|id_token)"?\s*[:=]\s*"[^"]+"/gi, '$1: "[REDACTED]"'],
    [/\bBearer\s+[A-Za-z0-9._-]+\b/g, "Bearer [REDACTED]"],
    [/(cookie|authorization|set-cookie)"?\s*[:=]\s*"[^"]+"/gi, '$1: "[REDACTED]"'],
    [/\b(rt_[A-Za-z0-9._-]+)\b/g, "[REDACTED_REFRESH_TOKEN]"],
    [/\b(sk-[A-Za-z0-9._-]+)\b/g, "[REDACTED_API_KEY]"],
  ];

  let result = text;
  for (const [pattern, replacement] of patterns) {
    result = result.replace(pattern, replacement);
  }
  return result;
}

function stripInjectedContext(text) {
  const replacements = [
    [/# AGENTS\.md instructions[\s\S]*?<\/INSTRUCTIONS>\s*/gi, "[AGENTS instructions attached]\n\n"],
    [/<environment_context>[\s\S]*?<\/environment_context>\s*/gi, "[Environment context attached]\n\n"],
    [/========= MEMORY_SUMMARY BEGINS =========[\s\S]*?========= MEMORY_SUMMARY ENDS =========\s*/gi, "[Memory summary attached]\n\n"],
    [/<image[^>]*>[\s\S]*?<\/image>\s*/gi, "[Image attached]\n\n"],
  ];

  let result = text;
  for (const [pattern, replacement] of replacements) {
    result = result.replace(pattern, replacement);
  }
  return result;
}

function truncate(text, limit = 160) {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (cleaned.length <= limit) return cleaned;
  return `${cleaned.slice(0, limit - 3)}...`;
}

function extractMessageText(content, role, mode) {
  if (!Array.isArray(content)) return "";
  if (role === "developer" || role === "system") {
    if (mode === "audit") return `[${role} prompt omitted]`;
    return "";
  }

  const parts = [];
  for (const item of content) {
    if (!item || typeof item !== "object") continue;
    if (item.type === "input_text" || item.type === "output_text") {
      let text = redactText(item.text || "");
      if (role === "user") text = stripInjectedContext(text);
      if (text) parts.push(text);
      continue;
    }
    if (item.type === "input_image") {
      parts.push("[Image attached]");
      continue;
    }
    if (item.type === "output_image") {
      parts.push("[Image generated]");
    }
  }

  return parts.join("\n\n").trim();
}

function isPlaceholderOnly(text) {
  const compact = text.replace(/\s+/g, " ").trim();
  return /^\[(?:[^\]]+)\](?:\s+\[(?:[^\]]+)\])*$/.test(compact);
}

function summarizeExecCommand(commandText) {
  const line = truncate(commandText, 120);
  return line ? `Ran exec_command: \`${line}\`` : "Ran exec_command.";
}

function summarizeArgs(name, argsText) {
  const args = safeJsonParse(argsText);
  if (!args || typeof args !== "object") return `Called \`${name}\`.`;

  if (name === "exec_command" && typeof args.cmd === "string") {
    return summarizeExecCommand(args.cmd);
  }
  if (name === "request_user_input") return "Requested user input.";
  if (name === "apply_patch") return "Applied a patch.";
  if (name === "spawn_agent") return "Spawned a sub-agent.";
  if (name === "wait") return "Waited for a sub-agent result.";

  const interestingKey = ["path", "q", "query", "url", "location", "ticker"].find((key) =>
    Object.prototype.hasOwnProperty.call(args, key),
  );
  if (interestingKey) {
    return `Called \`${name}\`: ${truncate(String(args[interestingKey]), 100)}`;
  }
  return `Called \`${name}\`.`;
}

function summarizeOutput(name, outputText) {
  const output = typeof outputText === "string" ? outputText : JSON.stringify(outputText);
  if (!output) return `\`${name}\` returned output.`;

  const exitMatch = output.match(/Process exited with code (\d+)/);
  if (exitMatch) {
    return `\`${name}\` finished with exit code ${exitMatch[1]}.`;
  }

  const lines = output
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, 2)
    .join(" | ");

  if (lines) return `\`${name}\` output: ${truncate(redactText(lines), 140)}`;
  return `\`${name}\` returned output.`;
}

function formatTimestamp(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toISOString();
}

function buildTranscript(events, mode) {
  const meta = {};
  const items = [];
  const pendingCalls = new Map();

  for (const event of events) {
    if (!event || typeof event !== "object") continue;

    if (event.type === "session_meta") {
      const payload = event.payload || {};
      meta.sessionId = payload.id || meta.sessionId;
      meta.startedAt = payload.timestamp || event.timestamp || meta.startedAt;
      meta.cwd = payload.cwd || meta.cwd;
      meta.source = payload.source || meta.source;
      meta.originator = payload.originator || meta.originator;
      meta.modelProvider = payload.model_provider || meta.modelProvider;
      continue;
    }

    if (event.type === "response_item") {
      const payload = event.payload || {};

      if (payload.type === "message") {
        const text = extractMessageText(payload.content, payload.role, mode);
        if (!text) continue;
        if (payload.role === "user" && mode === "readable" && isPlaceholderOnly(text)) {
          items.push({
            kind: "note",
            timestamp: event.timestamp,
            text: `Context attached: ${text.replace(/\n+/g, " ").trim()}`,
          });
          continue;
        }
        items.push({
          kind: "turn",
          role: payload.role,
          timestamp: event.timestamp,
          text,
        });
        continue;
      }

      if (payload.type === "function_call") {
        pendingCalls.set(payload.call_id, payload);
        if (mode !== "dialogue") {
          items.push({
            kind: "note",
            timestamp: event.timestamp,
            text: summarizeArgs(payload.name || "tool", payload.arguments || ""),
          });
        }
        continue;
      }

      if (payload.type === "function_call_output") {
        const call = pendingCalls.get(payload.call_id);
        pendingCalls.delete(payload.call_id);
        if (mode !== "dialogue") {
          items.push({
            kind: "note",
            timestamp: event.timestamp,
            text: summarizeOutput(call?.name || "tool", payload.output),
          });
        }
        continue;
      }

      if (payload.type === "web_search_call" && mode !== "dialogue") {
        items.push({
          kind: "note",
          timestamp: event.timestamp,
          text: "Ran a web search.",
        });
      }

      if (payload.type === "reasoning" && mode === "audit") {
        items.push({
          kind: "note",
          timestamp: event.timestamp,
          text: "Reasoning step omitted.",
        });
      }

      continue;
    }

    if (event.type === "event_msg" && mode === "audit") {
      const payload = event.payload || {};
      if (typeof payload.message === "string" && payload.message.trim()) {
        items.push({
          kind: "note",
          timestamp: event.timestamp,
          text: truncate(redactText(payload.message), 160),
        });
      }
    }
  }

  return { meta, items };
}

function renderHeader(meta, mode, inputPath) {
  const lines = [
    "# Codex Session Transcript",
    "",
    `- Source file: \`${inputPath}\``,
    `- Mode: \`${mode}\``,
  ];

  if (meta.sessionId) lines.push(`- Session ID: \`${meta.sessionId}\``);
  if (meta.startedAt) lines.push(`- Started: \`${formatTimestamp(meta.startedAt)}\``);
  if (meta.cwd) lines.push(`- CWD: \`${meta.cwd}\``);
  if (meta.source) lines.push(`- Source: \`${meta.source}\``);
  if (meta.originator) lines.push(`- Originator: \`${meta.originator}\``);
  if (meta.modelProvider) lines.push(`- Model provider: \`${meta.modelProvider}\``);

  lines.push("", "## Conversation", "");
  return lines;
}

function renderItems(items) {
  const lines = [];
  for (let i = 0; i < items.length; i += 1) {
    const item = items[i];
    if (item.kind === "turn") {
      lines.push(`### ${item.role[0].toUpperCase()}${item.role.slice(1)}`);
      if (item.timestamp) lines.push(`_${formatTimestamp(item.timestamp)}_`);
      lines.push("", item.text, "");
      continue;
    }

    if (item.kind === "note") {
      const notes = [];
      let j = i;
      while (j < items.length && items[j].kind === "note") {
        notes.push(items[j]);
        j += 1;
      }
      lines.push("### Tool Activity");
      for (const note of notes) {
        lines.push(`- ${note.text}`);
      }
      lines.push("");
      i = j - 1;
    }
  }
  return lines;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const inputPath = normalizePath(path.resolve(args.input));
  if (!fs.existsSync(inputPath)) {
    throw new Error(`Input file not found: ${inputPath}`);
  }

  const events = readJsonl(inputPath);
  const transcript = buildTranscript(events, args.mode);
  const lines = [
    ...renderHeader(transcript.meta, args.mode, inputPath),
    ...renderItems(transcript.items),
  ];
  const markdown = `${lines.join("\n").trim()}\n`;

  if (args.output) {
    const outputPath = normalizePath(path.resolve(args.output));
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(outputPath, markdown, "utf8");
  } else {
    process.stdout.write(markdown);
  }
}

try {
  main();
} catch (error) {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  usage(1);
}
