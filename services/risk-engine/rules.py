from typing import Tuple

def check_chaos_safety(is_safe: bool) -> Tuple[bool, str]:
    if not is_safe:
        return False, "Hard Veto: Chaos sandbox test failed."
    return True, ""

def check_allocation_limit(trade_amount: float, portfolio_value: float, max_pct: float) -> Tuple[bool, str]:
    max_allowed = portfolio_value * max_pct
    if trade_amount > max_allowed:
        return False, f"Hard Veto: Trade amount exceeds {max_pct*100}% portfolio limit (${max_allowed})."
    return True, ""

def check_conviction_score(score: float, threshold: float) -> Tuple[bool, str]:
    if score < threshold:
        return False, f"Hard Veto: AI conviction score ({score}) is below the {threshold} threshold."
    return True, ""

def check_delta_limit(trade_delta_pct: float, current_portfolio_delta_pct: float, max_delta_pct: float) -> Tuple[bool, str]:
    # Both deltas are delta-dollar exposure as a fraction of portfolio
    # value (same normalization style as check_allocation_limit's dollars-
    # as-fraction-of-portfolio), not raw delta-equivalent-shares - a fixed
    # share count means a different real risk on every ticker's price.
    total = abs(current_portfolio_delta_pct + trade_delta_pct)
    if total > max_delta_pct:
        return False, f"Hard Veto: Portfolio delta exposure ({total*100:.1f}%) exceeds the {max_delta_pct*100:.0f}% limit."
    return True, ""