// focused re-checks: (a) dependents of a parked card still launched; (b) synthesizer after HALT; (c) fixer prompt for a digest-only failure
import { makeScript } from './assembled.mjs'
const src = await import('./drive.mjs').catch(() => null)
