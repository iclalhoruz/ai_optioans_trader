"""European, non-dividend option pricing using only the standard library."""

import math
from typing import Literal


def black_scholes_price(
    *,
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float,
    option_type: Literal["call", "put"],
) -> float:
    """Price per underlying unit; zero time returns intrinsic value.

    Zero spot is allowed for the configured 100% adverse call move. At
    negligible total volatility, use the discounted deterministic payoff.
    Unrepresentable calculations raise instead of producing a safe score.
    """
    if option_type not in ("call", "put"):
        raise ValueError("option_type must be call or put")
    if not all(math.isfinite(v) for v in (spot, strike, time_to_expiry, volatility, risk_free_rate)):
        raise ValueError("pricing inputs must be finite")
    if spot < 0 or strike <= 0 or time_to_expiry < 0 or volatility < 0:
        raise ValueError("spot, time and volatility must be nonnegative; strike must be positive")
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
    d1 = (
        math.log(spot) - math.log(strike)
        + (risk_free_rate + volatility * volatility / 2) * time_to_expiry
    ) / sigma_sqrt_t
    d2 = d1 - sigma_sqrt_t

    def cdf(x: float) -> float:
        return (1 + math.erf(x / math.sqrt(2))) / 2

    price = sign * (spot * cdf(sign * d1) - discounted_strike * cdf(sign * d2))
    if not math.isfinite(price):
        raise ValueError("option price is not finite")
    return max(0.0, price)
