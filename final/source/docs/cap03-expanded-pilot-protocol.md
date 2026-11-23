# CAP-03 expanded synthetic pilot protocol — 7 October 2026

The owner approved continued synthetic development work while keeping final evaluation open. This is a second exploratory pilot using the expanded 308-record pool; the first pilot's source data, frozen release, code and score remain unchanged. All examples and annotations are development-exposed, including the new batch authored after pilot 1. No unseen, independent-gold or real-shopper quality claim is permitted.

## Before fitting

1. Retain all existing conversation/paraphrase components and adjudicated new links. Review the available legacy corpus/scenarios for additional connecting templates. Private chats/screenshots and live debugging material remain exposed and are not imported; exhaustive private-history deduplication cannot be established. The split is only group-separated synthetic development validation.
2. Use only the 263 provisionally eligible top-level intent rows. Preserve all 45 exclusions and context references. Do not train on the legacy corpus, browser tests or private logs in this run.
3. Freeze a new version with original annotation text/labels, source and context hashes, all group assignments and actual support before any candidate fit. Do not modify old release files or repair labels after scores.

## Allocation rule

The earlier desired three-training/one-validation-family target was an authoring heuristic. The supported mutation tasks have three known components; this pilot explicitly accepts at least two training components and one validation component per intent, including `mutate`. This changes experiment sampling only. Confirmation, action safety and final unseen-evaluation requirements are unchanged.

Allocate whole connected components. Require **at least eight training and four validation rows per intent**, at least **two training and one validation row per intent/language cell**, and at least **two training and one validation component per intent**. No row is moved individually to satisfy a count. If the constraints are infeasible after review, stop without fitting and report the conflict; do not silently relax them.

Prefer a validation count nearest 20% of eligible rows, rounded to an integer. Use integer optimization with one binary variable per component and absolute count-distance objective. Among optimal distances choose the lexicographically smallest assignment vector in sorted component-ID order (training=0, validation=1), by sequential feasibility checks. Record the SciPy version. Accept only optimal/feasible solver statuses, then independently validate actual integer counts and memberships. No model predictions enter allocation.

## Model experiment and reporting

Keep the first pilot's predeclared twelve configurations and preprocessing unchanged: word 1–2 grams or `char_wb` 3–5 grams, TF-IDF, Logistic Regression C in {0.1,1,10}, unweighted/balanced classes, lbfgs, max_iter=2000, seed42. Train vocabulary/IDF on training only. Select by ten-label validation macro-F1, then accuracy, word features, lower C and unweighted classes; exclude nonconverged fits and do not refit validation.

Use the existing offline runner. Preserve all trials, predictions, support, per-language/per-class metrics, confusion matrices, majority baseline, environment/source/model hashes and timings. Report this run separately: different synthetic examples and distributions mean a higher score would not establish a causal improvement or superiority to an LLM. No paid inference or runtime integration is authorized by this protocol. CAP-02 final release and CAP-03 final comparison remain open.

Implementation reference: [SciPy integer optimization](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html), checked 7 October 2026. The existing [model protocol](cap03-pilot-protocol.md) supplies the unchanged classifier grid; this document supplies the new data/allocation policy.
