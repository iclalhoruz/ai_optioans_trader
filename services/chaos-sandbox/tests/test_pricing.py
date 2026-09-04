import math

import pytest

from chaos_sandbox.pricing import black_scholes_delta, black_scholes_price


def price(**overrides):
    return black_scholes_price(**{
        "spot": 100, "strike": 100, "time_to_expiry": 1,
        "risk_free_rate": 0.05, "volatility": 0.20, "option_type": "call",
        **overrides,
    })


def delta(**overrides):
    return black_scholes_delta(**{
        "spot": 100, "strike": 100, "time_to_expiry": 1,
        "risk_free_rate": 0.05, "volatility": 0.20, "option_type": "call",
        **overrides,
    })


@pytest.mark.parametrize("option_type,expected", [("call", 10.4506), ("put", 5.5735)])
def test_known_reference_price(option_type, expected):
    assert price(option_type=option_type) == pytest.approx(expected, abs=0.00005)


@pytest.mark.parametrize("option_type,expected", [("call", 0.63683), ("put", -0.36317)])
def test_known_reference_delta(option_type, expected):
    assert delta(option_type=option_type) == pytest.approx(expected, abs=0.00001)


@pytest.mark.parametrize("option_type,spot,expected", [
    ("call", 1000, 1.0),
    ("call", 10, 0.0),
    ("put", 10, -1.0),
    ("put", 1000, 0.0),
])
def test_deep_itm_and_otm_delta_limits(option_type, spot, expected):
    assert delta(option_type=option_type, spot=spot, risk_free_rate=0) == pytest.approx(
        expected, abs=1e-9,
    )


def test_atm_call_and_put_deltas_are_near_half_and_mirror_each_other():
    inputs = {"spot": 100, "strike": 100, "time_to_expiry": 1 / 365,
              "risk_free_rate": 0, "volatility": 0.20}
    call_delta = delta(**inputs, option_type="call")
    put_delta = delta(**inputs, option_type="put")
    assert call_delta == pytest.approx(0.5, abs=0.003)
    assert put_delta == pytest.approx(-0.5, abs=0.003)
    assert call_delta - put_delta == pytest.approx(1.0)


@pytest.mark.parametrize("option_type,spot,expected", [
    ("call", 120, 20), ("call", 80, 0), ("call", 100, 0),
    ("put", 80, 20), ("put", 120, 0), ("put", 100, 0),
])
def test_zero_expiry_is_intrinsic(option_type, spot, expected):
    assert price(option_type=option_type, spot=spot, time_to_expiry=0) == expected


@pytest.mark.parametrize("option_type,spot,expected", [
    ("call", 120, 1.0), ("call", 80, 0.0), ("call", 100, 0.5),
    ("put", 80, -1.0), ("put", 120, 0.0), ("put", 100, -0.5),
])
def test_zero_expiry_delta_is_intrinsic_slope(option_type, spot, expected):
    assert delta(option_type=option_type, spot=spot, time_to_expiry=0) == expected


@pytest.mark.parametrize("volatility", [0.0, 1e-16])
@pytest.mark.parametrize("option_type", ["call", "put"])
def test_negligible_volatility_is_discounted_payoff(volatility, option_type):
    sign = 1 if option_type == "call" else -1
    expected = max(0, sign * (100 - 100 * math.exp(-0.05)))
    assert price(volatility=volatility, option_type=option_type) == pytest.approx(expected)


@pytest.mark.parametrize("option_type,spot,expected", [
    ("call", 110, 1.0), ("call", 90, 0.0),
    ("put", 90, -1.0), ("put", 110, 0.0),
])
def test_negligible_volatility_delta_matches_discounted_payoff_slope(option_type, spot, expected):
    assert delta(option_type=option_type, spot=spot, volatility=0) == expected


@pytest.mark.parametrize("option_type", ["call", "put"])
@pytest.mark.parametrize("spot", [0, 1, 100, 10000])
def test_finite_nonnegative_price(option_type, spot):
    result = price(option_type=option_type, spot=spot)
    assert math.isfinite(result) and result >= 0


@pytest.mark.parametrize("option_type", ["call", "put"])
@pytest.mark.parametrize("spot", [80, 100, 120])
def test_lower_iv_does_not_increase_long_value(option_type, spot):
    assert price(option_type=option_type, spot=spot, volatility=0.04) <= price(option_type=option_type, spot=spot)


def test_put_call_parity():
    assert price() - price(option_type="put") == pytest.approx(100 - 100 * math.exp(-0.05))


@pytest.mark.parametrize("overrides", [
    {"option_type": "straddle"}, {"spot": -1}, {"strike": 0},
    {"time_to_expiry": -1}, {"volatility": -0.1},
    {"spot": math.inf}, {"risk_free_rate": math.nan},
])
def test_invalid_pricing_inputs(overrides):
    with pytest.raises(ValueError):
        price(**overrides)
    with pytest.raises(ValueError):
        delta(**overrides)
