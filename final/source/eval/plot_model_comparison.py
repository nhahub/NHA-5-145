"""Render recorded model comparison results without fitting any estimator."""

import argparse
import json
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def render(paths: list[Path], output: Path) -> None:
    reports = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    if len({r["release_sha256"] for r in reports}) != 1:
        raise ValueError("Cannot combine different releases")
    if any(r["status"] != "complete" for r in reports):
        raise ValueError("Incomplete comparison; inspect failures before plotting")
    families = [f for r in reports for f in r["families"]]
    if len({f["family"] for f in families}) != len(families):
        raise ValueError("Duplicate family results")
    output.mkdir(parents=True, exist_ok=False)
    labels = reports[0]["labels"]
    names = [f["family"] for f in families]
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(11, 5))
    for offset, metric, color in ((-0.2, "accuracy", "#197278"), (0.2, "macro_f1", "#C44536")):
        bars = ax.bar(
            x + offset, [f["validation"][metric] for f in families], 0.4, label=metric, color=color
        )
        ax.bar_label(bars, fmt="%.3f", fontsize=8)
    ax.set(
        xticks=x,
        xticklabels=names,
        ylim=(0, 1),
        ylabel="Validation score",
        title="Synthetic development comparison — 53 reused validation examples",
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / "comparison.png", dpi=160)
    plt.close(fig)
    for family in families:
        for key, matrix in family["confusion_matrices"].items():
            matrix = np.asarray(matrix)
            fig, ax = plt.subplots(figsize=(8, 7))
            im = ax.imshow(
                matrix, cmap="Blues", vmin=0, vmax=1 if key == "row_normalized" else None
            )
            ax.set(
                xticks=range(len(labels)),
                yticks=range(len(labels)),
                xticklabels=labels,
                yticklabels=labels,
                xlabel="Predicted intent",
                ylabel="Annotated intent",
                title=f"{family['family']} — {key} (development)",
            )
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
            for i in range(len(labels)):
                for j in range(len(labels)):
                    value = f"{matrix[i, j]:.2f}" if key == "row_normalized" else str(matrix[i, j])
                    ax.text(
                        j,
                        i,
                        value,
                        ha="center",
                        va="center",
                        fontsize=7,
                        color="white" if matrix[i, j] > matrix.max() / 2 else "black",
                    )
            fig.colorbar(im, ax=ax)
            fig.tight_layout()
            fig.savefig(output / f"{family['family']}-{key}.png", dpi=130)
            plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render(args.reports, args.output)


if __name__ == "__main__":
    main()
