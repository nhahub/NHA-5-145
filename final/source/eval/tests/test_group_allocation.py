"""Observable sampling contract, independent of classifier quality."""

import pytest

pytest.importorskip("scipy")

from eval.group_allocation import allocate


def examples():
    return [
        {
            "case_id": f"{label}-{family}-{lang}",
            "label": label,
            "language": lang,
            "group": f"{label}-{family}",
        }
        for label in ("advice", "mutate")
        for family in range(3)
        for lang in ("egyptian_arabic", "franco_arabic", "english", "mixed")
    ]


def test_allocates_whole_groups_with_support_and_stable_ties():
    rows = examples()
    assignments = allocate(rows)
    assert assignments == allocate(list(reversed(rows)))
    # Twenty percent would be 5 rows, but both intents need four validation rows.
    assert sum(assignments[r["group"]] == "validation" for r in rows) == 8
    for label in ("advice", "mutate"):
        assert assignments[f"{label}-0"] == "train"
        assert assignments[f"{label}-1"] == "train"
        assert assignments[f"{label}-2"] == "validation"


def test_rejects_indivisible_or_underrepresented_data():
    rows = examples()
    for row in rows:
        if row["label"] == "mutate":
            row["group"] = "one-mutation-conversation"
    with pytest.raises(ValueError, match="infeasible"):
        allocate(rows)


def test_rejects_component_map_that_splits_a_source_conversation():
    from eval.freeze_expanded_pilot import validate_components

    rows = [
        {
            "case_id": i,
            "grouping": {"conversation_group_id": "conversation", "paraphrase_group_id": i},
        }
        for i in ("initial", "correction")
    ]
    graph = {
        "components": [{"component_id": i, "case_ids": [i]} for i in ("initial", "correction")],
        "membership": [{"case_id": i, "component_id": i} for i in ("initial", "correction")],
    }
    with pytest.raises(ValueError, match="group divided"):
        validate_components(rows, graph)


def test_allocates_mixed_intent_conversations_without_leaking_them():
    rows = examples()
    for row in rows:
        if row["group"] in {"advice-2", "mutate-2"}:
            row["group"] = "shared-conversation"
    assignments = allocate(rows)
    for label in ("advice", "mutate"):
        for language in ("egyptian_arabic", "franco_arabic", "english", "mixed"):
            subset = [r for r in rows if r["label"] == label and r["language"] == language]
            assert sum(assignments[r["group"]] == "train" for r in subset) == 2
            assert sum(assignments[r["group"]] == "validation" for r in subset) == 1


def test_freeze_refuses_existing_evidence_directory(tmp_path):
    from eval.freeze_expanded_pilot import freeze

    evidence = tmp_path / "existing-release"
    evidence.mkdir()
    marker = evidence / "release.json"
    marker.write_text("original evidence", encoding="utf-8")
    with pytest.raises(ValueError, match="existing evidence is preserved"):
        freeze(tmp_path, evidence)
    assert marker.read_text(encoding="utf-8") == "original evidence"


def test_failed_export_leaves_no_published_or_partial_release(tmp_path, monkeypatch):
    import subprocess

    from eval.freeze_expanded_pilot import publish_release

    def failed_formatter(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "formatter")

    monkeypatch.setattr(subprocess, "check_output", failed_formatter)
    with pytest.raises(subprocess.CalledProcessError):
        publish_release(tmp_path, tmp_path / "new-release", {}, {"source_hashes": {}})
    assert list(tmp_path.iterdir()) == []


def test_rejected_annotation_leaves_no_published_release(tmp_path, monkeypatch):
    import subprocess

    from eval.freeze_expanded_pilot import publish_release
    from eval.pilot_data import LABELS

    monkeypatch.setattr(subprocess, "check_output", lambda *args, **kwargs: kwargs["input"])
    data = {
        "kind": "synthetic_development_pilot",
        "unseen_count": 0,
        "labels": LABELS,
        "source_hashes": {},
        "annotation_files": [],
        "records": [
            {
                "case_id": str(i),
                "text": str(i),
                "group": str(i),
                "eligible": True,
                "label": label,
                "split": split,
            }
            for i, (label, split) in enumerate(
                [("advice", "train"), ("mutate", "train"), ("advice", "validation")]
            )
        ],
    }
    with pytest.raises(ValueError, match="differs from annotation"):
        publish_release(tmp_path, tmp_path / "new-release", {"membership": []}, data)
    assert list(tmp_path.iterdir()) == []
