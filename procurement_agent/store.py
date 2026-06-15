import asyncio
import sqlite3
from pathlib import Path
from uuid import UUID

from procurement_agent.schemas import AnalysisResponse, ContractSubmitted


class AnalysisStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS analyses (
                    contract_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    baseline_hash TEXT NOT NULL,
                    submitted_at TEXT NOT NULL,
                    completed_at TEXT,
                    response_json TEXT
                )
                """
            )

    async def create(self, event: ContractSubmitted) -> None:
        await asyncio.to_thread(self._create_sync, event)

    def _create_sync(self, event: ContractSubmitted) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                INSERT INTO analyses(contract_id, status, baseline_hash, submitted_at)
                VALUES (?, 'processing', ?, ?)
                """,
                (str(event.contract_id), event.baseline_hash, event.submitted_at.isoformat()),
            )

    async def complete(self, response: AnalysisResponse) -> None:
        await asyncio.to_thread(self._complete_sync, response)

    def _complete_sync(self, response: AnalysisResponse) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """
                UPDATE analyses
                SET status = 'completed', completed_at = ?, response_json = ?
                WHERE contract_id = ?
                """,
                (
                    response.completed_at.isoformat(),
                    response.model_dump_json(),
                    str(response.contract_id),
                ),
            )

    async def get(self, contract_id: UUID) -> AnalysisResponse | None:
        payload = await asyncio.to_thread(self._get_sync, contract_id)
        return AnalysisResponse.model_validate_json(payload) if payload else None

    def _get_sync(self, contract_id: UUID) -> str | None:
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                "SELECT response_json FROM analyses WHERE contract_id = ?",
                (str(contract_id),),
            ).fetchone()
        return row[0] if row and row[0] else None

    async def health(self) -> bool:
        try:
            await asyncio.to_thread(self._health_sync)
            return True
        except sqlite3.Error:
            return False

    def _health_sync(self) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute("SELECT 1").fetchone()
