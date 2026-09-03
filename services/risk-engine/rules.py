from typing import Tuple

def check_chaos_safety(is_safe: bool) -> Tuple[bool, str]:
    if not is_safe:
        return False, "Hard Veto: Chaos sandbox test failed."
    return True, ""

def check_allocation_limit(trade_amount: float, portfolio_value: float) -> Tuple[bool, str]:
    max_allowed = portfolio_value * 0.05
    if trade_amount > max_allowed:
        return False, f"Hard Veto: Trade amount exceeds 5% portfolio limit (${max_allowed})."
    return True, ""

def check_conviction_score(score: float, threshold: float = 0.80) -> Tuple[bool, str]:
    if score < threshold:
        return False, f"Hard Veto: AI conviction score ({score}) is below the {threshold} threshold."
    return True, ""

def check_delta_limit(trade_delta: float, current_portfolio_delta: float = 0.0) -> Tuple[bool, str]:
    max_delta = 0.5 
    if abs(current_portfolio_delta + trade_delta) > max_delta:
        return False, "Hard Veto: Overall portfolio delta limit exceeded."
    return True, ""