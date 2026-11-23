# Experiment notebooks

[CAP-02/03 synthetic holdout](cap03-synthetic-holdout.ipynb) contains the completed 9 October comparison of seven frozen classifiers and Gemini on 120 new synthetic messages. Its Run All reads evidence only, recomputes metrics and verifies release hashes. See [closeout](../docs/cap02-cap03-closeout.md) for the approved scope and limits.

[CAP-03 seven-model comparison](cap03-model-comparison.ipynb) presents the recorded 7 October 2026 experiment with executed tables, figures, all 46 trials, language slices, selectable model error analysis and reproduction instructions.

## Open and use

Open the `.ipynb` in VS Code with its Jupyter extension and select the project's `.venv` Python kernel, or use JupyterLab. Saved outputs are included, so a notebook viewer can display results without installing the training stack.

To execute the analysis cells, the Python environment needs `ipykernel` (which supplies IPython). Run from within this checkout so the notebook can locate the evidence directory. For a browser-based editor:

```powershell
python -m pip install jupyterlab ipykernel
python -m jupyterlab notebooks/cap03-model-comparison.ipynb
```

**Run All only reads local evidence.** It does not train models, download weights, load joblib files or call a model provider. No GPU or provider key is needed to inspect results. Optional retraining commands are Markdown instructions and are never executed by Run All.

Change `selected_family` in section 5 to inspect another model, then rerun its detail and error cells. Valid values: `lr`, `svm`, `nb`, `rf`, `xgb`, `embedding_lr`, `embedding_mlp`.

## Evidence and limits

The notebook validates release/source hashes and recomputes selected accuracy and macro-F1 from predictions. If a pinned source changes, it deliberately fails; use the matching experiment revision rather than editing away the check. Source reports remain in `eval/evidence/cap03-comparison-20261007/`. Large models and weights remain in ignored local outputs.

This is a synthetic development comparison: 210 training / 53 reused validation / zero unseen cases. It does not establish live Shopping Copilot quality, independent generalization or runtime replacement. See the [full results](../docs/cap03-model-comparison-results.md) and [protocol](../docs/cap03-model-comparison-protocol.md).

Validation for this notebook: nbformat validation, clean-kernel execution of every code cell, saved error-free outputs and independent review. No training or application-source change accompanies it; the application regression suite was not rerun for this presentation artifact.
