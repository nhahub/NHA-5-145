# CAP-03 exploratory synthetic pilot — 6 October 2026

The offline experiment ran successfully, but classification quality is weak. **4 of 21 validation examples were correct (19.05% accuracy; ten-label macro-F1 0.1024).** This is development evidence selected on validation, not an unseen test result or a measure of the shopping assistant's quality. CAP-02 final evaluation and CAP-03's final comparison remain open.

## Data and experiment

The owner approved a synthetic pilot exception on 6 October. The [predeclared protocol](cap03-pilot-protocol.md) and [frozen release](../eval/datasets/capstone-v1/pilot-20261006/release.json) cover 40 language-model-generated examples and 100 Gemini-generated messages. The original intake is preserved. Draft annotations do not constitute independent human gold labels.

- 103 eligible top-level intent examples; 37 excluded with individual reasons.
- 82 training / 21 validation / **0 unseen**; 15 connected conversation/paraphrase components remain intact.
- The largest component contains 104 original records (69 eligible). Splitting it for balanced scores would leak related cases.
- All twelve TF-IDF + Logistic Regression configurations converged. Selection used validation macro-F1, with the declared tie-breakers; no refitting on validation followed.
- Selected: word 1–2 grams, `C=0.1`, balanced class weights. Vocabulary and IDF were fitted on training only.
- No runtime, prompt, phrase rules, provider configuration or spending cap changed. **Zero inference API calls.**

## Results and coverage

| Method                                         | Correct / validation | Accuracy | Macro-F1, fixed ten labels |
| ---------------------------------------------- | -------------------- | -------- | -------------------------- |
| Selected TF-IDF + Logistic Regression          | 4 / 21               | 19.05%   | 0.1024                     |
| Always predict training majority (`cart_edit`) | 1 / 21               | 4.76%    | 0.0091                     |

| Intent        | Training | Validation |
| ------------- | -------- | ---------- |
| advice        | 16       | 1          |
| find_products | 23       | 3          |
| locate        | 3        | 0          |
| navigate      | 1        | 8          |
| open_product  | 2        | 0          |
| mutate        | 1        | 7          |
| cart_edit     | 29       | 1          |
| help          | 2        | 0          |
| off_topic     | 1        | 0          |
| unsupported   | 4        | 1          |

Only six classes have validation support. Navigate and mutate each have just one training example; together they account for 15 of 21 validation examples. This severe distribution imbalance is a consequence of this small grouped pool, not evidence of a broadly representative evaluation. Four absent classes contribute zero to the predeclared ten-label macro-F1; their capabilities were not evaluated.

| Language group  | Validation count | Correct | Accuracy |
| --------------- | ---------------- | ------- | -------- |
| Egyptian Arabic | 5                | 0       | 0%       |
| Franco-Arabic   | 7                | 2       | 28.57%   |
| English         | 5                | 2       | 40%      |
| Mixed           | 4                | 0       | 0%       |

These tiny, differently composed subsets do not establish relative language quality. Every prediction, all twelve trials and per-class metrics are retained in the [machine-readable report](../eval/evidence/cap03-pilot-20261006/report.json). The [raw confusion matrix](../eval/evidence/cap03-pilot-20261006/confusion-raw.png) and [normalized matrix](../eval/evidence/cap03-pilot-20261006/confusion-row_normalized.png) show the full label order, including unsupported classes.

Warm single-message feature extraction and prediction: p50 **0.441 ms**, p95 **0.640 ms**, 21 samples. Reloading the just-written model with a warm OS cache took **8.516 ms**. These timings are local observations, excluding process start, network, LLM inference and browser execution; they are not production latency estimates. Local compute cost was not measured.

## Reproduce and inspect

From the repository root, using Python 3.12 in an isolated environment:

```powershell
python -m pip install -r eval/requirements-baseline.txt
python -m eval.baseline_pilot --release eval/datasets/capstone-v1/pilot-20261006/release.json --output outputs/baseline-pilot/run-002
```

Use a fresh output directory. Source hashes and annotation/component bindings are checked before training. The frozen release is already included; do not edit it after seeing results. To check deterministic allocation independently, generate a temporary copy with `python -m eval.freeze_pilot --output outputs/baseline-pilot/reconstructed-release.json` and compare its JSON content with the frozen release.

The report records the exact command, release/source/model hashes, pre-experiment Git HEAD, all configurations and package/platform versions. The run happened on uncommitted experiment code atop that HEAD; recorded source hashes identify the executed files. `outputs/baseline-pilot/run-001/model.joblib` remains an ignored local artifact; a fresh run recreates a model. Never load an untrusted pickle/joblib artifact. Reruns may differ in timing and serialized bytes across environments.

## What this changes next

The pipeline is usable for further offline experiments. The data is not sufficient for final quality claims. Add independent conversation families with meaningful training and held-out support for every intent; preserve typos, negation and all four language groups. Record provenance and review labels before a new version is frozen. Future unseen examples must remain outside development access until evaluation.

Do not tune or relabel this release to repair the observed failures. Any revised dataset or experiment must be a new, explicitly development-exposed version. A same-input LLM comparison remains unrun and needs an agreed evaluation release and separately authorized inference budget. No superiority claim can be made from this pilot.
