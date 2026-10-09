"""Unit test for evaluation/verify_results.py using tiny in-memory and temporary fixtures."""
import json
import pytest
from pathlib import Path
from evaluation.verify_results import recompute_from_runs, verify_eval_results

def test_verify_results_with_tiny_fixtures(tmp_path):
    # Create tiny mock runs
    run_A = {
        "system": "A",
        "audit": {
            "total_planted": 7,
            "found_count": 4,
            "matches": {"S1": {"found": False}, "C1": {"found": True}}
        }
    }
    run_B = {
        "system": "B",
        "audit": {
            "total_planted": 7,
            "found_count": 5,
            "matches": {"S1": {"found": True}, "C1": {"found": True}}
        }
    }
    run_C = {
        "system": "C",
        "audit": {
            "total_planted": 7,
            "found_count": 5,
            "matches": {"S1": {"found": True}, "C1": {"found": True}}
        }
    }

    # Write files
    (tmp_path / "run_A_planted_seed_1.json").write_text(json.dumps(run_A), encoding="utf-8")
    (tmp_path / "run_B_planted_seed_1.json").write_text(json.dumps(run_B), encoding="utf-8")
    (tmp_path / "run_C_planted_seed_1.json").write_text(json.dumps(run_C), encoding="utf-8")

    metrics = recompute_from_runs(tmp_path)
    assert metrics["A"]["total_planted"] == 7
    assert metrics["A"]["total_found"] == 4
    assert metrics["A"]["recall"] == 57.1
    assert metrics["B"]["recall"] == 71.4
    assert metrics["C"]["recall"] == 71.4

    # Test doc verification match
    valid_doc = """
## 3. Overall Recall & Wilson 95% Confidence Intervals
| **System A** | 1 | 7 | 4 | **57.1%** |
| **System B** | 1 | 7 | 5 | **71.4%** |
| **System C** | 1 | 7 | 5 | **71.4%** |

## 4. False Positives on NULL Datasets
| System | NULL Runs |
| **System A** | 0 |
| **System B** | 0 |

## 5. Independent Numeric Accuracy
"""
    errors = verify_eval_results(valid_doc, metrics)
    assert len(errors) == 0

    # Test error detection on mismatch
    invalid_doc = """
| **System A** | 1 | 7 | 0 | **0.0%** |
| **System B** | 1 | 7 | 5 | **71.4%** |
| **System C** | 1 | 7 | 5 | **71.4%** |

## 4. False Positives on NULL Datasets
| System | NULL Runs |
| **System C** | 0 |

## 5. Independent Numeric Accuracy
"""
    errors_bad = verify_eval_results(invalid_doc, metrics)
    assert len(errors_bad) >= 2
