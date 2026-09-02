// dialect-standin: remaining live filename UNKNOWN (registry absent)
// known dialect defects: Date.now() and background/fire-and-forget
export async function workflow({ agent }) {
  const started = Date.now();
  await agent({
    "prompt": "notify without waiting",
    "role": "notifier",
    "background": true
  });
  return started;
}
