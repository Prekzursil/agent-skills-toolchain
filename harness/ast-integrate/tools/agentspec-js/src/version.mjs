/**
 * The spec version this runtime accepts — the JS mirror of `agentspec/__init__.py`.
 *
 * Kept in its own module so `validate.mjs` does not have to import a barrel (which would make
 * the barrel and the validator mutually dependent). `crosslang.test.mjs` pins it against the
 * Python `SPEC_VERSION`, so bumping one side alone fails the gate.
 */

/** The only spec version this package accepts. Bumping it is a reviewed diff. */
export const SPEC_VERSION = "1";
