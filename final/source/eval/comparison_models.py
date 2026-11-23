"""Bounded offline candidate construction; no language interpretation rules."""

import itertools
import time
import warnings

from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import ComplementNB
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC


def configurations() -> list[dict]:
    configs = []
    for family in ("lr", "svm", "nb", "rf", "xgb", "embedding_lr", "embedding_mlp"):
        features = ("embedding",) if family.startswith("embedding") else ("word", "char_wb")
        if family in {"lr", "svm", "embedding_lr"}:
            params = [
                {"C": c, "class_weight": w}
                for c, w in itertools.product((0.1, 1.0, 10.0), (None, "balanced"))
            ]
        elif family == "nb":
            params = [{"alpha": a} for a in (0.1, 1.0)]
        elif family in {"rf", "xgb"}:
            params = [{"max_depth": d} for d in ((10, None) if family == "rf" else (3, 6))]
        else:
            params = [
                {"hidden_layer_sizes": (h,), "alpha": a}
                for h, a in itertools.product((64, 128), (0.001, 0.01))
            ]
        for feature, param in itertools.product(features, params):
            configs.append({"index": len(configs), "family": family, "features": feature, **param})
    return configs


def build(config: dict) -> Pipeline:
    family = config["family"]
    param = {k: v for k, v in config.items() if k not in {"index", "family", "features"}}
    if family in {"lr", "embedding_lr"}:
        estimator = LogisticRegression(**param, solver="lbfgs", max_iter=2000, random_state=42)
    elif family == "svm":
        estimator = LinearSVC(**param, dual="auto", max_iter=10000, random_state=42)
    elif family == "nb":
        estimator = ComplementNB(**param, norm=False)
    elif family == "rf":
        estimator = RandomForestClassifier(
            **param, n_estimators=200, class_weight="balanced", random_state=42, n_jobs=4
        )
    elif family == "xgb":
        from xgboost import XGBClassifier

        estimator = XGBClassifier(
            **param,
            n_estimators=100,
            learning_rate=0.1,
            tree_method="hist",
            objective="multi:softprob",
            random_state=42,
            n_jobs=4,
        )
    elif family == "embedding_mlp":
        estimator = MLPClassifier(
            **param, solver="lbfgs", max_iter=1000, max_fun=15000, random_state=42
        )
    else:
        raise ValueError(f"Unknown comparison family: {family}")
    feature = config["features"]
    transformer = (
        StandardScaler()
        if feature == "embedding"
        else TfidfVectorizer(
            analyzer=feature,
            ngram_range=(1, 2) if feature == "word" else (3, 5),
            token_pattern=r"(?u)\b\w+\b" if feature == "word" else None,
            stop_words=None,
        )
    )
    return Pipeline([("features", transformer), ("classifier", estimator)])


def fit(inputs, targets: list[int], config: dict) -> tuple[Pipeline, dict]:
    model = build(config)
    start = time.perf_counter()
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        model.fit(inputs, targets)
    return model, {
        "training_seconds": time.perf_counter() - start,
        "converged": not any(issubclass(w.category, ConvergenceWarning) for w in captured),
        "warnings": [str(w.message) for w in captured],
    }


def select(trials: list[dict]) -> dict | None:
    usable = [t for t in trials if t.get("converged") and "error" not in t]
    return (
        min(usable, key=lambda t: (-t["macro_f1"], -t["accuracy"], t["config"]["index"]))
        if usable
        else None
    )
