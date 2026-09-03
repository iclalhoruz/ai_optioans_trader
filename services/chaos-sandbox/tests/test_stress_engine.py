import asyncio
from copy import deepcopy

import pytest
from pydantic import ValidationError

from contracts.interfaces import BaseChaosSandbox
from chaos_sandbox.models import OptionStressInputs
from chaos_sandbox.pricing import black_scholes_price
from chaos_sandbox.settings import Settings
from chaos_sandbox.stress_engine import ChaosSandbox, calculate_scenarios


def run(proposal, settings):
    return asyncio.run(ChaosSandbox(settings).run_stress_test(proposal))


@pytest.mark.parametrize("option_type,spot_factor", [("call", 0.90), ("put", 1.10)])
def test_shocks_are_independent(order_details, settings, option_type, spot_factor):
    order_details["option_type"] = option_type
    inputs = OptionStressInputs(**order_details)
    spread, iv, adverse = calculate_scenarios(inputs, settings)
    assert spread.spread == pytest.approx((inputs.ask - inputs.bid) * 6)
    assert spread.spot_price == inputs.spot_price
    assert spread.implied_volatility == inputs.implied_volatility
    assert iv.implied_volatility == pytest.approx(inputs.implied_volatility * 0.20)
    assert iv.spot_price == inputs.spot_price
    assert iv.spread == pytest.approx(inputs.ask - inputs.bid)
    assert adverse.spot_price == pytest.approx(inputs.spot_price * spot_factor)
    assert adverse.implied_volatility == inputs.implied_volatility
    assert adverse.spread == pytest.approx(inputs.ask - inputs.bid)
    for result in (spread, iv, adverse):
        assert result.strike == inputs.strike
        assert result.days_to_expiry == inputs.days_to_expiry
        assert result.risk_free_rate == inputs.risk_free_rate
        assert result.theoretical_price == pytest.approx(black_scholes_price(
            spot=result.spot_price, strike=inputs.strike, time_to_expiry=30 / 365,
            volatility=result.implied_volatility, risk_free_rate=inputs.risk_free_rate,
            option_type=option_type,
        ))
    assert spread.estimated_exit_price == pytest.approx(max(0, spread.theoretical_price - spread.spread / 2))
    assert iv.estimated_exit_price == iv.theoretical_price
    assert adverse.estimated_exit_price == adverse.theoretical_price


def test_cost_pnl_and_worst_loss(proposal, settings):
    proposal.order_details.update(quantity=3, contract_multiplier=50)
    results = calculate_scenarios(OptionStressInputs(**proposal.order_details), settings)
    for result in results:
        assert result.entry_total == pytest.approx(5.10 * 3 * 50)
        assert result.exit_total == pytest.approx(result.estimated_exit_price * 3 * 50)
        assert result.pnl == pytest.approx(result.exit_total - result.entry_total)
        assert result.loss_pct == pytest.approx(max(0, -result.pnl / result.entry_total))
    score = run(proposal, settings).stress_score
    assert score == max(result.loss_pct for result in results)
    assert score != pytest.approx(sum(result.loss_pct for result in results) / 3)


def test_threshold_below_equal_above(proposal, settings):
    score = run(proposal, settings).stress_score
    assert 0 < score < 1
    for threshold, expected in ((score - 1e-8, False), (score, True), (score + 1e-8, True)):
        result = run(proposal, Settings(max_stress_loss_pct=threshold))
        assert result.is_safe is expected
        assert result.logs[-1].startswith("SAFE:" if expected else "VETO:")


def test_default_threshold_veto_and_safe_buy(proposal, settings):
    assert not run(proposal, settings).is_safe
    proposal.order_details.update(spot_price=300.0, strike=190.0, limit_price=100.0)
    assert run(proposal, settings).is_safe


@pytest.mark.parametrize("action", ["HOLD", "SELL"])
def test_hold_and_sell_skip_order_validation(proposal, settings, action):
    proposal.action = action
    proposal.order_details = {}
    result = run(proposal, settings)
    assert result.is_safe is (action == "HOLD")
    assert result.stress_score == (0.0 if action == "HOLD" else 1.0)
    if action == "HOLD":
        assert result.logs == ["HOLD: no position will be opened; stress testing skipped"]
    else:
        assert "short-option margin model" in result.logs[-1]
        assert result.logs[-1].startswith("VETO:")
    assert result.refined_proposal == proposal


def test_empty_buy_is_invalid(proposal, settings):
    proposal.order_details = {}
    with pytest.raises(ValidationError):
        run(proposal, settings)


def test_crossed_quote_is_invalid(proposal, settings):
    proposal.order_details.update(ask=4.0, bid=5.0)
    with pytest.raises(ValidationError, match="ask must be greater than or equal to bid"):
        run(proposal, settings)


def test_zero_spread(order_details, settings):
    order_details["bid"] = order_details["ask"]
    spread, *_ = calculate_scenarios(OptionStressInputs(**order_details), settings)
    assert spread.spread == 0
    assert spread.estimated_exit_price == spread.theoretical_price


def test_exit_price_cannot_be_negative(proposal, settings):
    proposal.order_details.update(bid=0.0, ask=100.0)
    spread, *_ = calculate_scenarios(OptionStressInputs(**proposal.order_details), settings)
    assert spread.estimated_exit_price == spread.exit_total == 0
    assert spread.loss_pct == 1
    assert run(proposal, settings).stress_score == 1


def test_100_percent_adverse_call_move(order_details):
    *_, adverse = calculate_scenarios(OptionStressInputs(**order_details), Settings(adverse_price_move_pct=1))
    assert adverse.spot_price == adverse.theoretical_price == adverse.exit_total == 0
    assert adverse.loss_pct == 1


def test_zero_dte_and_gains_have_zero_loss(order_details, settings):
    order_details.update(days_to_expiry=0, spot_price=300.0, limit_price=1.0)
    for scenario in calculate_scenarios(OptionStressInputs(**order_details), settings):
        assert scenario.pnl > 0
        assert scenario.loss_pct == 0
        assert scenario.theoretical_price == max(scenario.spot_price - 190.0, 0)


def test_deterministic_unmodified_proposal(proposal, settings):
    original = deepcopy(proposal.model_dump())
    engine = ChaosSandbox(settings)
    assert isinstance(engine, BaseChaosSandbox)
    first = run(proposal, settings)
    for _ in range(3):
        assert run(proposal, settings).model_dump() == first.model_dump()
    assert proposal.model_dump() == original
    assert first.refined_proposal.model_dump() == original
    assert len(first.logs) == 4
    for log in first.logs[:3]:
        for label in ("spot=", "strike=", "IV=", "DTE=", "rate=", "theoretical price=", "estimated exit price=", "entry=", "exit=", "PnL=", "estimated loss"):
            assert label in log


def test_only_documented_optional_defaults(order_details):
    for key in ("option_symbol", "delta", "risk_free_rate", "contract_multiplier"):
        order_details.pop(key)
    inputs = OptionStressInputs(**order_details)
    assert inputs.option_symbol is inputs.delta is None
    assert inputs.risk_free_rate == 0.04
    assert inputs.contract_multiplier == 100


@pytest.mark.parametrize("field,value", [
    ("quantity", 0), ("quantity", 1.5), ("quantity", True), ("quantity", "1"),
    ("limit_price", 0), ("limit_price", "5.1"), ("limit_price", True),
    ("spot_price", 0), ("strike", -1), ("days_to_expiry", -1), ("days_to_expiry", 1.5),
    ("bid", -1), ("ask", 0), ("contract_multiplier", 0), ("contract_multiplier", 1.5),
    ("implied_volatility", 0), ("implied_volatility", 5.01),
    ("implied_volatility", float("nan")), ("risk_free_rate", float("inf")),
    ("delta", float("nan")), ("option_type", "CALL"), ("extra_field", 1),
])
def test_strict_invalid_inputs(order_details, field, value):
    order_details[field] = value
    with pytest.raises(ValidationError):
        OptionStressInputs(**order_details)


@pytest.mark.parametrize("field,value", [
    ("max_stress_loss_pct", -0.1), ("max_stress_loss_pct", 1.1),
    ("adverse_price_move_pct", -0.1), ("adverse_price_move_pct", 1.1),
    ("spread_widening_multiplier", 0.99), ("spread_widening_multiplier", "inf"),
    ("max_stress_loss_pct", "nan"), ("adverse_price_move_pct", "invalid"),
])
def test_invalid_environment(monkeypatch, field, value):
    monkeypatch.setenv("CHAOS_" + field.upper(), str(value))
    with pytest.raises(ValidationError):
        Settings()


def test_environment_affects_scenarios_and_decision(monkeypatch, proposal):
    monkeypatch.setenv("CHAOS_MAX_STRESS_LOSS_PCT", "1")
    monkeypatch.setenv("CHAOS_ADVERSE_PRICE_MOVE_PCT", "0.25")
    monkeypatch.setenv("CHAOS_SPREAD_WIDENING_MULTIPLIER", "2")
    configured = Settings()
    spread, _, adverse = calculate_scenarios(OptionStressInputs(**proposal.order_details), configured)
    assert spread.spread == pytest.approx(0.4)
    assert adverse.spot_price == pytest.approx(189.5 * 0.75)
    assert run(proposal, configured).is_safe


@pytest.mark.parametrize("boundary", [0, 1])
def test_settings_accept_ratio_boundaries(boundary):
    Settings(max_stress_loss_pct=boundary, adverse_price_move_pct=boundary, spread_widening_multiplier=1)
