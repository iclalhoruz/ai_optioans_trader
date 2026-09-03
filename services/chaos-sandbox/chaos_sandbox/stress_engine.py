"""Independent fixed shocks for single-leg long options."""

import math
from dataclasses import dataclass

from contracts.interfaces import BaseChaosSandbox
from contracts.schemas import ChaosTestResult, TradeProposal

from chaos_sandbox.models import OptionStressInputs, ScenarioName, ScenarioResult
from chaos_sandbox.pricing import black_scholes_price
from chaos_sandbox.settings import Settings


def calculate_scenarios(inputs: OptionStressInputs, settings: Settings) -> tuple[ScenarioResult, ...]:
    """Each scenario starts from the same inputs; no cumulative shocks or time decay."""
    units = inputs.quantity * inputs.contract_multiplier
    entry_total = inputs.limit_price * units
    if not math.isfinite(entry_total) or entry_total <= 0:
        raise ValueError("entry cost must be finite and positive")
    original_spread = inputs.ask - inputs.bid
    adverse_direction = -1 if inputs.option_type == "call" else 1
    shocks: tuple[tuple[ScenarioName, float, float, float], ...] = (
        ("SPREAD_SHOCK", inputs.spot_price, inputs.implied_volatility,
         original_spread * settings.spread_widening_multiplier),
        ("IV_CRUSH", inputs.spot_price, inputs.implied_volatility * 0.20, original_spread),
        ("ADVERSE_MOVE", inputs.spot_price * (1 + adverse_direction * settings.adverse_price_move_pct),
         inputs.implied_volatility, original_spread),
    )
    results: list[ScenarioResult] = []
    for name, spot, iv, spread in shocks:
        if not all(math.isfinite(value) for value in (spot, iv, spread)):
            raise ValueError("stressed inputs must be finite")
        theoretical_price = black_scholes_price(
            spot=spot, strike=inputs.strike, time_to_expiry=inputs.days_to_expiry / 365,
            volatility=iv, risk_free_rate=inputs.risk_free_rate, option_type=inputs.option_type,
        )
        # Only spread widening applies a liquidity haircut. The other two
        # scenarios isolate repricing, using theoretical value as the exit.
        exit_price = max(0.0, theoretical_price - spread / 2) if name == "SPREAD_SHOCK" else theoretical_price
        exit_total = exit_price * units
        results.append(ScenarioResult(
            name=name, spot_price=spot, strike=inputs.strike, implied_volatility=iv,
            days_to_expiry=inputs.days_to_expiry, risk_free_rate=inputs.risk_free_rate,
            spread=spread, theoretical_price=theoretical_price, estimated_exit_price=exit_price,
            entry_total=entry_total, exit_total=exit_total, pnl=exit_total - entry_total,
            loss_pct=max(0.0, (entry_total - exit_total) / entry_total),
        ))
    return tuple(results)


def _scenario_log(result: ScenarioResult, inputs: OptionStressInputs) -> str:
    if result.name == "SPREAD_SHOCK":
        change = f"spread widened from {inputs.ask - inputs.bid:.4f} to {result.spread:.4f}"
    elif result.name == "IV_CRUSH":
        change = f"IV reduced from {inputs.implied_volatility:.1%} to {result.implied_volatility:.1%}"
    else:
        change = f"spot moved from {inputs.spot_price:.4f} to {result.spot_price:.4f}"
    return (
        f"{result.name}: {change}; "
        f"{inputs.option_type}, spot={result.spot_price:.4f}, strike={result.strike:.4f}, "
        f"IV={result.implied_volatility:.2%}, DTE={result.days_to_expiry}, "
        f"rate={result.risk_free_rate:.2%}, spread={result.spread:.4f}; "
        f"theoretical price=${result.theoretical_price:.4f}, estimated exit price=${result.estimated_exit_price:.4f}; "
        f"quantity={inputs.quantity}, multiplier={inputs.contract_multiplier}, "
        f"entry=${result.entry_total:.2f}, exit=${result.exit_total:.2f}, PnL=${result.pnl:.2f}; "
        f"estimated loss {result.loss_pct:.1%} (${max(0.0, -result.pnl):.2f})"
    )


@dataclass(frozen=True)
class ChaosSandbox(BaseChaosSandbox):
    settings: Settings

    async def run_stress_test(self, proposal: TradeProposal) -> ChaosTestResult:
        if proposal.action == "HOLD":
            return ChaosTestResult(
                is_safe=True, stress_score=0.0,
                logs=["HOLD: no position will be opened; stress testing skipped"],
                refined_proposal=proposal,
            )
        if proposal.action == "SELL":
            return ChaosTestResult(
                is_safe=False, stress_score=1.0,
                logs=["VETO: SELL is unsupported; the short-option margin model is not supported"],
                refined_proposal=proposal,
            )
        inputs = OptionStressInputs.model_validate(proposal.order_details)
        results = calculate_scenarios(inputs, self.settings)
        stress_score = min(1.0, max(result.loss_pct for result in results))
        is_safe = stress_score <= self.settings.max_stress_loss_pct
        logs = [_scenario_log(result, inputs) for result in results]
        decision = "SAFE" if is_safe else "VETO"
        comparison = "is within" if is_safe else "exceeds"
        logs.append(
            f"{decision}: worst-case loss {stress_score:.1%} {comparison} "
            f"the configured {self.settings.max_stress_loss_pct:.1%} limit"
        )
        return ChaosTestResult(
            is_safe=is_safe, stress_score=stress_score, logs=logs, refined_proposal=proposal,
        )
