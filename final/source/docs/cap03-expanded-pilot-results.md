# CAP-03 expanded synthetic pilot — 7 October 2026

The unchanged offline baseline classified **20 of 53 validation examples correctly (37.74% accuracy; ten-label macro-F1 0.3776)**. All ten labels now have training and validation support. This remains a weak classifier on exposed synthetic development data; it is not an unseen result or a measurement of the Shopping Copilot runtime. CAP-02 final release and CAP-03 final comparison remain open.

## Release and allocation

The [pre-fit protocol](cap03-expanded-pilot-protocol.md) and [frozen release](../eval/datasets/capstone-v1/pilot-20261007/release.json) retain all 308 source records through 263 scored candidates and 45 documented exclusions. Every draft remains synthetic/exposed; draft review is not independent human gold. No annotation or split was changed after fitting.

The [bounded overlap review](../eval/datasets/capstone-v1/development/pilot2-overlap-review.json) added four conservative links to the earlier graph, preserving all inherited links. Its 37 components stay whole; the largest contains 137 original records. It is not exhaustive deduplication of private development history. The new allocation contains **210 training / 53 validation / zero unseen**. Every label has at least eight training and four validation rows, two training and one validation components, and two training/one validation rows in each language. The earlier four-family authoring target was explicitly revised before fitting; mutation has only three components.

## Results

All twelve predeclared configurations converged. Selected: character `char_wb` 3–5 grams, Logistic Regression `C=0.1`, balanced class weights. Vocabulary and IDF use training only; model selection uses validation macro-F1 and the declared tie-breakers, without a validation refit.

| Method                                | Correct / validation | Accuracy | Ten-label macro-F1 |
| ------------------------------------- | -------------------- | -------- | ------------------ |
| Selected TF-IDF + Logistic Regression | 20 / 53              | 37.74%   | 0.3776             |
| Training majority (`cart_edit`)       | 4 / 53               | 7.55%    | 0.0140             |

| Intent        | Training | Validation | Correct | F1     |
| ------------- | -------- | ---------- | ------- | ------ |
| advice        | 29       | 4          | 0       | 0.0000 |
| find_products | 38       | 4          | 3       | 0.5000 |
| locate        | 15       | 4          | 2       | 0.6667 |
| navigate      | 20       | 5          | 2       | 0.3636 |
| open_product  | 14       | 4          | 4       | 0.6154 |
| mutate        | 20       | 4          | 0       | 0.0000 |
| cart_edit     | 42       | 4          | 4       | 0.8889 |
| help          | 14       | 4          | 1       | 0.2000 |
| off_topic     | 9        | 8          | 1       | 0.1667 |
| unsupported   | 9        | 12         | 3       | 0.3750 |

| Language        | Validation | Correct | Accuracy |
| --------------- | ---------- | ------- | -------- |
| egyptian_arabic | 13         | 5       | 38.46%   |
| english         | 14         | 5       | 35.71%   |
| franco_arabic   | 13         | 3       | 23.08%   |
| mixed           | 13         | 7       | 53.85%   |

Advice and guarded mutation each scored 0/4. The four advice cases were assigned to product search, product opening or help; the four mutation cases to navigation, product opening or help. Unsupported requests scored 3/12, with three misclassified as mutation. These are offline label errors, not executed Actions. Open-product and cart-edit each scored 4/4, but four examples cannot establish dependable behaviour. Language subsets are small and differently composed, so do not rank language capability from this table.

Pilot 1 scored 19.05% on a different 21-row validation set. This run changes the data and distribution, so the higher number is not a controlled gain or evidence of superiority to an LLM. The second batch was authored after pilot 1; neither score is unbiased final evaluation. No LLM comparison ran.

All trials, predictions, per-class/language metrics and provenance are in the [report](../eval/evidence/cap03-pilot-20261007/report.json), with [raw](../eval/evidence/cap03-pilot-20261007/confusion-raw.png) and [row-normalized](../eval/evidence/cap03-pilot-20261007/confusion-row_normalized.png) confusion matrices. The unchanged runner emits a generic “rare and absent classes” limitation: in this release all ten classes are present; small support remains the applicable limitation.

Warm single-message prediction: p50 **0.490 ms**, p95 **0.622 ms**, 53 samples. Model load with a warm OS cache: **17.163 ms**. Local browser tests ran concurrently; these are incidental local timings, excluding process startup, network, inference APIs and browser execution. Local compute cost was not measured. **Zero inference API calls.**

## Reproduce

With Python 3.12 and the evaluation dependencies installed, use a fresh output directory:

```powershell
python -m pip install -r eval/requirements-baseline.txt
python -m eval.baseline_pilot --release eval/datasets/capstone-v1/pilot-20261007/release.json --output outputs/baseline-pilot/reproduction-002
```

The checked-in release is already frozen. To reconstruct allocation without fitting, install the repository Node/pnpm dependencies (`pnpm install --frozen-lockfile`) and use `python -m eval.freeze_expanded_pilot --output outputs/baseline-pilot/reconstructed-pilot2`. The exporter formats, validates and hashes staged JSON before publishing the directory. Compare records, assignments and group membership: the reconstructed release has a different group-map path and corresponding hash entry. Existing output is refused.

The report pins the unchanged runner and original model protocol; the release separately pins the new allocator, exporter, allocation protocol, annotations, context and group graph. The run used uncommitted experiment additions atop Git HEAD `9b5c297`; hashes identify their content. The ignored local model is `outputs/baseline-pilot/run-002/model.joblib`. Reruns may change timing and serialized model bytes across environments; never load untrusted joblib/pickle artifacts.

## Remaining work

Keep both pilots immutable. Final CAP-02 still needs a defensible independent evaluation arrangement and reviewed labels; final CAP-03 needs the same-input LLM comparison with separately authorized inference spending. This experiment adds no runtime classifier, prompt changes, phrase rules, API calls or cloud resources.
