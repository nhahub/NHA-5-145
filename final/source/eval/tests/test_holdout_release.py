from copy import deepcopy

import pytest

from eval.holdout_release import checked_file, validate_records


def fixture():
    record = dict(
        case_id="new-1",
        input=dict(
            message="where is the cart control exactly", requires_context=False, followup_turns=[]
        ),
        eligible_for_evaluation=True,
        expected={"intent": "locate"},
        language_group="english",
        comparison={"intent_only_eligible": True},
        grouping=dict(
            split="synthetic_test",
            paraphrase_group_id="new-family",
            conversation_group_id="new-conv",
        ),
        annotation=dict(status="reviewed_synthetic", annotator_id="author", reviewer_id="reviewer"),
    )
    return (
        [record],
        dict(target_count=1, cases_per_cell=1, labels=["locate"], languages=["english"]),
        dict(
            status="approved_ai_review",
            records=[dict(case_id="new-1", final_intent="locate", status="accepted")],
        ),
        {"records": [dict(text="a different message", group="old-family")]},
    )


def test_reviewed_record_requires_complete_cells_and_distinct_review():
    args = fixture()
    validate_records(*args)
    bad = deepcopy(args)
    bad[0][0]["annotation"]["reviewer_id"] = "author"
    with pytest.raises(ValueError, match="review"):
        validate_records(*bad)
    bad = deepcopy(args)
    bad[1]["languages"].append("mixed")
    with pytest.raises(ValueError, match="coverage"):
        validate_records(*bad)


def test_normalized_development_overlap_and_group_leakage_block_freeze():
    args = fixture()
    args[3]["records"][0]["text"] = "WHERE is the cart control, exactly?"
    with pytest.raises(ValueError, match="overlap"):
        validate_records(*args)
    args = fixture()
    args[0][0]["grouping"]["paraphrase_group_id"] = "old-family"
    with pytest.raises(ValueError, match="group"):
        validate_records(*args)


def test_hash_and_path_mismatch_are_rejected(tmp_path):
    (tmp_path / "file.json").write_text("{}")
    with pytest.raises(ValueError, match="hash"):
        checked_file(tmp_path, "file.json", "0" * 64)
    with pytest.raises(ValueError, match="path"):
        checked_file(tmp_path, "../outside.json", "0" * 64)


def test_overlap_requires_hashed_input_coverage_and_resolved_review():
    from eval.holdout_release import inputs_digest, validate_overlap

    rows, _, review, _ = fixture()
    audit = {
        "inputs_sha256": inputs_digest(rows),
        "prior_candidate_count": 5,
        "source_hashes": {"fixture.py": "hash"},
        "cases": [{"case_id": "new-1", "nearest_prior": [{"normalized_exact": False}]}],
    }
    with pytest.raises(ValueError, match="Unresolved"):
        validate_overlap(rows, review, audit)
    review["records"][0].update(overlap_status="resolved", overlap_disposition="distinct request")
    validate_overlap(rows, review, audit)
    audit["cases"][0]["nearest_prior"][0]["normalized_exact"] = True
    with pytest.raises(ValueError, match="exact"):
        validate_overlap(rows, review, audit)
    with pytest.raises(ValueError, match="Missing"):
        validate_overlap(rows, review, {})


def test_overlap_inventory_includes_untracked_manual_python(tmp_path, monkeypatch):
    from eval.holdout_overlap import inventory

    monkeypatch.setattr("eval.holdout_overlap.subprocess.check_output", lambda *a, **kw: "")
    folder = tmp_path / "work/manual-test"
    folder.mkdir(parents=True)
    (folder / "probe.py").write_text('request="please add the blue shoes"', encoding="utf8")
    candidates, sources = inventory(tmp_path)
    assert candidates[0]["text"] == "please add the blue shoes"
    assert "work/manual-test/probe.py" in sources
