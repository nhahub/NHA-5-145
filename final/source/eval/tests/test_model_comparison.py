"""Offline model-family comparison contracts; never download weights in tests."""

import pytest

pytest.importorskip("sklearn")


def test_word_classifier_never_learns_validation_tokens():
    from eval.comparison_models import configurations, fit

    config = next(c for c in configurations() if c["family"] == "svm")
    model, status = fit(["compare cotton", "remove shirt"], [0, 1], config)
    assert status["converged"]
    model.predict(["sentinelvalidation cotton"])
    assert "sentinelvalidation" not in model.named_steps["features"].vocabulary_
    assert "cotton" in model.named_steps["features"].vocabulary_


def test_selection_excludes_failures_and_uses_predeclared_ties():
    from eval.comparison_models import select

    trials = [
        {"config": {"index": 1}, "converged": True, "macro_f1": 0.5, "accuracy": 0.6},
        {"config": {"index": 0}, "converged": True, "macro_f1": 0.5, "accuracy": 0.6},
        {"config": {"index": 2}, "converged": False, "macro_f1": 1.0, "accuracy": 1.0},
        {"config": {"index": 3}, "error": "failed"},
    ]
    assert select(trials)["config"]["index"] == 0
    assert select(trials[2:]) is None


def test_embedding_scaler_is_fitted_only_on_training():
    import numpy as np

    from eval.comparison_models import configurations, fit

    config = next(c for c in configurations() if c["family"] == "embedding_lr")
    model, _ = fit(np.array([[0, 1], [2, 3], [4, 5], [6, 7]]), [0, 0, 1, 1], config)
    model.predict(np.array([[1000, 2000]]))
    np.testing.assert_array_equal(model.named_steps["features"].mean_, [3, 4])


def test_family_report_preserves_predictions_and_reloaded_artifact(tmp_path):
    from eval.compare_models import evaluate_family
    from eval.comparison_models import configurations

    rows = [
        {"case_id": str(i), "text": text, "label": label, "language": "english"}
        for i, (text, label) in enumerate(
            [
                ("compare cotton", "advice"),
                ("remove shirt", "cart_edit"),
                ("compare linen", "advice"),
                ("remove shoes", "cart_edit"),
            ]
        )
    ]
    configs = [next(c for c in configurations() if c["family"] == "nb")]
    result = evaluate_family(rows[:2], rows[2:], ["advice", "cart_edit"], configs, tmp_path)
    assert result["status"] == "complete"
    assert result["validation"]["accuracy"] == 1.0
    assert [p["case_id"] for p in result["predictions"]] == ["2", "3"]
    assert result["artifact_reload_verified"] is True
    assert result["latency_ms"]["sample_count"] == 2


def test_failed_family_keeps_trial_evidence(tmp_path):
    import json

    from eval.compare_models import evaluate_family
    from eval.comparison_models import configurations

    rows = [{"case_id": "1", "text": "", "label": "advice", "language": "english"}]
    config = next(c for c in configurations() if c["family"] == "lr")
    result = evaluate_family(rows, rows, ["advice", "cart_edit"], [config], tmp_path)
    saved = json.loads((tmp_path / "lr-trials.json").read_text(encoding="utf-8"))
    assert result == saved
    assert saved["status"] == "unavailable"
    assert "empty vocabulary" in saved["trials"][0]["error"]


def test_run_rejects_existing_directory_without_overwriting(tmp_path):
    from pathlib import Path

    from eval.compare_models import run

    root = Path(__file__).resolve().parents[2]
    marker = tmp_path / "report.json"
    marker.write_text("existing evidence", encoding="utf-8")
    with pytest.raises(FileExistsError):
        run(root / "eval/datasets/capstone-v1/pilot-20261007/release.json", tmp_path, root)
    assert marker.read_text(encoding="utf-8") == "existing evidence"


@pytest.mark.parametrize(
    "family", ["lr", "svm", "nb", "rf", "xgb", "embedding_lr", "embedding_mlp"]
)
def test_each_backend_roundtrips_multiclass_predictions(family, tmp_path):
    import joblib
    import numpy as np

    from eval.comparison_models import configurations, fit

    if family == "xgb":
        pytest.importorskip("xgboost")
    inputs = ["compare cotton", "remove shirt", "find shoes"] * 3
    if family.startswith("embedding"):
        inputs = np.tile(np.eye(3), (3, 1))
    config = next(c for c in configurations() if c["family"] == family)
    model, _ = fit(inputs, [0, 1, 2] * 3, config)
    before = model.predict(inputs)
    path = tmp_path / "own-model.joblib"
    joblib.dump(model, path)
    assert set(before) <= {0, 1, 2}
    np.testing.assert_array_equal(joblib.load(path).predict(inputs), before)


def test_embedding_latency_path_encodes_each_message(tmp_path):
    import numpy as np

    from eval.compare_models import evaluate_family
    from eval.comparison_models import configurations

    class LocalEncoder:
        metadata = {"bytes": 0}

        def __init__(self):
            self.calls = []

        def encode(self, texts):
            self.calls.append(texts)
            return np.array([[float(t), 1] for t in texts])

    rows = [
        {
            "case_id": str(i),
            "text": str(i),
            "label": "advice" if i < 2 else "cart_edit",
            "language": "english",
        }
        for i in range(4)
    ]
    encoder = LocalEncoder()
    features = np.array([[i, 1] for i in range(4)])
    config = next(c for c in configurations() if c["family"] == "embedding_lr")
    report = evaluate_family(
        rows, rows, ["advice", "cart_edit"], [config], tmp_path, encoder, (features, features)
    )
    assert report["latency_ms"]["includes_encoder"]
    assert encoder.calls[1:] == [[str(i)] for i in range(4)]
