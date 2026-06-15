import pytest
from pydantic import ValidationError

from procurement_agent.schemas import ContractSubmitted


def test_submission_rejects_modified_baseline_hash():
    with pytest.raises(ValidationError, match="baseline hash"):
        ContractSubmitted(contract_text="A" * 100, baseline_hash="invalid")


def test_submission_normalizes_and_hashes_contract():
    event = ContractSubmitted.from_text(f"  {'A' * 100}  ")
    assert event.contract_text == "A" * 100
    assert len(event.baseline_hash) == 64
