export function makeScheduler(space) {
  const points = [];
  const bounce = (index) => {
    const angle = 2 * Math.PI * index / space;
    points.push([Math.cos(angle), Math.sin(angle)]);
    return points[points.length - 1];
  };
  return { bounce, points };
}
