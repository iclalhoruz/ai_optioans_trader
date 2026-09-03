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
