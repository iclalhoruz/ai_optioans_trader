import httpx
from fastapi import FastAPI
from pydantic_settings import BaseSettings, SettingsConfigDict
from contracts.schemas import ChaosTestResult, RiskResult, TradeProposal
from rules import (
    check_chaos_safety,
    check_allocation_limit,
    check_conviction_score,
    check_delta_limit
)

class Settings(BaseSettings):
    max_allocation_pct: float = 0.05
    min_conviction_score: float = 0.80
    max_portfolio_delta: float = 0.5
    broker_gateway_url: str = "http://broker-gateway:8001"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings()

app = FastAPI(title="Aegis-OptionAI Risk Engine")

async def get_portfolio_value() -> float:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{settings.broker_gateway_url}/account")
            response.raise_for_status()
            data = response.json()
            return float(data.get("portfolio_value", 100000.0))
    except Exception as e:
        print(f"Broker connection error: {e}")
        return 100000.0

@app.post("/validate-risk", response_model=RiskResult)
async def validate_risk(chaos_result: ChaosTestResult):
    portfolio_value = await get_portfolio_value()
    proposal: TradeProposal = chaos_result.refined_proposal
    
    # order_details never actually has an "amount" key - ai-strategy's real
    # proposals carry quantity/limit_price/contract_multiplier instead
    # (same shape workflow/pipeline.py's own _notional_value() reads), so
    # this was silently always 0.0 and the allocation check never fired.
    details = proposal.order_details
    trade_amount = (
        float(details.get("quantity", 0))
        * float(details.get("limit_price", 0))
        * float(details.get("contract_multiplier", 100))
    )
    # chaos-sandbox computes this (ChaosTestResult.net_delta) - a
    # delta-equivalent-shares number, e.g. +85 behaves like being long 85
    # shares. Comparing that raw number against a fixed threshold isn't
    # meaningful on its own: 85 "shares" of a $14 stock and 85 "shares" of
    # a $330 stock are wildly different real risk. Normalized the same way
    # check_allocation_limit already normalizes trade_amount - as
    # delta-dollar exposure relative to portfolio value - so one threshold
    # means the same thing regardless of which ticker it's checking.
    trade_delta = chaos_result.net_delta or 0.0
    delta_dollars = trade_delta * float(details.get("spot_price", 0.0))
    delta_pct_of_portfolio = delta_dollars / portfolio_value if portfolio_value else 0.0
    current_portfolio_delta_pct = 0.0

    rules_to_check = [
        check_chaos_safety(chaos_result.is_safe),
        check_allocation_limit(trade_amount, portfolio_value, settings.max_allocation_pct),
        check_conviction_score(proposal.conviction_score, settings.min_conviction_score),
        check_delta_limit(delta_pct_of_portfolio, current_portfolio_delta_pct, settings.max_portfolio_delta)
    ]
    
    failed_reasons = [reason for passed, reason in rules_to_check if not passed]
    
    if failed_reasons:
        return RiskResult(
            is_approved=False,
            veto_reason=" | ".join(failed_reasons),
            final_proposal=None
        )
            
    return RiskResult(
        is_approved=True,
        veto_reason=None,
        final_proposal=proposal
    )