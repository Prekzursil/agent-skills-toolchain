import { pathToFileURL } from "node:url";

export function isDirectEntrypoint(moduleUrl: string, argv1: string | undefined): boolean {
  return typeof argv1 === "string" && argv1.length > 0 && moduleUrl === pathToFileURL(argv1).href;
}
