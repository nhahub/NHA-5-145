# Seven-family exploratory model comparison

See [results and reproduction](../../../docs/cap03-model-comparison-results.md) and [pre-fit protocol](../../../docs/cap03-model-comparison-protocol.md).

- `classical.json`: 36 trials across five TF-IDF classifiers.
- `embeddings.json`: ten trials across two frozen-encoder classification heads; RTX 3060 encoding.
- `figures/`: overview and raw/normalized confusion matrices for all seven selected configurations.

Same 210-training / 53-validation / zero-unseen release. These are exposed synthetic development scores, selected on validation, with no independent gold or runtime-quality claim. Large models and embedding arrays stay in ignored local outputs; hashes are retained in the reports.
