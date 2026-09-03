"""Featherless connection + prompt-shaping knobs, all overridable via .env."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    featherless_api_key: str
    featherless_base_url: str = "https://api.featherless.ai/v1"
    featherless_model: str

    # Proposes defined-risk vertical spreads (bull call / bear put), not
    # naked single-leg options - chaos-sandbox now models multi-leg P&L
    # (services/chaos-sandbox, "Support multi-leg net-debit spread stress
    # tests"). A single deep-ITM long option was checked exhaustively
    # (ITM% x DTE grid, real Black-Scholes) to have NO combination that
    # clears both chaos-sandbox's 35% stress threshold and risk-engine's
    # 5% MAX_ALLOCATION_PCT cap for any of the watchlist's higher-priced
    # tickers - a spread's short leg funds part of the cost and caps the
    # max loss, which is strictly better on both fronts. Verified live with
    # a real AAPL spread search: a 15%-ITM long leg, a short leg targeting
    # ~10% of spot wider (actual width often ends up larger - real strike
    # increments are coarser than the target and spread_max_debit_to_width_
    # ratio below walks to whichever strike keeps the risk/reward sane),
    # ~270 days out, costing ~$2,000-3,000/contract with 20-30% real
    # stress-test margin (vs. a single-leg deep-ITM equivalent costing
    # $10,000+).
    spread_long_itm_pct: float = 0.15
    spread_width_pct: float = 0.10
    spread_target_days_to_expiry: int = 270
    spread_min_days_to_expiry: int = 90
    # Checked live across several real widths on the same AAPL snapshot:
    # narrower spreads (debit consuming ~80% of the width) came back with
    # a stress score close to the 35% veto line (29-31%) - fine on that
    # exact snapshot, but real IV/price move enough between requests that
    # the same-shaped spread failed outright a few minutes later (45.5%).
    # Wider spreads (debit ~65-69% of width) consistently scored better
    # (23-25%) with real margin against that kind of noise. This caps how
    # much of the width the net debit may consume; candidate selection
    # walks to a wider strike instead of accepting a spread that fails it.
    spread_max_debit_to_width_ratio: float = 0.68

    # For sizing a real quantity instead of always proposing 1 spread -
    # broker-gateway/GET /account is the source of truth for portfolio
    # value (matches how risk-engine is supposed to get it too).
    broker_gateway_url: str = "http://localhost:8001"
    # Fraction of portfolio_value risked per trade at full (1.0) conviction,
    # scaled down by the model's actual conviction_score. Kept well under
    # risk-engine's MAX_ALLOCATION_PCT (5% default) so sizing itself isn't
    # the reason a reasonable proposal gets vetoed downstream.
    target_allocation_pct: float = 0.03
    max_contracts_per_trade: int = 5
