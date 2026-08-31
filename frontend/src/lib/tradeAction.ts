import type { BadgeProps } from "@/components/ui/Badge"
import type { TradeAction } from "@/types/domain"

// Shared by every screen that renders a BUY/SELL/HOLD badge (Dashboard's
// strategy card, run history, ...) so the color mapping lives in one place.
export const ACTION_BADGE_TONE: Record<TradeAction, NonNullable<BadgeProps["tone"]>> = {
  BUY: "buy",
  SELL: "sell",
  HOLD: "hold",
}
