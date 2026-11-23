"""Offline experiment invariants; no provider calls or application model changes."""

import pytest

pytest.importorskip("sklearn")

from eval.baseline_pilot import candidate_configs, fit_candidate, select_best
from eval.pilot_data import LABELS, load_release, validate_release


def release():
    return {
        "kind": "synthetic_development_pilot",
        "labels": list(LABELS),
        "unseen_count": 0,
        "records": [
            {
                "case_id": "a",
                "text": "compare cotton",
                "label": "advice",
                "group": "g1",
                "split": "train",
                "eligible": True,
                "language": "english",
            },
            {
                "case_id": "b",
                "text": "remove shirt",
                "label": "cart_edit",
                "group": "g2",
                "split": "train",
                "eligible": True,
                "language": "english",
            },
            {
                "case_id": "c",
                "text": "compare sentinelvalidation",
                "label": "advice",
                "group": "g3",
                "split": "validation",
                "eligible": True,
                "language": "english",
            },
        ],
    }


def test_release_rejects_group_leakage_and_ineligible_rows():
    data = release()
    validate_release(data)
    data["records"][2]["group"] = "g1"
    with pytest.raises(ValueError, match="group"):
        validate_release(data)
    data = release()
    data["records"][2]["eligible"] = False
    with pytest.raises(ValueError, match="eligible"):
        validate_release(data)


def test_release_rejects_duplicate_text_and_unseen_claim():
    data = release()
    data["records"][2]["text"] = data["records"][0]["text"]
    with pytest.raises(ValueError, match="duplicate"):
        validate_release(data)
    data = release()
    data["unseen_count"] = 1
    with pytest.raises(ValueError, match="unseen"):
        validate_release(data)


def test_release_requires_fixed_full_label_order():
    for labels in (LABELS[:-1], list(reversed(LABELS))):
        data = release()
        data["labels"] = labels
        with pytest.raises(ValueError, match="label"):
            validate_release(data)


def test_loading_rejects_changed_source(tmp_path):
    import json

    data = release()
    source = tmp_path / "source.json"
    source.write_text("[]", encoding="utf-8")
    data["source_hashes"] = {"source.json": "wrong"}
    path = tmp_path / "release.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Source hash"):
        load_release(path, tmp_path)


def test_loading_binds_records_to_sources_and_reviewed_groups(tmp_path):
    import json

    from eval.pilot_data import digest

    data = release()
    originals = [
        {
            "case_id": r["case_id"],
            "input": {"message": r["text"]},
            "expected": {"intent": r["label"]},
            "language_group": r["language"],
            "comparison": {"intent_only_eligible": True},
        }
        for r in data["records"]
    ]
    (tmp_path / "cases.json").write_text(json.dumps(originals), encoding="utf-8")
    (tmp_path / "groups.json").write_text(
        json.dumps(
            {
                "membership": [
                    {"case_id": r["case_id"], "component_id": r["group"]} for r in data["records"]
                ]
            }
        ),
        encoding="utf-8",
    )
    data.update(
        annotation_files=["cases.json"],
        group_map="groups.json",
        source_hashes={n: digest(tmp_path / n) for n in ("cases.json", "groups.json")},
    )
    path = tmp_path / "release.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    load_release(path, tmp_path)
    for field, value in (("group", "fake-component"), ("text", "invented"), ("label", "cart_edit")):
        changed = json.loads(json.dumps(data))
        changed["records"][2][field] = value
        path.write_text(json.dumps(changed), encoding="utf-8")
        with pytest.raises(ValueError, match="annotation/group"):
            load_release(path, tmp_path)
    originals[2]["comparison"]["intent_only_eligible"] = False
    (tmp_path / "cases.json").write_text(json.dumps(originals), encoding="utf-8")
    data["source_hashes"]["cases.json"] = digest(tmp_path / "cases.json")
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="annotation/group"):
        load_release(path, tmp_path)


def test_fitting_never_learns_validation_words():
    data = release()
    model, _ = fit_candidate(data["records"][:2], candidate_configs()[0])
    model.predict([data["records"][2]["text"]])
    vocab = model.named_steps["tfidf"].vocabulary_
    assert "sentinelvalidation" not in vocab
    assert "cotton" in vocab
    assert len(candidate_configs()) == 12


def test_selection_uses_declared_ties_and_excludes_failed_convergence():
    trials = [
        {"config": c, "macro_f1": 0.3, "accuracy": 0.5, "converged": True}
        for c in reversed(candidate_configs())
    ]
    trials[0].update(macro_f1=1.0, converged=False)
    assert select_best(trials)["config"] == candidate_configs()[0]
