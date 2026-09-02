// dialect-standin for harvest id wf-saved-design-gate (catalog: design-gate.mjs)
export async function workflow({ agent, phase }) {
  await phase("design-review", async () => {
    agent({
      "prompt": "review the design against the contract",
      "role": "design-reviewer",
      "gate": {
        "blocking": true,
        "expr": { "op": "eq", "left": "verdict", "right": "PASS" }
      }
    });
  });
}
