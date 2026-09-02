// dialect-standin: remaining live filename UNKNOWN (registry absent)
export async function workflow({ agent }) {
  await agent({
    "prompt": "pause for a human checkpoint then continue",
    "role": "operator",
    "checkpoint": { "human": true, "label": "manual-review" },
    "lineage": {
      "origin": "claude-code-saved-workflow",
      "parent": "wf-saved-design-gate"
    }
  });
}
