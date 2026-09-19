// Shipped module that illicitly imports a declared-dev-only package.
// Probe 2 MUST flag this: typescript is only in devDependencies, yet src/ ships.
import typescript from "typescript";

export function ping() {
  return typeof typescript;
}
