import asyncio
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from contracts.schemas import ChaosTestResult, TradeProposal
from chaos_sandbox.main import create_app
from chaos_sandbox.models import SpreadStressInputs, parse_stress_inputs
from chaos_sandbox.pricing import black_scholes_delta, black_scholes_price
from chaos_sandbox.settings import Settings
from chaos_sandbox.stress_engine import (
    ChaosSandbox,
    calculate_spread_net_delta,
    calculate_spread_scenarios,
)


@pytest.fixture
def spread_details():
    return {
        "strategy_type": "call_debit_spread",
        "direction": "bullish",
        "quantity": 1,
        "limit_price": 3.0,
        "spot_price": 100.0,
        "risk_free_rate": 0.04,
        "contract_multiplier": 100,
        "legs": [
            {
                "symbol": "TEST261016C00100000",
                "option_type": "call",
                "strike": 100.0,
                "implied_volatility": 0.25,
                "days_to_expiry": 45,
                "bid": 4.9,
                "ask": 5.1,
                "ratio_qty": 1,
                "side": "buy",
                "position_intent": "buy_to_open",
            },
            {
                "symbol": "TEST261016C00110000",
                "option_type": "call",
                "strike": 110.0,
                "implied_volatility": 0.22,
                "days_to_expiry": 45,
                "bid": 1.8,
                "ask": 2.0,
                "ratio_qty": 1,
                "side": "sell",
                "position_intent": "sell_to_open",
            },
        ],
    }


@pytest.fixture
def spread_proposal(spread_details):
    return TradeProposal(
        strategy_id="spread-v1",
        action="BUY",
        symbol="TEST",
        generated_code="",
        conviction_score=0.85,
        order_details=spread_details,
    )


def run(proposal, settings):
    return asyncio.run(ChaosSandbox(settings).run_stress_test(proposal))


def test_spread_input_is_selected_and_symbol_alias_is_accepted(spread_details):
    inputs = parse_stress_inputs(spread_details)
    assert isinstance(inputs, SpreadStressInputs)
    assert inputs.legs[0].option_symbol == "TEST261016C00100000"


def test_each_leg_is_priced_then_netted(spread_details, settings):
    inputs = SpreadStressInputs.model_validate(spread_details)
    spread, iv, adverse = calculate_spread_scenarios(inputs, settings)
    assert len(spread.legs) == len(iv.legs) == len(adverse.legs) == 2
    assert spread.theoretical_price == pytest.approx(
        spread.legs[0].theoretical_price - spread.legs[1].theoretical_price
    )
    assert spread.estimated_exit_price == pytest.approx(
        spread.legs[0].estimated_liquidation_price - spread.legs[1].estimated_liquidation_price
    )
    assert spread.legs[0].signed_contribution > 0
    assert spread.legs[1].signed_contribution < 0


def test_each_leg_uses_its_own_pricing_inputs(spread_details, settings):
    inputs = SpreadStressInputs.model_validate(spread_details)
    first = calculate_spread_scenarios(inputs, settings)[0]
    for expected, leg in zip(first.legs, inputs.legs, strict=True):
        assert expected.theoretical_price == pytest.approx(black_scholes_price(
            spot=inputs.spot_price,
            strike=leg.strike,
            time_to_expiry=leg.days_to_expiry / 365,
            volatility=leg.implied_volatility,
            risk_free_rate=inputs.risk_free_rate,
            option_type=leg.option_type,
        ))


def test_spread_widens_each_leg_with_correct_liquidation_side(spread_details, settings):
    spread = calculate_spread_scenarios(SpreadStressInputs.model_validate(spread_details), settings)[0]
    long_leg, short_leg = spread.legs
    assert long_leg.spread == pytest.approx(1.2)
    assert short_leg.spread == pytest.approx(1.2)
    assert long_leg.estimated_liquidation_price == pytest.approx(
        max(0, long_leg.theoretical_price - long_leg.spread / 2)
    )
    assert short_leg.estimated_liquidation_price == pytest.approx(
        short_leg.theoretical_price + short_leg.spread / 2
    )


def test_iv_crush_applies_to_each_original_leg_iv(spread_details, settings):
    iv = calculate_spread_scenarios(SpreadStressInputs.model_validate(spread_details), settings)[1]
    assert [leg.implied_volatility for leg in iv.legs] == pytest.approx([0.05, 0.044])


@pytest.mark.parametrize("direction,factor", [("bullish", 0.90), ("bearish", 1.10)])
def test_adverse_move_follows_spread_direction(spread_details, settings, direction, factor):
    spread_details["direction"] = direction
    adverse = calculate_spread_scenarios(SpreadStressInputs.model_validate(spread_details), settings)[2]
    assert adverse.spot_price == pytest.approx(spread_details["spot_price"] * factor)


def test_spread_pnl_score_decision_and_proposal_preservation(spread_proposal, settings):
    original = deepcopy(spread_proposal.model_dump())
    scenarios = calculate_spread_scenarios(
        SpreadStressInputs.model_validate(spread_proposal.order_details), settings,
    )
    result = run(spread_proposal, settings)
    assert result.stress_score == pytest.approx(min(1, max(item.loss_pct for item in scenarios)))
    assert result.is_safe is (result.stress_score <= settings.max_stress_loss_pct)
    assert result.refined_proposal.model_dump() == original
    assert spread_proposal.model_dump() == original
    assert result.net_delta == pytest.approx(calculate_spread_net_delta(
        SpreadStressInputs.model_validate(spread_proposal.order_details),
    ))
    assert [log.split(":", 1)[0] for log in result.logs] == [
        "SPREAD_SHOCK", "IV_CRUSH", "ADVERSE_MOVE", "VETO",
    ]
    assert "legs=[buy" in result.logs[0]
    assert "sell" in result.logs[0]


def test_safe_spread_result_includes_net_delta(spread_proposal):
    result = run(spread_proposal, Settings(max_stress_loss_pct=1.0))
    assert result.is_safe is True
    assert result.logs[-1].startswith("SAFE:")
    assert result.net_delta == pytest.approx(calculate_spread_net_delta(
        SpreadStressInputs.model_validate(spread_proposal.order_details),
    ))


def test_ratio_quantity_changes_signed_net_contribution(spread_details, settings):
    spread_details["legs"][0]["ratio_qty"] = 2
    result = calculate_spread_scenarios(SpreadStressInputs.model_validate(spread_details), settings)[1]
    long_leg = result.legs[0]
    assert long_leg.signed_contribution == pytest.approx(2 * long_leg.theoretical_price)


def test_net_delta_uses_leg_side_ratio_quantity_and_multiplier(spread_details):
    spread_details["quantity"] = 3
    spread_details["contract_multiplier"] = 50
    spread_details["legs"][0]["ratio_qty"] = 2
    inputs = SpreadStressInputs.model_validate(spread_details)
    leg_deltas = [black_scholes_delta(
        spot=inputs.spot_price,
        strike=leg.strike,
        time_to_expiry=leg.days_to_expiry / 365,
        volatility=leg.implied_volatility,
        risk_free_rate=inputs.risk_free_rate,
        option_type=leg.option_type,
    ) for leg in inputs.legs]
    expected = (2 * leg_deltas[0] - leg_deltas[1]) * 3 * 50
    assert calculate_spread_net_delta(inputs) == pytest.approx(expected)


def test_narrow_call_vertical_has_small_net_delta(spread_details):
    spread_details["legs"][0].update(implied_volatility=0.25)
    spread_details["legs"][1].update(
        symbol="TEST261016C00101000",
        strike=101.0,
        implied_volatility=0.25,
    )
    net_delta = calculate_spread_net_delta(SpreadStressInputs.model_validate(spread_details))
    assert 0 < net_delta < 10


def test_wide_vertical_with_far_otm_short_leg_tracks_long_leg_delta(spread_details):
    spread_details["legs"][1].update(
        symbol="TEST261016C00160000",
        strike=160.0,
    )
    inputs = SpreadStressInputs.model_validate(spread_details)
    long_leg = inputs.legs[0]
    long_delta = black_scholes_delta(
        spot=inputs.spot_price,
        strike=long_leg.strike,
        time_to_expiry=long_leg.days_to_expiry / 365,
        volatility=long_leg.implied_volatility,
        risk_free_rate=inputs.risk_free_rate,
        option_type=long_leg.option_type,
    ) * inputs.quantity * inputs.contract_multiplier
    net_delta = calculate_spread_net_delta(inputs)
    assert net_delta == pytest.approx(long_delta, abs=0.01)


@pytest.mark.parametrize("leg_count", [1, 5])
def test_spread_requires_two_to_four_legs(spread_details, leg_count):
    spread_details["legs"] = [deepcopy(spread_details["legs"][0]) for _ in range(leg_count)]
    with pytest.raises(ValidationError):
        SpreadStressInputs.model_validate(spread_details)


def test_missing_leg_pricing_field_is_rejected(spread_details):
    del spread_details["legs"][1]["implied_volatility"]
    with pytest.raises(ValidationError):
        SpreadStressInputs.model_validate(spread_details)


def test_leg_side_must_match_position_intent(spread_details):
    spread_details["legs"][1]["position_intent"] = "buy_to_open"
    with pytest.raises(ValidationError, match="side must match position_intent"):
        SpreadStressInputs.model_validate(spread_details)


@pytest.mark.parametrize("field,value,message", [
    ("symbol", "not-an-option", "OCC format"),
    ("option_type", "put", "option_type must match"),
    ("strike", 101.0, "strike must match"),
])
def test_leg_contract_metadata_must_match_symbol(spread_details, field, value, message):
    spread_details["legs"][0][field] = value
    with pytest.raises(ValidationError, match=message):
        SpreadStressInputs.model_validate(spread_details)


def test_unbounded_or_negative_payoff_debit_basket_is_rejected(spread_details):
    spread_details["legs"][1]["ratio_qty"] = 2
    with pytest.raises(ValidationError, match="unbounded loss|payoff cannot be negative"):
        SpreadStressInputs.model_validate(spread_details)


def test_debit_opening_legs_require_same_expiry(spread_details):
    spread_details["legs"][1]["days_to_expiry"] = 60
    with pytest.raises(ValidationError, match="same days_to_expiry"):
        SpreadStressInputs.model_validate(spread_details)


def test_credit_spread_is_valid_but_fail_closed(spread_proposal, settings):
    spread_proposal.order_details["limit_price"] = -1.25
    result = run(spread_proposal, settings)
    assert result.is_safe is False
    assert result.stress_score == 1
    assert result.net_delta is not None
    assert "net-credit spreads" in result.logs[0]


def test_closing_or_rolling_spread_is_valid_but_fail_closed(spread_proposal, settings):
    spread_proposal.order_details["legs"][0].update(
        side="sell", position_intent="sell_to_close",
    )
    result = run(spread_proposal, settings)
    assert result.is_safe is False
    assert result.stress_score == 1
    assert result.net_delta is not None
    assert "closing and rolling" in result.logs[0]


def test_mismatched_underlying_is_fail_closed(spread_proposal, settings):
    spread_proposal.order_details["legs"][1]["symbol"] = "MSFT261016C00110000"
    result = run(spread_proposal, settings)
    assert result.is_safe is False
    assert result.stress_score == 1
    assert result.net_delta is not None
    assert "underlying symbol" in result.logs[0]


def test_spread_api_response_matches_shared_contract(spread_proposal, settings):
    with TestClient(create_app(settings)) as client:
        response = client.post("/stress-test", json=spread_proposal.model_dump())
    assert response.status_code == 200
    result = ChaosTestResult.model_validate(response.json())
    assert result.refined_proposal == spread_proposal
    assert result.net_delta is not None
    assert len(result.logs) == 4


def test_invalid_spread_api_returns_leg_location(spread_proposal, settings):
    del spread_proposal.order_details["legs"][0]["strike"]
    with TestClient(create_app(settings)) as client:
        response = client.post("/stress-test", json=spread_proposal.model_dump())
    assert response.status_code == 422
    location = response.json()["detail"][0]["loc"]
    assert location == ["body", "order_details", "legs", 0, "strike"]


def test_spread_is_deterministic(spread_proposal, settings):
    first = run(spread_proposal, settings).model_dump()
    assert all(run(spread_proposal, settings).model_dump() == first for _ in range(3))
