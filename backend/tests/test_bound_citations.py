"""Adversarial and functional unit tests for Bound Citation Checking (Item 1)."""
import pytest
from backend.app.agent.citation_checker import (
    build_source_index,
    verify_bound_claim,
    validate_citations,
    strip_unverified_sentences
)

def test_adversarial_citation_engineering_attrition_fails():
    """
    Adversarial test (a):
    'Engineering attrition 46.36%' where 46.36 is Annual_Salary's imputation rate must FAIL.
    Even though 46.36 exists in the dataset facts, it belongs to salary imputation, NOT attrition.
    """
    insights = [
        {
            "id": "insight-attrition-dept",
            "type": "segment_difference",
            "title": "Attrition across Department",
            "metric_values": {
                "Engineering": 62.73,
                "Sales": 44.55,
                "attrition_rate": 62.73
            },
            "n_used": 60,
            "exclusion_rate": 0.10
        },
        {
            "id": "insight-dq-salary",
            "type": "data_quality",
            "title": "Invalid salary imputation",
            "metric_values": {
                "column": "Annual_Salary",
                "imputation_rate": 46.36
            },
            "n_used": 70,
            "exclusion_rate": 0.4636
        }
    ]

    source_index = build_source_index(insights=insights)

    # Claim 1: Citing attrition insight with salary's 46.36 -> FAILS value mismatch
    claim_1 = {
        "text": "Engineering attrition 46.36%",
        "source_id": "insight-attrition-dept",
        "metric_key": "attrition_rate",
        "value": 46.36
    }
    is_valid_1, reason_1 = verify_bound_claim(claim_1, source_index)
    assert not is_valid_1, "Expected claim_1 to fail"
    assert "mismatch" in reason_1.lower() or "expected" in reason_1.lower()

    # Claim 2: Citing salary insight with metric_key="attrition_rate" -> FAILS metric not found in source
    claim_2 = {
        "text": "Engineering attrition 46.36%",
        "source_id": "insight-dq-salary",
        "metric_key": "attrition_rate",
        "value": 46.36
    }
    is_valid_2, reason_2 = verify_bound_claim(claim_2, source_index)
    assert not is_valid_2, "Expected claim_2 to fail"
    assert "does not exist in source" in reason_2.lower()

def test_adversarial_citation_email_touchpoints_fails():
    """
    Adversarial test (b):
    'Email 28.0% of touchpoints' where 28.0 is an exclusion rate must FAIL.
    """
    insights = [
        {
            "id": "insight-channel-conversions",
            "type": "segment_difference",
            "title": "Conversions across Channel",
            "metric_values": {
                "Email": 14.0,
                "Social": 19.5,
                "conversions": 14.0
            },
            "n_used": 72,
            "n_excluded": 28,
            "exclusion_rate": 0.28  # 28.0% exclusion rate
        }
    ]

    source_index = build_source_index(insights=insights)

    # Claim cites touchpoints as metric_key, which is not an exclusion rate
    claim = {
        "text": "Email 28.0% of touchpoints",
        "source_id": "insight-channel-conversions",
        "metric_key": "touchpoints",
        "value": 28.0
    }
    is_valid, reason = verify_bound_claim(claim, source_index)
    assert not is_valid, "Expected touchpoints claim to fail"
    assert "does not exist" in reason.lower()

def test_correct_claim_passes():
    """
    Adversarial test (c):
    A correct claim matching its source and metric passes verification.
    """
    insights = [
        {
            "id": "insight-seg-category",
            "type": "segment_difference",
            "title": "Unit_Price across Category",
            "metric_values": {
                "Accessories": 497.02,
                "Office Supplies": 464.69,
                "p_value": 0.7567
            },
            "n_used": 105,
            "exclusion_rate": 0.125
        }
    ]

    source_index = build_source_index(insights=insights)

    valid_claim = {
        "text": "Accessories recorded a mean price of 497.02",
        "source_id": "insight-seg-category",
        "metric_key": "Accessories",
        "value": 497.02,
        "unit": "USD"
    }
    is_valid, reason = verify_bound_claim(valid_claim, source_index)
    assert is_valid, f"Expected claim to pass, but failed with: {reason}"
    assert reason == "verified"

def test_sentence_stripping_and_pre_post_rates():
    """
    Test that sentences containing unverified numbers/claims are stripped,
    leaving a 100% verified narrative post-strip.
    """
    insights = [
        {
            "id": "insight-1",
            "metric_values": {"revenue": 500.0},
            "n_used": 100
        }
    ]

    synthesis_payload = {
        "executive_summary": "Total revenue reached 500.0 in Q1. However bad metric is 9999.0 without evidence. Performance was steady.",
        "key_findings": [],
        "claims": [
            {
                "text": "Total revenue reached 500.0 in Q1",
                "source_id": "insight-1",
                "metric_key": "revenue",
                "value": 500.0
            }
        ]
    }

    result = validate_citations(synthesis_payload, structured_results=[], insights=insights)
    assert not result["is_valid"]
    assert result["unverified_claims_count"] == 0  # the one claim was verified
    assert 9999.0 in result["unverified_numbers"]
    assert len(result["stripped_sentences"]) == 1
    assert "9999.0" in result["stripped_sentences"][0]
    assert "500.0" in result["cleaned_executive_summary"]
    assert "9999.0" not in result["cleaned_executive_summary"]
    assert result["post_strip_verification_rate"] == 100.0
