"""
Ports for the hexagonal architecture: every microservice's core logic depends
on these abstract base classes, never on a concrete implementation of another
service. Swapping a service's internals (e.g. a mock broker adapter for a
real Alpaca adapter, or one chaos-test strategy for another) means writing a
new subclass here and wiring it in that service's own main.py — nothing else
in the monorepo has to change.
"""

from abc import ABC, abstractmethod

from contracts.schemas import (
    ChaosTestResult,
    ExecutionResponse,
    MarketContext,
    RiskResult,
    TradeProposal,
)


class BaseBrokerGateway(ABC):
    """Port for market data retrieval and order execution against a broker."""

    @abstractmethod
    async def get_market_context(self, ticker: str) -> MarketContext:
        raise NotImplementedError

    @abstractmethod
    async def execute_order(self, proposal: TradeProposal) -> ExecutionResponse:
        raise NotImplementedError


class BaseStrategyEngine(ABC):
    """Port for the AI/agentic layer that turns market data into a trade idea."""

    @abstractmethod
    async def generate_proposal(self, market_context: MarketContext) -> TradeProposal:
        raise NotImplementedError


class BaseChaosSandbox(ABC):
    """Port for executing a proposal's generated code under injected chaos."""

    @abstractmethod
    async def run_stress_test(self, proposal: TradeProposal) -> ChaosTestResult:
        raise NotImplementedError


class BaseRiskEngine(ABC):
    """Port for the deterministic, non-LLM hard-veto risk gate."""

    @abstractmethod
    async def validate_risk(self, chaos_result: ChaosTestResult) -> RiskResult:
        raise NotImplementedError
