// Control: Promise.withResolvers is Node 22+. Declared engines.node is >=16.
// A scan that does not flag this file is not reading Node versions.
const { promise, resolve } = Promise.withResolvers();
resolve("ok");
await promise;
console.log("withResolvers-ok");
