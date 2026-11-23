# CAP-02 / CAP-03 closeout — 9 October 2026

**Status: closed under the owner's approved synthetic-benchmark scope amendment.**
The original independent-human evaluation requirement is superseded for these two
academic tickets; its absence is a limitation, not a completed collection activity.
See [approved scope](cap02-cap03-closeout-plan.md).

## Dataset and methodology

CAP-02 releases [120 reviewed synthetic test records](../eval/datasets/capstone-v1/holdout-20261009/README.md),
three per ten-intent/four-language cell, in 44 related-family groups. Existing
210-training/53-validation assignments and all historical evidence remain unchanged.
No new test record was fitted or used to select a model/prompt. Candidate artifacts,
labels, LLM prompt/schema and settings were committed at `f2695b1` before authoring;
reviewed data and runner were committed at `7e20365` before predictions.

The cases were generated with a language model and every draft was reviewed
against the label guide; a planned second review was not completed. No human
labels, participant transcripts or nominal-team contributions are invented. The
lexical audit examined 2,199 candidate strings from 169 accessible development,
regression and debug sources, finding no exact normalized duplicate. Prior private
history is not exhaustively available. Shared capabilities and scenario semantics
remain, so this is **not scenario-family-independent or real-world unseen evidence**.
Some messages deliberately clarify what the shopper does not want and are longer
than spontaneous traffic; this may make classification easier. Language groups are
balanced by design, not estimates of natural prevalence.

CAP-03 applies the seven previously selected model artifacts without refitting and
compares them with `google/gemini-2.5-flash` on exactly the same raw messages and ten
labels. The LLM receives fixed label definitions but no examples, catalogue, cart,
conversation history or answers. Prior pretraining/supervision differs by approach;
equal per-case inputs do not mean equal total training information. One provider
attempt per case, no repair or score-driven retry. This is top-level **intent-only**
classification: constraints, quantities, grounding, clarification, safety and full
browser task completion have no measured denominator in this experiment.

## Results

| Frozen contender                              | Correct / 120 | Accuracy | Macro-F1 | Warm/request p50 ms |   p95 ms |
| --------------------------------------------- | ------------: | -------: | -------: | ------------------: | -------: |
| TF-IDF Logistic Regression                    |            69 |   57.50% |   0.5646 |               0.917 |    1.256 |
| TF-IDF Linear SVM                             |            63 |   52.50% |   0.4864 |               0.792 |    1.188 |
| TF-IDF Complement Naive Bayes                 |            74 |   61.67% |   0.5837 |               0.945 |    1.266 |
| TF-IDF Random Forest                          |            46 |   38.33% |   0.3664 |              24.271 |   25.075 |
| TF-IDF XGBoost                                |            40 |   33.33% |   0.3268 |               1.470 |    1.777 |
| Frozen embeddings + Logistic Regression       |            59 |   49.17% |   0.4702 |              15.019 |   17.342 |
| Frozen embeddings + MLP                       |            55 |   45.83% |   0.4259 |              14.897 |   17.633 |
| Gemini 2.5 Flash, fixed classification prompt |           120 |  100.00% |   1.0000 |            1476.860 | 4159.357 |

All eight contenders have 120 predictions and zero prediction/request failures.
The perfect LLM score is confined to this authored classification set. It neither
establishes 100% real-shopper accuracy nor replaces the runtime's safety/evaluation
evidence. These are different messages from the earlier validation set; higher
scores do not demonstrate improvement from training changes (there were none).

Complement Naive Bayes is the strongest classical result on this test; we do not
retune or replace the runtime based on this ranking. It gets 19/30 Arabic, 15/30
Franco-Arabic, 19/30 English and 21/30 mixed messages right. Its weakest classes are
`off_topic` and `unsupported`, each 2/12; guarded mutation is 6/12. Embedding LR is
9/30 on Franco-Arabic and 0/12 on off-topic. Full per-class/language metrics, raw and
normalized matrices and every error are preserved. More model complexity did not
consistently help this small training corpus.

Retain the LLM as the runtime interpreter: these frozen lightweight classifiers
are faster but lack reliable coverage even for the narrower intent-only task,
and they do not extract constraints, advise or execute shopping workflows. This
experiment does not qualify any AWS/Bedrock model; that remains CAP-05 work.

## Cost, timing and startup incident

The 120 paid calls cost **$0.0148178**, all costs known, against an approved maximum
**$0.20** within the unchanged **$2 total, non-resetting key cap**. No additional
deposit, auto top-up, cap increase or AWS resource. The ledger durably reserves each
request before dispatch; interrupted attempts never replay automatically and unknown
cost would retain its reservation. Provider usage is measured; local compute and
electricity costs are not. No invented zero total cost for local classifiers.

Local classifiers and frozen encoder ran on CPU with four threads for this test;
the earlier training experiment used the RTX 3060 for embedding preparation. Local
single-request timing includes vectorization or fresh tokenization/encoder/head,
after one non-test warm-up. LLM timing includes network and key checks. Environment,
load/warm-up times and token usage are included in evidence; these measurements are
not comparable with the multi-call, multi-action shopping latency.

The original offline run's two embedding families stopped before prediction because
the cache loader asked for unused ONNX/OpenVINO/other repository files. The explicit
recovery uses only the original hash-verified encoder-file manifest, without a new
download, retraining or parameter change. Five completed classifier results were
retained verbatim; the two embedding families then made their first predictions.
`initial-offline.json` preserves failures and `recovery.json` records the recovery.
The executed recovery source is preserved as `recovery-source.py.txt`; its hash is
recorded. The tracked recovery module only wraps the same explanatory string for
lint compliance after execution. No failed predictions were silently rerun.

## Inspect and reproduce

Open the [executed holdout notebook](../notebooks/cap03-synthetic-holdout.ipynb).
Run All only reads evidence; it recomputes accuracy/macro-F1 and checks dataset
hashes. No model loading, training, download or API request occurs in the notebook.
The [historical notebook](../notebooks/cap03-model-comparison.ipynb) is preserved.
Machine-readable evidence lives under [cap03-holdout-20261009](../eval/evidence/cap03-holdout-20261009/README.md).

Use Python 3.12 and the evaluation dependencies recorded in the prior comparison;
artifact/encoder bytes must match the frozen protocol. Trusted model binaries and
private debug sources remain outside Git. Consequently, reproducing inference needs
those local artifacts and audited sources; a clean clone can inspect/recompute the
published metrics but cannot re-verify absent private audit files or deserialize
absent models. Do not bypass hash checks or present newly trained artifacts as the
original model bytes. The earlier comparison documents reproduction of training.

Original commands (from the worktree; credentials were loaded privately, never
written into commands or published evidence):

```powershell
python -m eval.holdout_eval offline --release eval/datasets/capstone-v1/holdout-20261009/release.json --output outputs/holdout-20261009 --artifact-root "D:/agent depi" --encoder-cache "D:/agent depi/outputs/model-cache"
python -m eval.holdout_eval llm --release eval/datasets/capstone-v1/holdout-20261009/release.json --output outputs/holdout-20261009 --artifact-root "D:/agent depi"
python -m eval.holdout_recovery --release eval/datasets/capstone-v1/holdout-20261009/release.json --initial outputs/holdout-20261009/offline.json --output outputs/holdout-20261009-recovery --artifact-root "D:/agent depi" --cache "D:/agent depi/outputs/model-cache"
python -m eval.holdout_eval report --release eval/datasets/capstone-v1/holdout-20261009/release.json --output outputs/holdout-20261009-recovery --artifact-root "D:/agent depi"
```

The canonical paid ledger prevents another paid pass by merely selecting a new
output directory. Do not reset it to obtain a better score. A new paid experiment
requires a separate approved protocol/allowance; this consumed holdout is exposed.

## Verification and next gate

567 non-browser Python tests passed after the runner/release work; four additional
startup-recovery tests passed. The prior full application suite already covered the
unchanged runtime, and occupied manual browser services were preserved. Dataset/hash,
coverage, budget/no-replay, failure-denominator and exact-payload reservation checks
pass. Notebook clean-kernel execution completed without errors; plots were rendered
and the comparison chart visually inspected. Ruff and repository Prettier checks pass.

Spec review found two overlap-audit omissions and one source-hash coverage gap; all
were fixed before evaluation. A second label review was not completed
and is not claimed. A single review pass completed the labels and final report. This
is the documented level of review, not independent human gold or a completed second
external sign-off.

CAP-02 and CAP-03 are complete **under the amended synthetic scope**. Independent
human/real-shopper evaluation is a future limitation rather than an unfinished item
inside these amended tickets. CAP-04 is next: approved credit-only architecture,
public HTTPS and abuse/budget controls, followed by CAP-05 model qualification.
No application source change, push or cloud deployment accompanies this closeout.
