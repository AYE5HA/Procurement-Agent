from fastapi.testclient import TestClient

from procurement_agent.api import create_app
from procurement_agent.config import Settings

CONTRACT = """
PROCUREMENT AGREEMENT
Supplier provides consulting services. Supplier's liability shall be unlimited for
any and all claims.
Invoices are payable within thirty days. Intellectual property created before this agreement remains
with its original owner. No other risk allocation or third-party claim language applies.
"""


def test_health_and_analysis_round_trip(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api.db'}",
        cors_origins=["https://aye5ha.github.io"],
        analysis_provider="deterministic",
    )
    with TestClient(create_app(settings)) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "healthy"

        response = client.post("/api/v1/analyses", json={"contract_text": CONTRACT})
        assert response.status_code == 201
        body = response.json()
        assert body["baseline_integrity_verified"] is True
        assert body["corrected_text"].startswith("PROCUREMENT AGREEMENT")

        persisted = client.get(f"/api/v1/analyses/{body['contract_id']}")
        assert persisted.status_code == 200
        assert persisted.json()["contract_id"] == body["contract_id"]


def test_access_key_protection(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'auth.db'}",
        api_access_key="production-secret",
        analysis_provider="deterministic",
    )
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/v1/analyses", json={"contract_text": CONTRACT}).status_code == 401
        response = client.post(
            "/api/v1/analyses",
            json={"contract_text": CONTRACT},
            headers={"Authorization": "Bearer production-secret"},
        )
        assert response.status_code == 201
