// lib.mjs — shared helpers for the design-tokens-pipeline skill.
// DTCG = W3C Design Tokens Community Group format (spec v1.0, Oct 28 2025):
// a token is an object carrying a `$value` (and usually a `$type`); a *group*
// is a plain object of tokens/groups and may carry a `$type` that descendants
// inherit. Aliases reference another token with the `{group.token}` syntax.
// Reserved keys start with `$` (`$value`, `$type`, `$description`, `$extensions`).
// No external deps — Node built-ins only.

/** Minimal `--flag value` / `--flag=value` / boolean-flag parser. */
export function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const eq = a.indexOf("=");
      if (eq !== -1) {
        out[a.slice(2, eq)] = a.slice(eq + 1);
      } else {
        const next = argv[i + 1];
        if (next === undefined || next.startsWith("--")) {
          out[a.slice(2)] = true;
        } else {
          out[a.slice(2)] = next;
          i++;
        }
      }
    } else {
      out._.push(a);
    }
  }
  return out;
}

const HEX = /^#([0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})$/i;
const DIM = /^-?\d*\.?\d+(px|rem|em|%|vh|vw|pt)$/;
const NUM = /^-?\d*\.?\d+$/;
const DURATION = /^-?\d*\.?\d+(ms|s)$/;
const ALIAS = /^\{[^}]+\}$/;

/**
 * Infer a DTCG `$type` from a raw CSS value. Returns one of the DTCG core
 * types or null when we cannot tell (caller should then leave $type unset and
 * let validation flag it, rather than guessing wrong).
 */
export function inferType(value) {
  if (typeof value !== "string") return null;
  const v = value.trim();
  if (ALIAS.test(v)) return null; // alias resolves to the referent's type
  if (HEX.test(v)) return "color";
  if (/^(rgb|rgba|hsl|hsla|oklch|oklab|color)\(/i.test(v)) return "color";
  if (DURATION.test(v)) return "duration";
  if (DIM.test(v)) return "dimension";
  if (/\bcubic-bezier\(/i.test(v) || ["linear", "ease", "ease-in", "ease-out", "ease-in-out"].includes(v))
    return "cubicBezier";
  if (/\d+px\s+\d+px/.test(v) && /rgba?\(|#[0-9a-f]/i.test(v)) return "shadow";
  if (/,/.test(v) && /[a-z]/i.test(v) && !DIM.test(v)) return "fontFamily";
  if (NUM.test(v)) return "number";
  return null;
}

/**
 * Flatten a DTCG tree to a Map of dot-path -> { value, type } for every leaf
 * token (an object owning `$value`). `$type` is resolved by walking up the
 * group chain (nearest ancestor `$type` wins) per the DTCG inheritance rule.
 */
export function flatten(tree, prefix = "", inheritedType = null, out = new Map()) {
  if (tree == null || typeof tree !== "object") return out;
  const groupType = typeof tree.$type === "string" ? tree.$type : inheritedType;
  if (Object.prototype.hasOwnProperty.call(tree, "$value")) {
    out.set(prefix, {
      value: tree.$value,
      type: typeof tree.$type === "string" ? tree.$type : groupType,
    });
    return out;
  }
  for (const key of Object.keys(tree)) {
    if (key.startsWith("$")) continue;
    const child = tree[key];
    const path = prefix ? `${prefix}.${key}` : key;
    flatten(child, path, groupType, out);
  }
  return out;
}

/** Build a nested DTCG tree from [path, {value,type}] entries. */
export function unflatten(entries) {
  const root = {};
  for (const [path, leaf] of entries) {
    const parts = path.split(".");
    let node = root;
    for (let i = 0; i < parts.length - 1; i++) {
      node[parts[i]] ??= {};
      node = node[parts[i]];
    }
    const tok = { $value: leaf.value };
    if (leaf.type) tok.$type = leaf.type;
    node[parts[parts.length - 1]] = tok;
  }
  return root;
}

/** Resolve a `{group.token}` alias to a dot-path; returns null if not an alias. */
export function aliasTarget(value) {
  if (typeof value !== "string" || !ALIAS.test(value.trim())) return null;
  return value.trim().slice(1, -1);
}

/**
 * Convert a flat name like `color-primary-500` (CSS custom property minus the
 * leading `--` and optional prefix) into a DTCG dot-path `color.primary.500`.
 */
export function nameToPath(name, stripPrefix = "") {
  let n = name.replace(/^--/, "");
  if (stripPrefix && n.startsWith(stripPrefix)) n = n.slice(stripPrefix.length).replace(/^-/, "");
  return n.split("-").filter(Boolean).join(".");
}

/** Convert a CSS `var(--x)` reference inside a value into a DTCG `{x}` alias. */
export function cssRefToAlias(value, stripPrefix = "") {
  return value.replace(/var\(\s*--([\w-]+)\s*(?:,[^)]*)?\)/g, (_, ref) => `{${nameToPath(ref, stripPrefix)}}`);
}

/** Last line of every CLI: a §4 terminal-state marker. */
export function emitMarker(ok, id, reason = "") {
  const tag = ok ? `SUCCESS:${id}` : `FAILED:${id}`;
  const line = reason ? `${tag} ${reason}` : tag;
  process.stdout.write(line + "\n");
  return ok ? 0 : 1;
}
