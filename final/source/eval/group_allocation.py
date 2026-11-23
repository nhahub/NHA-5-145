"""Allocate synthetic development groups without using model predictions."""

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

LANGUAGES = ("egyptian_arabic", "franco_arabic", "english", "mixed")


def allocate(rows: list[dict]) -> dict[str, str]:
    groups = sorted({r["group"] for r in rows})
    labels = sorted({r["label"] for r in rows})
    if not groups or not labels:
        raise ValueError("Allocation infeasible: empty input")
    positions = {g: i for i, g in enumerate(groups)}
    width = len(groups) + 1  # Last variable is integer absolute count distance.
    matrix, low, high = [], [], []

    def counts(subset: list[dict]) -> np.ndarray:
        vector = np.zeros(width)
        for row in subset:
            vector[positions[row["group"]]] += 1
        return vector

    def constraint(vector: np.ndarray, lower: float, upper: float) -> None:
        if upper < lower:
            raise ValueError("Allocation infeasible: insufficient support")
        matrix.append(vector)
        low.append(lower)
        high.append(upper)

    for label in labels:
        labelled = [r for r in rows if r["label"] == label]
        vector = counts(labelled)
        constraint(vector, 4, len(labelled) - 8)
        presence = (vector > 0).astype(float)
        constraint(presence, 1, sum(presence) - 2)
        for language in LANGUAGES:
            cell = [r for r in labelled if r["language"] == language]
            constraint(counts(cell), 1, len(cell) - 2)

    target = round(len(rows) * 0.2)
    total = counts(rows)
    upper_distance, lower_distance = total.copy(), -total.copy()
    upper_distance[-1] = lower_distance[-1] = -1
    constraint(upper_distance, -np.inf, target)
    constraint(lower_distance, -np.inf, -target)
    a = np.array(matrix)
    lo, hi = np.zeros(width), np.ones(width)
    hi[-1] = len(rows)
    constraints = LinearConstraint(a, low, high)

    def solve(objective: np.ndarray):
        result = milp(
            objective,
            integrality=np.ones(width),
            bounds=Bounds(lo, hi),
            constraints=constraints,
            options={"mip_rel_gap": 0.0, "time_limit": 10.0},
        )
        if result.status == 2:
            return None
        if result.status != 0:
            raise ValueError(f"Allocation solver did not finish: {result.message}")
        return result

    objective = np.zeros(width)
    objective[-1] = 1
    optimal = solve(objective)
    if optimal is None:
        raise ValueError("Allocation infeasible under predeclared support constraints")
    lo[-1] = hi[-1] = round(optimal.x[-1])
    # Keep optimal distance, then choose a unique lexicographic assignment.
    for index in range(len(groups)):
        hi[index] = 0
        if solve(np.zeros(width)) is None:
            lo[index] = hi[index] = 1

    actual = a @ lo
    if np.any(actual < np.asarray(low) - 1e-8) or np.any(actual > np.asarray(high) + 1e-8):
        raise ValueError("Allocation failed independent integer constraint check")
    return {g: "validation" if lo[i] else "train" for i, g in enumerate(groups)}
