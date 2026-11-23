# CAP-03 synthetic development pilot protocol

Approved by the owner on **6 October 2026**: prepare a synthetic development release and run an exploratory offline pilot, while leaving final unseen evaluation and the LLM comparison open. This is a scoped exception to the original data gate, not CAP-02/03 completion or a relaxation of runtime safety.

## Predeclared experiment

- Data: 40 language-model-generated cases plus 100 Gemini-generated messages, with reviewed draft labels and all provenance retained. Include only messages eligible for the text-only intent task; preserve exclusions with reasons.
- Annotation status: draft semantic review, not independent human verification. Missing context and multi-intent cases are excluded where one text-only target is not justified. No synthetic fixture is presented as an observed shopper interaction.
- Split: use the reviewed connected components of conversation and paraphrase links, never individual turns. Enumerate whole-component subsets and minimize distance to 20% of eligible cases (rounded to an integer), requiring every validation label to retain training support. Break ties by the smallest SHA-256 of `42:` followed by sorted component IDs joined with commas. Record actual support and any unsupported classes. No test/unseen split exists.
- Freeze records, group membership and split hashes before fitting any candidate. Labels may not be repaired after observing scores in this run.
- Fixed label order: `advice`, `find_products`, `locate`, `navigate`, `open_product`, `mutate`, `cart_edit`, `help`, `off_topic`, `unsupported`. Report all ten, including zero support.
- Features: word 1–2 grams or character-within-word 3–5 grams. Preserve original text, numerals, negation and script; no stop-word dictionary, transliteration or hand-built phrase features. Word tokenization includes single-character tokens. TF-IDF vocabulary/IDF is fitted only on training data through a pipeline.
- Estimator: Logistic Regression, `C` in {0.1, 1, 10}, `class_weight` in {None, balanced}, solver `lbfgs`, max iterations 2000, random state 42. Twelve configurations total. Capture all convergence warnings and exclude nonconverged configurations from selection.
- Select by validation macro-F1 over the fixed ten labels, then accuracy, then word features, lower C, then unweighted classes. Do not refit on validation afterward.
- Report per-case predictions, all trials, per-class and per-language metrics/support, raw and row-normalized confusion matrices, training duration and warm single-message transform/predict latency. Timing includes local feature extraction, not browser actions or model-network time.
- Persist model artifact, hashes, package versions, platform, command and source hashes. Loading a model uses only the just-created trusted artifact; never load an untrusted pickle/joblib file.

## Interpretation limits

Validation is used to select the model, so its score is optimistic development evidence, not an unbiased performance estimate. The small synthetic pool, linked language templates, rare classes, single annotation process and missing real-user examples limit generalization. Report majority-class performance alongside the trained candidates for context. No inference API calls or cloud resources are needed.

The pilot cannot demonstrate reliable Constraint extraction, conversation understanding, recommendation grounding, safe execution or superiority to an LLM. A future same-input LLM comparison needs separately authorized paid access, frozen configuration and transparent accounting; independent unseen evaluation remains outstanding. The classifier never enters the shopping runtime.

Method references checked 6 October 2026: [TF-IDF](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html), [Logistic Regression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html), [data leakage and pipelines](https://scikit-learn.org/stable/common_pitfalls.html). Installed versions are pinned in `eval/requirements-baseline.txt` and captured in the run report.
