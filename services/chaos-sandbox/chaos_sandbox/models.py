"""Strict service-local inputs, leaving shared wire contracts unchanged."""

import math
import re
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    AliasChoices,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    ValidationInfo,
    field_validator,
    model_validator,
)

OptionType = Literal["call", "put"]
ScenarioName = Literal["SPREAD_SHOCK", "IV_CRUSH", "ADVERSE_MOVE"]
PositionSide = Literal["buy", "sell"]
_OPTION_SYMBOL_PATTERN = re.compile(
    r"^(?P<underlying>[A-Z]{1,6})(?P<expiration>\d{6})(?P<kind>[CP])(?P<strike>\d{8})$"
)


def option_underlying(option_symbol: str) -> str | None:
    match = _OPTION_SYMBOL_PATTERN.fullmatch(option_symbol)
    return match.group("underlying") if match else None


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


class SpreadLegInputs(BaseModel):
    """Pricing and execution details for one option in a multi-leg spread."""

    model_config = ConfigDict(
        strict=True, extra="forbid", allow_inf_nan=False, frozen=True,
        populate_by_name=True,
    )

    option_symbol: str = Field(validation_alias=AliasChoices("option_symbol", "symbol"))
    option_type: OptionType
    strike: PositiveFloat
    implied_volatility: float = Field(gt=0, le=5)
    days_to_expiry: NonNegativeInt
    bid: NonNegativeFloat
    ask: PositiveFloat
    ratio_qty: PositiveInt = 1
    side: PositionSide
    position_intent: Literal["buy_to_open", "sell_to_open", "buy_to_close", "sell_to_close"]

    @field_validator("ask")
    @classmethod
    def ask_must_cover_bid(cls, value: float, info: ValidationInfo) -> float:
        bid = info.data.get("bid")
        if bid is not None and value < bid:
            raise ValueError("ask must be greater than or equal to bid")
        return value

    @model_validator(mode="after")
    def side_must_match_position_intent(self) -> "SpreadLegInputs":
        if not self.position_intent.startswith(f"{self.side}_"):
            raise ValueError("side must match position_intent")
        match = _OPTION_SYMBOL_PATTERN.fullmatch(self.option_symbol)
        if match is None:
            raise ValueError("option symbol must use OCC format, for example AAPL261016C00190000")
        symbol_type = "call" if match.group("kind") == "C" else "put"
        if symbol_type != self.option_type:
            raise ValueError("option_type must match the option symbol")
        symbol_strike = int(match.group("strike")) / 1000
        if not math.isclose(symbol_strike, self.strike, rel_tol=0, abs_tol=1e-9):
            raise ValueError("strike must match the option symbol")
        return self


class SpreadStressInputs(BaseModel):
    """A net-priced option basket; positive limit_price means net debit."""

    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False, frozen=True)

    strategy_type: str | None = None
    direction: Literal["bullish", "bearish"]
    quantity: PositiveInt
    limit_price: float
    spot_price: PositiveFloat
    risk_free_rate: float = 0.04
    contract_multiplier: PositiveInt = 100
    time_in_force: str = "day"
    legs: Annotated[list[SpreadLegInputs], Field(min_length=2, max_length=4)]

    @field_validator("limit_price")
    @classmethod
    def limit_price_must_be_nonzero(cls, value: float) -> float:
        if value == 0:
            raise ValueError("limit_price must be nonzero; positive is debit and negative is credit")
        return value

    @model_validator(mode="after")
    def debit_opening_basket_must_have_bounded_loss(self) -> "SpreadStressInputs":
        # Credit and closing/rolling baskets are parsed so the engine can
        # return an explicit fail-closed risk result. This bounded-payoff
        # check applies to debit opening baskets that can be stress tested.
        if self.limit_price < 0 or any(leg.position_intent.endswith("_to_close") for leg in self.legs):
            return self
        expiries = {leg.days_to_expiry for leg in self.legs}
        if len(expiries) != 1:
            raise ValueError("net-debit opening spread legs must have the same days_to_expiry")

        def expiry_payoff(spot: float) -> float:
            total = 0.0
            for leg in self.legs:
                sign = 1 if leg.side == "buy" else -1
                intrinsic = (
                    max(spot - leg.strike, 0.0)
                    if leg.option_type == "call"
                    else max(leg.strike - spot, 0.0)
                )
                total += sign * leg.ratio_qty * intrinsic
            return total

        breakpoints = [0.0, *(leg.strike for leg in self.legs)]
        if min(expiry_payoff(spot) for spot in breakpoints) < -1e-10:
            raise ValueError("net-debit spread payoff cannot be negative at expiry")
        call_slope = sum(
            (1 if leg.side == "buy" else -1) * leg.ratio_qty
            for leg in self.legs
            if leg.option_type == "call"
        )
        if call_slope < 0:
            raise ValueError("net-debit spread has unbounded loss as spot rises")
        return self


StressInputs = OptionStressInputs | SpreadStressInputs


def parse_stress_inputs(order_details: dict) -> StressInputs:
    """Select the strict local schema without changing the shared contract."""
    model = SpreadStressInputs if "legs" in order_details else OptionStressInputs
    return model.model_validate(order_details)


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


class SpreadLegScenarioResult(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    option_symbol: str
    option_type: OptionType
    side: PositionSide
    ratio_qty: PositiveInt
    strike: PositiveFloat
    implied_volatility: NonNegativeFloat
    days_to_expiry: NonNegativeInt
    spread: NonNegativeFloat
    theoretical_price: NonNegativeFloat
    estimated_liquidation_price: NonNegativeFloat
    signed_contribution: float


class SpreadScenarioResult(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: ScenarioName
    spot_price: NonNegativeFloat
    legs: list[SpreadLegScenarioResult]
    theoretical_price: float
    estimated_exit_price: float
    entry_total: PositiveFloat
    exit_total: float
    pnl: float
    loss_pct: NonNegativeFloat
