"""
Shared domain contracts for Aegis-OptionAI.

These Pydantic v2 models are the single source of truth for the shape of data
exchanged between microservices. Every service imports from here instead of
redefining its own copy — if a field needs to change, it changes once, here.

`chain_summary` and `order_details` are intentionally typed as loose `dict`
fields rather than nested strict models: the real Alpaca MCP tool schemas
have not been verified against this contract yet, so these two fields are
the deliberate "expansion joints"that let each service attach extra keys
later without breaking every other service's Pydantic validation.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# Borsa servisinin piyasadan topladığı ham veri
class MarketContext(BaseModel):
    ticker: str
    spot_price: float
    implied_volatility: float
    chain_summary: dict = Field(default_factory=dict)
    timestamp: str

# Ai ürettiği işlem teklifi
class TradeProposal(BaseModel):
    strategy_id: str
    action: Literal["BUY", "SELL", "HOLD"]
    symbol: str
    generated_code: str
    conviction_score: float
    order_details: dict = Field(default_factory=dict)

# Kod stres testinden geçti mi (is_safe)
class ChaosTestResult(BaseModel):
    is_safe: bool
    stress_score: float
    logs: List[str] = Field(default_factory=list)
    refined_proposal: TradeProposal

# Risk motoru kararı
class RiskResult(BaseModel):
    is_approved: bool
    veto_reason: Optional[str] = None
    final_proposal: Optional[TradeProposal] = None

# Borsaya iletilen emrin sonucu
class ExecutionResponse(BaseModel):
    status: str
    order_id: str
    filled_avg_price: float
    timestamp: str
