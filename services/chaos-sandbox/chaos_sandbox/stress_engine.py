"""Independent fixed shocks for single-leg long options."""

import math
from dataclasses import dataclass

from contracts.interfaces import BaseChaosSandbox
from contracts.schemas import ChaosTestResult, TradeProposal

from chaos_sandbox.models import (
    OptionStressInputs,
    ScenarioName,
    ScenarioResult,
    SpreadLegScenarioResult,
    SpreadScenarioResult,
    SpreadStressInputs,
    option_underlying,
    parse_stress_inputs,
)
from chaos_sandbox.pricing import black_scholes_delta, black_scholes_price
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


def calculate_spread_scenarios(
    inputs: SpreadStressInputs, settings: Settings,
) -> tuple[SpreadScenarioResult, ...]:
    """Reprice every leg, then measure the stressed net liquidation value."""
    if inputs.limit_price <= 0:
        raise ValueError("spread stress calculation requires a positive net debit")
    units = inputs.quantity * inputs.contract_multiplier
    entry_total = inputs.limit_price * units
    if not math.isfinite(entry_total) or entry_total <= 0:
        raise ValueError("spread entry cost must be finite and positive")

    adverse_factor = 1 - settings.adverse_price_move_pct if inputs.direction == "bullish" else 1 + settings.adverse_price_move_pct
    shocks: tuple[tuple[ScenarioName, float, float, float], ...] = (
        ("SPREAD_SHOCK", inputs.spot_price, 1.0, settings.spread_widening_multiplier),
        ("IV_CRUSH", inputs.spot_price, 0.20, 1.0),
        ("ADVERSE_MOVE", inputs.spot_price * adverse_factor, 1.0, 1.0),
    )

    results: list[SpreadScenarioResult] = []
    for name, spot, iv_factor, spread_factor in shocks:
        leg_results: list[SpreadLegScenarioResult] = []
        theoretical_net = 0.0
        estimated_exit_price = 0.0
        for leg in inputs.legs:
            iv = leg.implied_volatility * iv_factor
            spread = (leg.ask - leg.bid) * spread_factor
            theoretical = black_scholes_price(
                spot=spot,
                strike=leg.strike,
                time_to_expiry=leg.days_to_expiry / 365,
                volatility=iv,
                risk_free_rate=inputs.risk_free_rate,
                option_type=leg.option_type,
            )
            sign = 1 if leg.side == "buy" else -1
            if name == "SPREAD_SHOCK":
                liquidation_price = (
                    max(0.0, theoretical - spread / 2)
                    if sign > 0
                    else theoretical + spread / 2
                )
            else:
                liquidation_price = theoretical
            signed_contribution = sign * liquidation_price * leg.ratio_qty
            theoretical_net += sign * theoretical * leg.ratio_qty
            estimated_exit_price += signed_contribution
            leg_results.append(SpreadLegScenarioResult(
                option_symbol=leg.option_symbol,
                option_type=leg.option_type,
                side=leg.side,
                ratio_qty=leg.ratio_qty,
                strike=leg.strike,
                implied_volatility=iv,
                days_to_expiry=leg.days_to_expiry,
                spread=spread,
                theoretical_price=theoretical,
                estimated_liquidation_price=liquidation_price,
                signed_contribution=signed_contribution,
            ))

        exit_total = estimated_exit_price * units
        pnl = exit_total - entry_total
        loss_pct = max(0.0, (entry_total - exit_total) / entry_total)
        results.append(SpreadScenarioResult(
            name=name,
            spot_price=spot,
            legs=leg_results,
            theoretical_price=theoretical_net,
            estimated_exit_price=estimated_exit_price,
            entry_total=entry_total,
            exit_total=exit_total,
            pnl=pnl,
            loss_pct=loss_pct,
        ))
    return tuple(results)


def calculate_spread_net_delta(inputs: SpreadStressInputs) -> float:
    """Return the spread's current exposure in underlying-share equivalents."""
    per_contract_delta = sum(
        (1 if leg.side == "buy" else -1)
        * leg.ratio_qty
        * black_scholes_delta(
            spot=inputs.spot_price,
            strike=leg.strike,
            time_to_expiry=leg.days_to_expiry / 365,
            volatility=leg.implied_volatility,
            risk_free_rate=inputs.risk_free_rate,
            option_type=leg.option_type,
        )
        for leg in inputs.legs
    )
    net_delta = per_contract_delta * inputs.quantity * inputs.contract_multiplier
    if not math.isfinite(net_delta):
        raise ValueError("spread net delta must be finite")
    return net_delta


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


def _spread_scenario_log(
    result: SpreadScenarioResult, inputs: SpreadStressInputs, settings: Settings,
) -> str:
    if result.name == "SPREAD_SHOCK":
        change = f"each leg bid-ask spread widened {settings.spread_widening_multiplier:.2f}x"
    elif result.name == "IV_CRUSH":
        change = "each leg IV reduced to 20.0% of its original value"
    else:
        change = f"{inputs.direction} spread spot moved from {inputs.spot_price:.4f} to {result.spot_price:.4f}"
    legs = "; ".join(
        f"{leg.side} {leg.ratio_qty}x {leg.option_symbol} "
        f"(K={leg.strike:.4f}, IV={leg.implied_volatility:.2%}, DTE={leg.days_to_expiry}, "
        f"theoretical=${leg.theoretical_price:.4f}, liquidation=${leg.estimated_liquidation_price:.4f}, "
        f"net=${leg.signed_contribution:.4f})"
        for leg in result.legs
    )
    return (
        f"{result.name}: {change}; legs=[{legs}]; "
        f"net theoretical=${result.theoretical_price:.4f}, estimated net exit=${result.estimated_exit_price:.4f}; "
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
        inputs = parse_stress_inputs(proposal.order_details)
        net_delta: float | None = None
        if isinstance(inputs, SpreadStressInputs):
            net_delta = calculate_spread_net_delta(inputs)
            if any(option_underlying(leg.option_symbol) != proposal.symbol.upper() for leg in inputs.legs):
                return ChaosTestResult(
                    is_safe=False,
                    stress_score=1.0,
                    logs=["VETO: every spread leg must use the proposal's underlying symbol"],
                    refined_proposal=proposal,
                    net_delta=net_delta,
                )
            if inputs.limit_price < 0:
                return ChaosTestResult(
                    is_safe=False,
                    stress_score=1.0,
                    logs=["VETO: net-credit spreads require a maximum-loss or margin model and are not supported"],
                    refined_proposal=proposal,
                    net_delta=net_delta,
                )
            if any(leg.position_intent.endswith("_to_close") for leg in inputs.legs):
                return ChaosTestResult(
                    is_safe=False,
                    stress_score=1.0,
                    logs=["VETO: closing and rolling spread legs require current-position cost basis and are not supported"],
                    refined_proposal=proposal,
                    net_delta=net_delta,
                )
            results = calculate_spread_scenarios(inputs, self.settings)
            logs = [_spread_scenario_log(result, inputs, self.settings) for result in results]
        else:
            results = calculate_scenarios(inputs, self.settings)
            logs = [_scenario_log(result, inputs) for result in results]
        stress_score = min(1.0, max(result.loss_pct for result in results))
        is_safe = stress_score <= self.settings.max_stress_loss_pct
        decision = "SAFE" if is_safe else "VETO"
        comparison = "is within" if is_safe else "exceeds"
        logs.append(
            f"{decision}: worst-case loss {stress_score:.1%} {comparison} "
            f"the configured {self.settings.max_stress_loss_pct:.1%} limit"
        )
        return ChaosTestResult(
            is_safe=is_safe,
            stress_score=stress_score,
            logs=logs,
            refined_proposal=proposal,
            net_delta=net_delta,
        )
