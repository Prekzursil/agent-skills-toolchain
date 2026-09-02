// dialect-standin for catalog-named plan-gate.mjs
export async function workflow({ agent, phase }) {
  await phase("plan-review", async () => {
    agent({
      "prompt": "block until the plan is accepted",
      "role": "plan-reviewer",
      "gate": {
        "blocking": true,
        "expr": { "op": "eq", "left": "plan_status", "right": "ACCEPTED" }
      },
      "checkpoint": { "human": true, "label": "owner-plan-signoff" }
    });
  });
}
