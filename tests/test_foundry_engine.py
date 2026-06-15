from procurement_agent.analysis import AnalysisEngine
from procurement_agent.config import Settings

CONTRACT = "A procurement contract with supplier obligations. " * 4


async def test_foundry_engine_uses_structured_model_output(monkeypatch):
    settings = Settings(
        _env_file=None,
        analysis_provider="azure",
        azure_ai_foundry_endpoint="https://procurement.services.ai.azure.com/models",
        azure_ai_foundry_api_key="configured-secret",
    )
    engine = AnalysisEngine(settings)

    async def fake_json(system_prompt, user_prompt):
        assert "financial liability" in system_prompt
        assert user_prompt == CONTRACT
        return {
            "findings": [
                {
                    "clause_reference": "Liability",
                    "risk_level": "high",
                    "issue": "No aggregate cap",
                    "business_impact": "Unbounded exposure",
                    "recommended_language": "Cap liability at twelve months of fees.",
                }
            ]
        }

    monkeypatch.setattr(engine, "_azure_json", fake_json)
    findings = await engine.evaluate_liability(CONTRACT)
    assert len(findings) == 1
    assert findings[0].clause_reference == "Liability"


def test_production_rejects_non_foundry_provider():
    try:
        Settings(
            _env_file=None,
            environment="production",
            analysis_provider="deterministic",
        )
    except ValueError as error:
        assert "Microsoft Foundry" in str(error)
    else:
        raise AssertionError("Production accepted a non-Foundry provider")
