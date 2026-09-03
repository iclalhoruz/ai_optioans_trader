"""Immutable startup configuration; invalid environment values fail startup."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CHAOS_", frozen=True, allow_inf_nan=False,
    )

    max_stress_loss_pct: float = Field(default=0.35, ge=0, le=1)
    adverse_price_move_pct: float = Field(default=0.10, ge=0, le=1)
    spread_widening_multiplier: float = Field(default=6.0, ge=1)
