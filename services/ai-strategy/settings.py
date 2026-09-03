"""Featherless connection + prompt-shaping knobs, all overridable via .env."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    featherless_api_key: str
    featherless_base_url: str = "https://api.featherless.ai/v1"
    featherless_model: str

    # How many contracts get shown to the LLM - the raw chain can be 700+
    # contracts, way too many tokens for one prompt.
    contracts_in_prompt: int = 12

    # A single long option is extremely leveraged - checked live with the
    # real Black-Scholes math in chaos_sandbox/pricing.py: an at-the-money
    # call loses 60-100% of its value on chaos-sandbox's 10%-adverse-move
    # scenario regardless of expiry, and even a deep (40%) ITM 30-day call
    # still loses ~25%. Only deep-ITM, long-dated contracts (where the
    # option behaves close to the underlying itself) realistically clear
    # its 35% veto threshold - so the strategy only ever considers
    # contracts at least this deep ITM and at least this many days out,
    # matching broker-gateway's ITM_STRIKE_LOW_PCT/HIGH_PCT/
    # ITM_MIN_DAYS_TO_EXPIRY window (alpaca_client.py) that fetches them.
    target_itm_pct: float = 0.25
    min_days_to_expiry: int = 180
    # Picking the *longest* available expiration per strike (an earlier
    # version of this) maximized stress-test margin but pushed selections
    # out to 2027-2028 - real cost for a deep-ITM contract that far out
    # priced nearly every trade out of a sane risk budget (verified live:
    # AAPL/NVDA both came back "too expensive" at 2% allocation). 365 days
    # still clears chaos-sandbox with real margin (~30% loss vs the 35%
    # veto, per the same pricing grid) without the extra cost of going
    # multiple years out.
    target_days_to_expiry: int = 365

    # For sizing a real quantity instead of always proposing 1 contract -
    # broker-gateway/GET /account is the source of truth for portfolio
    # value (matches how risk-engine is supposed to get it too).
    broker_gateway_url: str = "http://localhost:8001"
    # Fraction of portfolio_value risked per trade at full (1.0) conviction,
    # scaled down by the model's actual conviction_score. Kept well under
    # risk-engine's MAX_ALLOCATION_PCT (5% default) so sizing itself isn't
    # the reason a reasonable proposal gets vetoed downstream.
    target_allocation_pct: float = 0.03
    max_contracts_per_trade: int = 5
