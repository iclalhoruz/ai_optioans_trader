import httpx
from fastapi import FastAPI
from schemas import TradeProposal, EvaluationResponse
from rules import (
    check_chaos_safety,
    check_allocation_limit,
    check_conviction_score,
    check_delta_limit
)

app = FastAPI(title="Aegis-OptionAI Risk Engine")

async def get_mock_portfolio_value() -> float:
    """
    Mock function returning a temporary balance of $100,000.
    To be replaced with httpx.AsyncClient() calling http://localhost:8001/account
    """
    return 100000.0

@app.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_trade(proposal: TradeProposal):
    portfolio_value = await get_mock_portfolio_value()
    
    rules_to_check = [
        check_chaos_safety(proposal.chaos_result.is_safe),
        check_allocation_limit(proposal.amount, portfolio_value),
        check_conviction_score(proposal.conviction_score),
        check_delta_limit(proposal.trade_delta)
    ]
    
    for passed, reasons in rules_to_check:
        if not passed:
            return EvaluationResponse(approved=False, reasons=reasons)
            
    return EvaluationResponse(approved=True)