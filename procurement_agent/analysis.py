import json
import re
from collections.abc import Sequence

from pydantic import BaseModel

from procurement_agent.config import Settings
from procurement_agent.schemas import (
    IndemnityFinding,
    LiabilityFinding,
    RiskLevel,
)


class RemediationPayload(BaseModel):
    corrected_text: str
    changes_applied: tuple[str, ...]
    legal_review_notes: str


class LiabilityFindingsPayload(BaseModel):
    findings: tuple[LiabilityFinding, ...]


class IndemnityFindingsPayload(BaseModel):
    findings: tuple[IndemnityFinding, ...]


class AnalysisEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def evaluate_liability(self, text: str) -> tuple[LiabilityFinding, ...]:
        if self._use_azure:
            payload = await self._azure_object(
                LIABILITY_PROMPT,
                text,
                LiabilityFindingsPayload,
            )
            return payload.findings
        return deterministic_liability(text)

    async def evaluate_indemnity(self, text: str) -> tuple[IndemnityFinding, ...]:
        if self._use_azure:
            payload = await self._azure_object(
                INDEMNITY_PROMPT,
                text,
                IndemnityFindingsPayload,
            )
            return payload.findings
        return deterministic_indemnity(text)

    async def remediate(
        self,
        text: str,
        liability: Sequence[LiabilityFinding],
        indemnity: Sequence[IndemnityFinding],
    ) -> RemediationPayload:
        if self._use_azure:
            prompt = REMEDIATION_PROMPT.format(
                contract=text,
                findings=json.dumps(
                    [
                        *[finding.model_dump(mode="json") for finding in liability],
                        *[finding.model_dump(mode="json") for finding in indemnity],
                    ]
                ),
            )
            return await self._azure_object(
                "Return only valid JSON matching the requested schema.",
                prompt,
                RemediationPayload,
            )
        return deterministic_remediation(text, liability, indemnity)

    @property
    def _use_azure(self) -> bool:
        return self.settings.analysis_provider == "azure"

    async def _azure_object(
        self,
        system_prompt: str,
        user_prompt: str,
        model: type[BaseModel],
    ) -> BaseModel:
        result = await self._azure_json(system_prompt, user_prompt)
        return model.model_validate(result)

    async def _azure_json(self, system_prompt: str, user_prompt: str):
        from azure.ai.inference.aio import ChatCompletionsClient
        from azure.ai.inference.models import SystemMessage, UserMessage
        from azure.core.credentials import AzureKeyCredential

        client = ChatCompletionsClient(
            endpoint=self.settings.azure_ai_foundry_endpoint,
            credential=AzureKeyCredential(self.settings.azure_ai_foundry_api_key),
        )
        try:
            response = await client.complete(
                model=self.settings.foundry_model_name,
                messages=[
                    SystemMessage(content=system_prompt),
                    UserMessage(content=user_prompt),
                ],
                temperature=0.1,
                response_format="json_object",
            )
            content = response.choices[0].message.content
            return json.loads(content)
        finally:
            await client.close()


def deterministic_liability(text: str) -> tuple[LiabilityFinding, ...]:
    lowered = text.lower()
    findings: list[LiabilityFinding] = []
    if "unlimited liability" in lowered or re.search(r"liabilit\w* shall be unlimited", lowered):
        findings.append(
            LiabilityFinding(
                clause_reference="Liability limitation",
                risk_level=RiskLevel.CRITICAL,
                issue="The agreement creates unlimited contractual liability.",
                business_impact="Exposure is uncapped and may exceed the total contract value.",
                recommended_language=LIABILITY_CAP,
            )
        )
    if "consequential damages" not in lowered and "indirect damages" not in lowered:
        findings.append(
            LiabilityFinding(
                clause_reference="Damages exclusion",
                risk_level=RiskLevel.HIGH,
                issue="No mutual exclusion of indirect or consequential damages was identified.",
                business_impact="Remote and difficult-to-quantify losses may remain recoverable.",
                recommended_language=CONSEQUENTIAL_DAMAGES,
            )
        )
    if "insurance" not in lowered:
        findings.append(
            LiabilityFinding(
                clause_reference="Insurance",
                risk_level=RiskLevel.MEDIUM,
                issue="No minimum supplier insurance requirement was identified.",
                business_impact=(
                    "The supplier may lack financial resources to satisfy covered claims."
                ),
                recommended_language=INSURANCE,
            )
        )
    return tuple(findings)


def deterministic_indemnity(text: str) -> tuple[IndemnityFinding, ...]:
    lowered = text.lower()
    findings: list[IndemnityFinding] = []
    has_third_party_ip = all(term in lowered for term in ("third-party", "intellectual property"))
    if not has_third_party_ip:
        findings.append(
            IndemnityFinding(
                clause_reference="Third-party IP indemnity",
                risk_level=RiskLevel.CRITICAL,
                issue=(
                    "Complete third-party intellectual property infringement protection "
                    "was not identified."
                ),
                third_party_exposure=(
                    "The buyer may bear defense costs, damages, and replacement costs."
                ),
                recommended_language=IP_INDEMNITY,
            )
        )
    if "defend" not in lowered:
        findings.append(
            IndemnityFinding(
                clause_reference="Defense obligation",
                risk_level=RiskLevel.HIGH,
                issue="The indemnity does not clearly include a duty to defend.",
                third_party_exposure=(
                    "The buyer may need to fund litigation before recovering costs."
                ),
                recommended_language=DEFENSE_CONTROL,
            )
        )
    if "replace" not in lowered and "modify" not in lowered:
        findings.append(
            IndemnityFinding(
                clause_reference="Infringement remedies",
                risk_level=RiskLevel.HIGH,
                issue="No replacement, modification, or refund remedy was identified.",
                third_party_exposure=(
                    "An injunction could interrupt use of critical goods or services."
                ),
                recommended_language=IP_REMEDIES,
            )
        )
    return tuple(findings)


def deterministic_remediation(
    text: str,
    liability: Sequence[LiabilityFinding],
    indemnity: Sequence[IndemnityFinding],
) -> RemediationPayload:
    clauses: list[str] = []
    changes: list[str] = []
    seen: set[str] = set()
    for finding in [*liability, *indemnity]:
        language = finding.recommended_language.strip()
        if language not in seen:
            seen.add(language)
            clauses.append(language)
            changes.append(f"Added or replaced {finding.clause_reference.lower()} language")
    appendix = "\n\nRISK ALLOCATION AMENDMENT\n\n" + "\n\n".join(
        f"{index}. {clause}" for index, clause in enumerate(clauses, start=1)
    )
    return RemediationPayload(
        corrected_text=text.rstrip() + appendix,
        changes_applied=tuple(changes),
        legal_review_notes=(
            "Automated remediation addresses identified financial liability and third-party "
            "protection gaps. Qualified counsel should confirm jurisdiction-specific "
            "enforceability."
        ),
    )


LIABILITY_CAP = (
    "Except for fraud, willful misconduct, breach of confidentiality, infringement obligations, "
    "or amounts payable under an indemnity, each party's aggregate liability arising from this "
    "Agreement will not exceed the fees paid or payable during the twelve months "
    "preceding the claim."
)
CONSEQUENTIAL_DAMAGES = (
    "Neither party will be liable for indirect, incidental, special, punitive, or consequential "
    "damages, or for lost profits, revenue, data, or business opportunity, regardless of theory."
)
INSURANCE = (
    "Supplier will maintain commercially reasonable general liability, professional liability, "
    "cyber liability, and workers' compensation insurance and provide evidence upon request."
)
IP_INDEMNITY = (
    "Supplier will defend, indemnify, and hold harmless Buyer and its affiliates from third-party "
    "claims alleging that the goods, services, or deliverables infringe intellectual "
    "property rights, "
    "including resulting damages, settlements, costs, and reasonable legal fees."
)
DEFENSE_CONTROL = (
    "Supplier's duty to defend begins upon written notice. Buyer may participate with "
    "counsel of its choice, and Supplier may not settle any claim admitting fault or "
    "imposing obligations on Buyer "
    "without Buyer's prior written consent."
)
IP_REMEDIES = (
    "If use is enjoined or likely to be enjoined, Supplier will promptly obtain continued "
    "usage rights, modify or replace the affected item without material loss of "
    "functionality, or refund all amounts "
    "paid for the affected item and reimburse reasonable transition costs."
)

LIABILITY_PROMPT = """You are a procurement contract risk specialist. Identify financial liability
gaps only. Return one JSON object with a findings array. Each finding must contain clause_reference,
risk_level (critical/high/medium/low), issue, business_impact, and recommended_language.
Do not discuss intellectual property indemnity."""

INDEMNITY_PROMPT = """You are an independent third-party IP protection specialist. Identify
indemnification, defense, infringement, ownership, and remedy gaps only. Return one JSON object with
a findings array. Each finding must contain clause_reference, risk_level
(critical/high/medium/low), issue, third_party_exposure, and recommended_language.
Do not discuss financial liability caps."""

REMEDIATION_PROMPT = """Rewrite the contract to resolve every supplied finding while preserving
unrelated commercial terms. Return JSON with corrected_text, changes_applied (array), and
legal_review_notes. Do not claim legal certainty.

CONTRACT:
{contract}

VALIDATED FINDINGS:
{findings}
"""
