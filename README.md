# Procurement Contract Intelligence

Production-oriented contract risk analysis for procurement teams. The service evaluates financial liability and third-party intellectual property protection concurrently, validates every event against strict schemas, verifies contract baseline integrity, and produces a corrected contract through an autonomous remediation worker.

## Architecture

The pipeline uses event-driven choreography rather than request-time orchestration:

1. The API validates and publishes `contract.submitted`.
2. Independent liability and indemnity workers receive the same immutable event concurrently.
3. The synthesis gate waits for both validated outputs and verifies contract ID, baseline hash, and processing drift.
4. The remediation worker self-triggers from `evaluation.synthesized`.
5. The API receives the final `contract.remediated` event through contract-scoped correlation.

The evaluation workers do not import or call one another. The remediation worker is never called by the API.

## Local Development

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn procurement_agent.api:create_app --factory --reload
```

On Windows, activate the environment with `.venv\Scripts\Activate.ps1`.

Open `web/index.html` through a local static server:

```bash
python -m http.server 3000 --directory web
```

## Docker

```bash
docker compose up --build
```

The API is available on `http://localhost:8000`; the frontend is available on `http://localhost:3000`.

## Configuration

Copy `.env.example` to `.env` and provide the endpoint, API key, and deployed model name
from Microsoft Foundry. Foundry is the required runtime provider and the service refuses to
start with missing or placeholder credentials. The deterministic engine is reserved for automated
tests and must be selected explicitly.

| Variable | Purpose |
| --- | --- |
| `ANALYSIS_PROVIDER` | `azure` for runtime; `deterministic` is test-only |
| `AZURE_AI_FOUNDRY_ENDPOINT` | Azure AI model endpoint |
| `AZURE_AI_FOUNDRY_API_KEY` | Azure AI credential |
| `FOUNDRY_MODEL_NAME` | Deployed model name |
| `DATABASE_URL` | SQLite URL for persisted analyses |
| `CORS_ORIGINS` | Comma-separated trusted frontend origins |
| `API_ACCESS_KEY` | Optional bearer token for API access |
| `RATE_LIMIT_REQUESTS` | Requests allowed per window |
| `RATE_LIMIT_WINDOW_SECONDS` | Rate-limit window |
| `MAX_CONTRACT_CHARACTERS` | Maximum accepted contract length |
| `MAX_PROCESSING_DRIFT_SECONDS` | Baseline-to-remediation timing limit |

For GitHub Pages, set `window.PROCUREMENT_AGENT_CONFIG.apiBaseUrl` in `web/config.js` to the deployed API URL.

## Quality

```bash
ruff check .
pytest
```

## Responsible Use

This system supports contract review but does not replace qualified legal counsel. Generated language must be reviewed before execution. Do not submit contracts containing regulated or confidential information unless the deployed environment and data-handling controls are approved for that information.

## License

Licensed under the MIT License.
