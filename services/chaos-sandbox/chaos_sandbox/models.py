"""Strict service-local inputs, leaving shared wire contracts unchanged."""

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    ValidationInfo,
    field_validator,
)

OptionType = Literal["call", "put"]
ScenarioName = Literal["SPREAD_SHOCK", "IV_CRUSH", "ADVERSE_MOVE"]


class OptionStressInputs(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False, frozen=True)

    option_symbol: str | None = None
    option_type: OptionType
    quantity: PositiveInt
    limit_price: PositiveFloat
    spot_price: PositiveFloat
    strike: PositiveFloat
    implied_volatility: float = Field(gt=0, le=5)
    days_to_expiry: NonNegativeInt
    bid: NonNegativeFloat
    ask: PositiveFloat
    risk_free_rate: float = 0.04
    contract_multiplier: PositiveInt = 100
    delta: float | None = None

    @field_validator("ask")
    @classmethod
    def ask_must_cover_bid(cls, value: float, info: ValidationInfo) -> float:
        bid = info.data.get("bid")
        if bid is not None and value < bid:
            raise ValueError("ask must be greater than or equal to bid")
        return value


class ScenarioResult(BaseModel):
    """Full precision results used internally and formatted for frontend logs."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: ScenarioName
    spot_price: NonNegativeFloat
    strike: PositiveFloat
    implied_volatility: NonNegativeFloat
    days_to_expiry: NonNegativeInt
    risk_free_rate: float
    spread: NonNegativeFloat
    theoretical_price: NonNegativeFloat
    estimated_exit_price: NonNegativeFloat
    entry_total: PositiveFloat
    exit_total: NonNegativeFloat
    pnl: float
    loss_pct: float = Field(ge=0, le=1)
