from pydantic import BaseModel
from typing import Optional, List

class ChaosResult(BaseModel):
    is_safe: bool
    survival_score: float

class TradeProposal(BaseModel):
    action: str
    amount: float
    conviction_score: float
    trade_delta: float
    chaos_result: ChaosResult

class EvaluationResponse(BaseModel):
    approved: bool
    reasons: Optional[List[str]] = []