// inexpressible: wall-clock dependency
export const meta = { name: 'date-now' };
const stamp = Date.now();
export const run = () => stamp;
