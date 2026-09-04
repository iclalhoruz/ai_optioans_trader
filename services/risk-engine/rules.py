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

def check_delta_limit(trade_delta: float, current_portfolio_delta: float, max_delta: float) -> Tuple[bool, str]:
    if abs(current_portfolio_delta + trade_delta) > max_delta:
        return False, f"Hard Veto: Overall portfolio delta limit ({max_delta}) exceeded."
    return True, ""