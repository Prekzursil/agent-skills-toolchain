// dialect-standin: remaining live filename UNKNOWN (registry absent)
export async function workflow({ agent }) {
  await agent({
    "prompt": "read the contract then stop; do not shell out",
    "role": "constrained-reader",
    "tools": { "allow": ["Read", "Grep"], "deny": ["Bash", "Write"] },
    "resume": { "key": "tool-policy-resume", "after": "gate" }
  });
}
