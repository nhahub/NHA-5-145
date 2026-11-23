# Seven-family synthetic development comparison — 7 October 2026

The owner approved extending the offline comparison to five classical classifiers and two frozen-embedding classifiers. This protocol is recorded before any new candidate fit. Existing pilots and runtime behaviour remain unchanged. No paid inference, cloud work, foundation-model training or encoder fine-tuning is included.

## Fixed data and selection

Use `pilot-20261007/release.json` unchanged: 210 training / 53 validation / zero unseen, ten labels, whole conversation/paraphrase components. Validate its source hashes before execution. Every family receives the same messages and labels. Training fits vocabulary, IDF, scaling and classifier parameters; validation is used only for scores and model selection. No additional context, translated messages, phrase rules, augmentation or relabeling.

This reuses previously inspected synthetic validation data. It is exploratory and selection-biased, not an independent comparison or final test. Report every attempted configuration, failure and nonconvergence; choose within each family by descending ten-label macro-F1, then accuracy, then ascending declared candidate index. Exclude nonconverged/failed fits from selection; if none remain, report that family unavailable. Do not expand the grid after scores or refit validation. Different tuning budgets and pretrained representations preclude a pure classifier-capacity causal claim.

## Predeclared grid

For the five classical families, use identical TF-IDF alternatives: word 1–2 grams with single-character tokens allowed, or `char_wb` 3–5 grams; default L2 normalization, no stop-word removal, no feature cap or dimensionality reduction. This preserves the old Logistic Regression reference. All stochastic fits use seed 42; Classifier CPU execution is limited to four threads. Before fitting, the owner authorized the RTX 3060 (12 GiB) for the frozen encoder; its CUDA device/build are recorded separately. Timing comparisons therefore include different hardware for embedding systems.

| Family                                  | Candidate settings                                                                                                                                | Fits |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ---- |
| TF-IDF Logistic Regression              | Both features × C {0.1, 1, 10} × weights {none, balanced}; lbfgs, max_iter 2000                                                                   | 12   |
| TF-IDF Linear SVM                       | Both features × C {0.1, 1, 10} × weights {none, balanced}; LinearSVC, dual auto, max_iter 10000                                                   | 12   |
| TF-IDF Complement Naive Bayes           | Both features × alpha {0.1, 1}; norm false                                                                                                        | 4    |
| TF-IDF Random Forest                    | Both features × max_depth {10, none}; 200 trees, balanced weights, sqrt features, min_samples_leaf 1                                              | 4    |
| TF-IDF XGBoost                          | Both features × max_depth {3, 6}; 100 trees, learning_rate 0.1, hist, multiclass softprob, min_child_weight 1, lambda 1, full row/column sampling | 4    |
| Frozen embeddings + Logistic Regression | C {0.1, 1, 10} × weights {none, balanced}; lbfgs, max_iter 2000                                                                                   | 6    |
| Frozen embeddings + MLP                 | One ReLU hidden layer {64, 128} × alpha {0.001, 0.01}; lbfgs, max_iter 1000, max_fun 15000, no early stopping                                     | 4    |

Total: **46 fits**, classical phase first (36), embedding phase second (10). Fixed seed comparisons do not measure seed variance. No post-result retuning.

The embedding encoder is `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, revision `e8f8c211226b894fcb81acc59f3b34ba3efd5f42`, CUDA when available (otherwise CPU with the fallback disclosed), 384 dimensions, maximum 128 tokens, mean pooling and L2-normalized output. Download only pinned configuration/tokenizer/safetensors files; disable remote code and inference APIs. Record local file hashes, truncation counts and encoder disk size. Downloading public weights is not a paid inference call. Encode splits separately with a frozen encoder; cache these fixed features for training, then fit a StandardScaler on training only for both embedding heads. The encoder is not fitted to our data.

## Evidence and timing

Publish per-family selected configuration, all trials and predictions, fixed-label metrics and confusion matrices, language slices, training time and warm single-message text-to-prediction p50/p95. Embedding inference timing must include tokenization and encoder execution, never just cached head prediction. CUDA encoding returns CPU arrays and explicitly synchronizes before returning, so GPU work is included. Record shared train/validation embedding preparation time separately from head fitting. Record trusted local artifact reload time and verify predictions; encoder initialization is separate and must not be described as total cold process startup. Record model bytes (head plus separately shared encoder for embedding systems), package versions, source/release/protocol hashes and invocation. Store binaries and embeddings locally under ignored outputs, not Git.

Persist partial trial evidence on exceptions; incomplete runs are explicitly incomplete and never presented as a completed family comparison. Refuse existing output directories. No training should happen merely by importing a module or running ordinary unit tests. Tests use small synthetic fixtures at fitting/selection/reporting boundaries; production safety regression tests remain unchanged.

The main question is which of these fixed approaches works best on this small development sample, not whether it can replace the runtime Intent Interpreter. CAP-02 independent evaluation and CAP-03 same-input LLM comparison remain open. Unmeasured compute cost remains unknown even though inference API calls are zero.

References checked 7 October 2026: [encoder model card](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2), [XGBoost Python API](https://xgboost.readthedocs.io/en/stable/python/python_api.html), [MLPClassifier](https://scikit-learn.org/stable/modules/generated/sklearn.neural_network.MLPClassifier.html).
