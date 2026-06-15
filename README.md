# Procurement Contract Intelligence

Event-driven contract risk analysis for procurement teams. The service concurrently evaluates financial liability gaps and third-party IP indemnity loopholes, validates every inter-component message against strict Pydantic schemas, verifies contract baseline integrity across the full processing window, and produces a corrected contract through an autonomous remediation worker — without a central orchestrator directing any of it.

---

## How it works

The pipeline is choreographed, not orchestrated. No single component acts as a manager.

```
POST /analyze
      │
      ▼
ContractIngestionAdapter          validates payload, stamps ContractSubmitted event
      │
      ├──────────────────────────────────────┐
      ▼                                      ▼
FinancialLiabilityWorker          IPIndemnityWorker
  (concurrent, isolated)            (concurrent, isolated)
  publishes LiabilityEvaluated      publishes IndemnityEvaluated
      │                                      │
      └──────────────┬───────────────────────┘
                     ▼
             SynthesisGate
  waits for both events · verifies baseline hash · checks processing drift
  self-fires EvaluationSynthesized when gate clears
                     │
                     ▼
         ClauseRemediationWorker
  triggered by event, not by the API
  publishes ContractRemediated
                     │
                     ▼
             API response
```

The two evaluation workers share no imports and make no calls to each other. The remediation worker is never invoked by the API. The synthesis gate transitions purely on the arrival of both upstream events and rejects synthesis if the contract's baseline hash has changed or if processing drift exceeds the configured threshold.

---

## Requirements

- Python 3.11 or 3.12
- An [Azure AI Foundry](https://ai.azure.com) project with a deployed model (GPT-4o recommended)
- Docker and Docker Compose (for containerised runs)

---

## Local development

```bash
cp .env.example .env
# Fill in AZURE_AI_FOUNDRY_ENDPOINT, AZURE_AI_FOUNDRY_API_KEY, FOUNDRY_MODEL_NAME

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"

uvicorn procurement_agent.api:create_app --factory --reload
```





The compose file expects credentials via `.env`. Copy `.env.example` first and fill in your Foundry details before building.

---

## Configuration

| Variable | Purpose |
|---|---|
| `ANALYSIS_PROVIDER` | `azure` for runtime; `deterministic` for automated tests only |
| `AZURE_AI_FOUNDRY_ENDPOINT` | Azure AI Foundry model endpoint |
| `AZURE_AI_FOUNDRY_API_KEY` | Azure AI Foundry credential |
| `FOUNDRY_MODEL_NAME` | Deployed model name (e.g. `gpt-4o`) |
| `DATABASE_URL` | SQLite connection string for persisted analyses |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins |
| `API_ACCESS_KEY` | Optional bearer token; omit to disable auth |
| `RATE_LIMIT_REQUESTS` | Maximum requests per rate-limit window |
| `RATE_LIMIT_WINDOW_SECONDS` | Duration of the rate-limit window |
| `MAX_CONTRACT_CHARACTERS` | Hard ceiling on accepted contract length |
| `MAX_PROCESSING_DRIFT_SECONDS` | Maximum allowed gap between contract submission and synthesis; requests exceeding this are rejected |
| `ANALYSIS_TIMEOUT_SECONDS` | Per-worker inference timeout |

The service refuses to start if `ANALYSIS_PROVIDER=azure` and any of the three Foundry credentials are absent or left at their placeholder values. The `deterministic` provider bypasses all Azure calls and is intended exclusively for the test suite.

To deploy the frontend to GitHub Pages, set `window.PROCUREMENT_AGENT_CONFIG.apiBaseUrl` in `web/config.js` to your deployed API URL.

---

## Testing and linting

```bash
ruff check .
pytest
```

The test suite uses the `deterministic` provider and does not require Foundry credentials. Tests cover event fan-out, baseline hash integrity, drift rejection, and end-to-end remediation flow.

---

## Project layout

```
procurement_agent/   core package (API, workers, gate, schemas, bus)
tests/               pytest suite; uses deterministic analysis provider
web/                 static frontend (HTML/CSS/JS)
deploy/              nginx config for Docker frontend service
```

---

## Responsible use

This system supports contract review. It does not replace qualified legal counsel. All generated language must be reviewed by a legal professional before execution. Do not submit contracts containing regulated, confidential, or personally identifiable information unless the deployment environment and its data-handling controls have been assessed and approved for that information class.

---

## License

MIT
