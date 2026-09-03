import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from contracts.schemas import ChaosTestResult
from chaos_sandbox.main import create_app
from chaos_sandbox.stress_engine import ChaosSandbox


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "chaos-sandbox"}


@pytest.mark.parametrize("option_type", ["call", "put"])
def test_buy_response_matches_shared_contract(client, proposal, option_type):
    proposal.order_details["option_type"] = option_type
    response = client.post("/stress-test", json=proposal.model_dump())
    assert response.status_code == 200
    result = ChaosTestResult.model_validate(response.json())
    assert result.refined_proposal == proposal
    assert 0 <= result.stress_score <= 1
    assert result.is_safe is False
    assert len(result.logs) == 4
    assert result.logs[-1].startswith("VETO:")


def test_safe_buy(client, proposal):
    proposal.order_details.update(spot_price=300.0, limit_price=100.0)
    response = client.post("/stress-test", json=proposal.model_dump())
    assert response.status_code == 200
    assert response.json()["is_safe"] is True
    assert response.json()["logs"][-1].startswith("SAFE:")


@pytest.mark.parametrize("action,score,safe", [("HOLD", 0, True), ("SELL", 1, False)])
def test_non_buy_without_order_details(client, proposal, action, score, safe):
    payload = proposal.model_dump(exclude={"order_details"})
    payload["action"] = action
    response = client.post("/stress-test", json=payload)
    assert response.status_code == 200
    result = ChaosTestResult.model_validate(response.json())
    assert result.stress_score == score
    assert result.is_safe is safe


@pytest.mark.parametrize("field", [
    "option_type", "quantity", "limit_price", "spot_price", "strike",
    "implied_volatility", "days_to_expiry", "bid", "ask",
])
def test_missing_order_field_returns_field_error(client, proposal, field):
    del proposal.order_details[field]
    response = client.post("/stress-test", json=proposal.model_dump())
    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", "order_details", field]
    assert error["type"] == "missing"


def test_missing_entire_buy_order(client, proposal):
    response = client.post("/stress-test", json=proposal.model_dump(exclude={"order_details"}))
    assert response.status_code == 422


@pytest.mark.parametrize("field,value", [
    ("implied_volatility", 0), ("implied_volatility", -0.1), ("implied_volatility", 5.01),
    ("implied_volatility", "0.27"), ("ask", 4.0), ("quantity", True),
    ("option_type", "future"), ("unsupported", 1),
])
def test_invalid_order_returns_field_error(client, proposal, field, value):
    proposal.order_details[field] = value
    response = client.post("/stress-test", json=proposal.model_dump())
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "order_details", field]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_input_does_not_break_error_serialization(client, proposal, value):
    payload = proposal.model_dump()
    payload["order_details"]["spot_price"] = value
    response = client.post("/stress-test", content=json.dumps(payload), headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "order_details", "spot_price"]


def test_shared_required_field_validation(client, proposal):
    payload = proposal.model_dump(exclude={"generated_code"})
    response = client.post("/stress-test", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "generated_code"]


def test_generated_code_is_inert_and_preserved(client, proposal):
    baseline = client.post("/stress-test", json=proposal.model_dump()).json()
    proposal.generated_code = "raise RuntimeError('generated code must never run')"
    response = client.post("/stress-test", json=proposal.model_dump())
    assert response.status_code == 200
    result = response.json()
    assert result["refined_proposal"] == proposal.model_dump()
    for key in ("stress_score", "is_safe", "logs"):
        assert result[key] == baseline[key]


def test_calculation_error_logged_without_leaking(client, proposal, monkeypatch, caplog):
    async def fail(self, proposal):
        raise RuntimeError("private error details")

    monkeypatch.setattr(ChaosSandbox, "run_stress_test", fail)
    response = client.post("/stress-test", json=proposal.model_dump())
    assert response.status_code == 500
    assert response.json() == {"detail": "Stress calculation failed"}
    assert "private error details" not in response.text
    assert "private error details" in caplog.text


def test_unrepresentable_cost_is_never_approved(client, proposal):
    proposal.order_details["limit_price"] = 1e308
    response = client.post("/stress-test", json=proposal.model_dump())
    assert response.status_code == 500
    assert response.json() == {"detail": "Stress calculation failed"}


def test_invalid_settings_fail_app_creation(monkeypatch):
    monkeypatch.setenv("CHAOS_MAX_STRESS_LOSS_PCT", "2")
    with pytest.raises(ValidationError):
        create_app()


def test_requests_do_not_share_mutable_state(settings, proposal):
    async def send_requests():
        transport = httpx.ASGITransport(app=create_app(settings))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await asyncio.gather(*[
                client.post("/stress-test", json=proposal.model_dump()) for _ in range(8)
            ])

    responses = asyncio.run(send_requests())
    assert all(response.status_code == 200 for response in responses)
    assert all(response.json() == responses[0].json() for response in responses)


def test_openapi_uses_shared_contracts(client):
    operation = client.get("/openapi.json").json()["paths"]["/stress-test"]["post"]
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith("/TradeProposal")
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/ChaosTestResult")
