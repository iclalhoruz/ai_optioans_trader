// Single source for every plain-language explanation shown via InfoTooltip.
// Written once here so the same term reads identically everywhere it
// appears, instead of each screen inventing its own wording.
export const GLOSSARY = {
  chaosSandbox:
    "Stress-tests this trade against extreme, simulated market shocks (sudden price swings, liquidity dry-ups) before it's ever trusted with real money.",
  riskGate:
    "A strict, rule-based safety check - not AI. It only does math against hard limits (like max position size) and either approves or blocks the trade, no exceptions.",
  hardGate:
    "A safety rule with no override from the AI - if a trade breaks it, the trade is blocked automatically, regardless of how confident the AI was.",
  optionsStrategy:
    "An options trade: a bet on a stock's price direction with a defined, limited amount of money at risk.",
} as const

export type GlossaryTerm = keyof typeof GLOSSARY
