import pytest

from eval.catalogue_retrieval import recall_at_k, reciprocal_rank, verify_manifest


def test_retrieval_metrics_and_duplicate_ids_are_not_inflated():
    assert recall_at_k(["p2", "p1"], {"p1", "p3"}, 2) == 0.5
    assert reciprocal_rank(["p2", "p1"], {"p1"}) == 0.5
    assert recall_at_k(["p1", "p1"], {"p1", "p3"}, 2) == 0.5
    assert recall_at_k(["p1"], set(), 10) is None


def test_manifest_rejects_changed_cases_before_comparison():
    with pytest.raises(ValueError, match="freeze"):
        verify_manifest(b"changed", {"sha256": "wrong"})
