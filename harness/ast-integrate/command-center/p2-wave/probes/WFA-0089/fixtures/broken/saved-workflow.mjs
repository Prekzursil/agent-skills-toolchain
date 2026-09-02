// Defective saved-workflow dialect: all four banned nondeterminism classes.
export default async function workflow({ agent }) {
  const stamp = Date.now();
  const jitter = Math.random();
  const out = `${process.env.HOME}/wfa-out-${stamp}`;
  await agent(`summarize ${out} jitter=${jitter}`);
  const kids = ["b", "a", "c"].sort(() => Math.random() - 0.5);
  return { stamp, jitter, out, kids };
}
