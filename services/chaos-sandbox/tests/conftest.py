import pytest

from contracts.schemas import TradeProposal
from chaos_sandbox.settings import Settings


@pytest.fixture(autouse=True)
def clean_settings_environment(monkeypatch):
    for name in (
        "CHAOS_MAX_STRESS_LOSS_PCT",
        "CHAOS_ADVERSE_PRICE_MOVE_PCT",
        "CHAOS_SPREAD_WIDENING_MULTIPLIER",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def order_details():
    return {
        "option_symbol": "AAPL261016C00190000",
        "option_type": "call",
        "quantity": 1,
        "limit_price": 5.10,
        "spot_price": 189.50,
        "strike": 190.00,
        "implied_volatility": 0.27,
        "days_to_expiry": 30,
        "bid": 5.00,
        "ask": 5.20,
        "risk_free_rate": 0.04,
        "contract_multiplier": 100,
        "delta": 0.52,
    }


@pytest.fixture
def proposal(order_details):
    return TradeProposal(
        strategy_id="dialectic-v1", action="BUY", symbol="AAPL",
        generated_code="", conviction_score=0.82, order_details=order_details,
    )


@pytest.fixture
def settings():
    return Settings()
