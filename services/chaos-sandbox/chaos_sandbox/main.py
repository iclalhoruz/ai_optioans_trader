"""FastAPI transport for the shared TradeProposal / ChaosTestResult contract."""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from contracts.schemas import ChaosTestResult, TradeProposal
from chaos_sandbox.models import parse_stress_inputs
from chaos_sandbox.settings import Settings
from chaos_sandbox.stress_engine import ChaosSandbox

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    engine = ChaosSandbox(settings=settings if settings is not None else Settings())
    application = FastAPI(title="chaos-sandbox", version="1.0.0")

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "chaos-sandbox"}

    @application.post("/stress-test", response_model=ChaosTestResult)
    async def stress_test(proposal: TradeProposal) -> ChaosTestResult:
        # Keep validation failures distinct from internal calculation/model
        # failures. Omit raw input/context: NaN and exception objects are not
        # JSON serializable, and a bad field should never leak an entire body.
        if proposal.action == "BUY":
            try:
                parse_stress_inputs(proposal.order_details)
            except ValidationError as exc:
                errors = [
                    {**error, "loc": ("body", "order_details", *error["loc"])}
                    for error in exc.errors(include_url=False, include_context=False, include_input=False)
                ]
                raise RequestValidationError(errors) from exc
        try:
            return await engine.run_stress_test(proposal)
        except Exception as exc:
            logger.exception("Stress calculation failed")
            raise HTTPException(status_code=500, detail="Stress calculation failed") from exc

    return application


app = create_app()
