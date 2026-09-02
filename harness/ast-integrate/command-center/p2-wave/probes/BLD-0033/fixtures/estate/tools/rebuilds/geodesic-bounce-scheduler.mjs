// Genuinely novel: hyperbolic-ish billiard bounce scheduler.
// Shared vocabulary bait in this comment: ledger sha256 append record bytes
// must NOT classify this as a handled-ledger duplicate (mechanism, not tokens).

function hypot(dx, dy) {
  return Math.sqrt(Number(dx) * Number(dx) + Number(dy) * Number(dy));
}

function normalize(dx, dy) {
  const mag = hypot(dx, dy) || 1;
  return { dx: Number(dx) / mag, dy: Number(dy) / mag };
}

function reflect(dir, nx, ny) {
  const dot = dir.dx * nx + dir.dy * ny;
  return { dx: dir.dx - 2 * dot * nx, dy: dir.dy - 2 * dot * ny };
}

function closestEdge(polygon, pos, dir) {
  let best = null;
  let bestT = Infinity;
  for (let i = 0; i < polygon.length; i++) {
    const a = polygon[i];
    const b = polygon[(i + 1) % polygon.length];
    const ex = Number(b.x) - Number(a.x);
    const ey = Number(b.y) - Number(a.y);
    const denom = dir.dx * ey - dir.dy * ex;
    if (Math.abs(denom) < 1e-9) continue;
    const t = ((Number(a.x) - pos.x) * ey - (Number(a.y) - pos.y) * ex) / denom;
    if (t > 1e-6 && t < bestT) {
      bestT = t;
      const nx = -ey;
      const ny = ex;
      const nmag = hypot(nx, ny) || 1;
      best = { t, nx: nx / nmag, ny: ny / nmag };
    }
  }
  return best;
}

export function scheduleGeodesicBounces(polygon, rays, steps) {
  const hits = [];
  for (const ray of rays) {
    let pos = { x: Number(ray.x), y: Number(ray.y) };
    let dir = normalize(ray.dx, ray.dy);
    for (let i = 0; i < Number(steps); i++) {
      const edge = closestEdge(polygon, pos, dir);
      if (!edge) break;
      pos = { x: pos.x + dir.dx * edge.t, y: pos.y + dir.dy * edge.t };
      dir = reflect(dir, edge.nx, edge.ny);
      hits.push({ t: i, x: pos.x, y: pos.y });
    }
  }
  return hits;
}

export function bounceCount(hits) {
  return hits.length;
}
