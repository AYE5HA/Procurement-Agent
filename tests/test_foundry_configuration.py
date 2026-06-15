import pytest
from pydantic import ValidationError

from procurement_agent.config import Settings


def test_foundry_is_the_default_runtime_provider(monkeypatch):
    monkeypatch.delenv("ANALYSIS_PROVIDER", raising=False)
    monkeypatch.delenv("AZURE_AI_FOUNDRY_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_AI_FOUNDRY_API_KEY", raising=False)
    with pytest.raises(ValidationError, match="Microsoft Foundry"):
        Settings(_env_file=None)


def test_foundry_configuration_is_accepted():
    settings = Settings(
        _env_file=None,
        analysis_provider="azure",
        azure_ai_foundry_endpoint="https://procurement.services.ai.azure.com/models",
        azure_ai_foundry_api_key="configured-secret",
    )
    assert settings.analysis_provider == "azure"
