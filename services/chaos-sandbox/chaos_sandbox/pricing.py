"""European, non-dividend option pricing using only the standard library."""

import math
from typing import Literal


OptionType = Literal["call", "put"]


def _validate_inputs(
    *,
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float,
    option_type: OptionType,
) -> None:
    if option_type not in ("call", "put"):
        raise ValueError("option_type must be call or put")
    if not all(math.isfinite(v) for v in (spot, strike, time_to_expiry, volatility, risk_free_rate)):
        raise ValueError("pricing inputs must be finite")
    if spot < 0 or strike <= 0 or time_to_expiry < 0 or volatility < 0:
        raise ValueError("spot, time and volatility must be nonnegative; strike must be positive")


def _normal_cdf(value: float) -> float:
    return (1 + math.erf(value / math.sqrt(2))) / 2


def _intrinsic_slope(*, spot: float, boundary: float, option_type: OptionType) -> float:
    """Return the deterministic payoff slope, symmetric at the strike kink."""
    if spot == boundary:
        return 0.5 if option_type == "call" else -0.5
    if option_type == "call":
        return 1.0 if spot > boundary else 0.0
    return -1.0 if spot < boundary else 0.0


def _d1(
    *,
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float,
    sigma_sqrt_t: float,
) -> float:
    return (
        math.log(spot) - math.log(strike)
        + (risk_free_rate + volatility * volatility / 2) * time_to_expiry
    ) / sigma_sqrt_t


def black_scholes_price(
    *,
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float,
    option_type: OptionType,
) -> float:
    """Price per underlying unit; zero time returns intrinsic value.

    Zero spot is allowed for the configured 100% adverse call move. At
    negligible total volatility, use the discounted deterministic payoff.
    Unrepresentable calculations raise instead of producing a safe score.
    """
    _validate_inputs(
        spot=spot,
        strike=strike,
        time_to_expiry=time_to_expiry,
        volatility=volatility,
        risk_free_rate=risk_free_rate,
        option_type=option_type,
    )
    sign = 1 if option_type == "call" else -1
    if time_to_expiry == 0:
        return max(0.0, sign * (spot - strike))
    discounted_strike = strike * math.exp(-risk_free_rate * time_to_expiry)
    if not math.isfinite(discounted_strike):
        raise ValueError("discounted strike is not finite")
    if spot == 0:
        return 0.0 if option_type == "call" else discounted_strike
    sigma_sqrt_t = volatility * math.sqrt(time_to_expiry)
    if sigma_sqrt_t <= 1e-12:
        return max(0.0, sign * (spot - discounted_strike))
    d1 = _d1(
        spot=spot,
        strike=strike,
        time_to_expiry=time_to_expiry,
        volatility=volatility,
        risk_free_rate=risk_free_rate,
        sigma_sqrt_t=sigma_sqrt_t,
    )
    d2 = d1 - sigma_sqrt_t
    price = sign * (
        spot * _normal_cdf(sign * d1)
        - discounted_strike * _normal_cdf(sign * d2)
    )
    if not math.isfinite(price):
        raise ValueError("option price is not finite")
    return max(0.0, price)


def black_scholes_delta(
    *,
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float,
    option_type: OptionType,
) -> float:
    """Return delta per underlying unit for a European option."""
    _validate_inputs(
        spot=spot,
        strike=strike,
        time_to_expiry=time_to_expiry,
        volatility=volatility,
        risk_free_rate=risk_free_rate,
        option_type=option_type,
    )
    if time_to_expiry == 0:
        return _intrinsic_slope(spot=spot, boundary=strike, option_type=option_type)

    discounted_strike = strike * math.exp(-risk_free_rate * time_to_expiry)
    if not math.isfinite(discounted_strike):
        raise ValueError("discounted strike is not finite")
    sigma_sqrt_t = volatility * math.sqrt(time_to_expiry)
    if spot == 0 or sigma_sqrt_t <= 1e-12:
        return _intrinsic_slope(
            spot=spot,
            boundary=discounted_strike,
            option_type=option_type,
        )

    d1 = _d1(
        spot=spot,
        strike=strike,
        time_to_expiry=time_to_expiry,
        volatility=volatility,
        risk_free_rate=risk_free_rate,
        sigma_sqrt_t=sigma_sqrt_t,
    )
    delta = _normal_cdf(d1)
    if option_type == "put":
        delta -= 1
    if not math.isfinite(delta):
        raise ValueError("option delta is not finite")
    return delta
