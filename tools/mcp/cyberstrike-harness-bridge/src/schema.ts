export type JsonSchema = Readonly<Record<string, unknown>>;

export const text = (maxLength = 2048, extra: Record<string, unknown> = {}): JsonSchema =>
  Object.freeze({ type: "string", minLength: 1, maxLength, ...extra });

export const integer = (minimum = 0, maximum = 1_000_000): JsonSchema =>
  Object.freeze({ type: "integer", minimum, maximum });

export const number = (minimum = 0, maximum = 1_000_000): JsonSchema =>
  Object.freeze({ type: "number", minimum, maximum });

export const boolean = (): JsonSchema => Object.freeze({ type: "boolean" });

export const enumeration = (values: readonly (string | number)[]): JsonSchema =>
  Object.freeze({ type: typeof values[0] === "number" ? "number" : "string", enum: [...values] });

export const arrayOf = (items: JsonSchema, maxItems = 100, minItems = 0): JsonSchema =>
  Object.freeze({ type: "array", items, minItems, maxItems });

export const objectSchema = (
  properties: Record<string, JsonSchema> = {},
  required: readonly string[] = [],
): JsonSchema =>
  Object.freeze({
    type: "object",
    properties: Object.freeze({ ...properties }),
    required: [...required],
    additionalProperties: false,
  });

export class SchemaValidationError extends Error {
  code: string;

  constructor(code: string) {
    super(code);
    this.name = "SchemaValidationError";
    this.code = code;
  }
}

function fail(path: string, reason: string): never {
  throw new SchemaValidationError(`invalid_arguments:${path}:${reason}`);
}

export function validateSchema(schema: JsonSchema, value: unknown, path = "arguments"): void {
  if (Array.isArray(schema.anyOf)) {
    const matched = (schema.anyOf as JsonSchema[]).some((candidate) => {
      try {
        validateSchema(candidate, value, path);
        return true;
      } catch {
        return false;
      }
    });
    if (!matched) fail(path, "any_of");
    return;
  }

  if (Array.isArray(schema.oneOf)) {
    const matches = (schema.oneOf as JsonSchema[]).filter((candidate) => {
      try {
        validateSchema(candidate, value, path);
        return true;
      } catch {
        return false;
      }
    });
    if (matches.length !== 1) fail(path, "one_of");
    return;
  }

  const type = schema.type;
  if (type === "object") {
    if (value === null || typeof value !== "object" || Array.isArray(value)) fail(path, "object_required");
    const record = value as Record<string, unknown>;
    const properties = (schema.properties ?? {}) as Record<string, JsonSchema>;
    const required = (schema.required ?? []) as string[];
    const keys = Object.keys(record);
    const minProperties = Number(schema.minProperties ?? 0);
    const maxProperties = Number(schema.maxProperties ?? Number.MAX_SAFE_INTEGER);
    if (keys.length < minProperties || keys.length > maxProperties) fail(path, "object_bounds");
    for (const key of required) {
      if (!Object.hasOwn(record, key)) fail(`${path}.${key}`, "required");
    }
    if (schema.propertyNames && typeof schema.propertyNames === "object") {
      const propertyNameSchema = schema.propertyNames as JsonSchema;
      for (const key of keys) {
        try {
          if (
            propertyNameSchema.pattern &&
            !new RegExp(String(propertyNameSchema.pattern), "u").test(key)
          ) {
            throw new SchemaValidationError("property_name_pattern");
          }
          if (
            Array.isArray(propertyNameSchema.enum) &&
            !(propertyNameSchema.enum as unknown[]).includes(key)
          ) {
            throw new SchemaValidationError("property_name_enum");
          }
        } catch {
          fail(`${path}.${key}`, "property_name");
        }
      }
    }
    for (const [key, item] of Object.entries(record)) {
      const propertySchema = properties[key];
      if (propertySchema) {
        validateSchema(propertySchema, item, `${path}.${key}`);
      } else if (schema.additionalProperties === false) {
        fail(`${path}.${key}`, "additional_property");
      } else if (typeof schema.additionalProperties === "object") {
        validateSchema(schema.additionalProperties as JsonSchema, item, `${path}.${key}`);
      }
    }
    return;
  }

  if (type === "array") {
    if (!Array.isArray(value)) fail(path, "array_required");
    const minItems = Number(schema.minItems ?? 0);
    const maxItems = Number(schema.maxItems ?? Number.MAX_SAFE_INTEGER);
    if (value.length < minItems || value.length > maxItems) fail(path, "array_bounds");
    value.forEach((item, index) => validateSchema(schema.items as JsonSchema, item, `${path}[${index}]`));
    return;
  }

  if (type === "string") {
    if (typeof value !== "string") fail(path, "string_required");
    const minLength = Number(schema.minLength ?? 0);
    const maxLength = Number(schema.maxLength ?? Number.MAX_SAFE_INTEGER);
    if (value.length < minLength || value.length > maxLength) fail(path, "string_bounds");
    if (schema.pattern && !new RegExp(String(schema.pattern), "u").test(value)) fail(path, "pattern");
  } else if (type === "integer") {
    if (!Number.isSafeInteger(value)) fail(path, "integer_required");
  } else if (type === "number") {
    if (typeof value !== "number" || !Number.isFinite(value)) fail(path, "number_required");
  } else if (type === "boolean") {
    if (typeof value !== "boolean") fail(path, "boolean_required");
  } else if (type === "null") {
    if (value !== null) fail(path, "null_required");
  } else {
    fail(path, "unsupported_schema_type");
  }

  if ((type === "integer" || type === "number") && typeof value === "number") {
    if (value < Number(schema.minimum ?? -Infinity) || value > Number(schema.maximum ?? Infinity)) {
      fail(path, "number_bounds");
    }
  }
  if (Array.isArray(schema.enum) && !(schema.enum as unknown[]).includes(value)) fail(path, "enum");
}
