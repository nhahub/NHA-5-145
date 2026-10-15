# CAP-01: Literature Review

Updated: 2026-10-16. Track: AWS ML Engineering. Published DEPI submission target: 16 October 2026. Status: prepared for submission, aligned with the [supplied guidelines](depi-guideline-alignment.md). This is a focused review of seven primary sources, not a systematic review or an exhaustive survey of the latest models.

The updated guidelines title section 2 “Literature Review” but list lecturer feedback, improvements and grading criteria; the original guide titles the same material “Lecturer Review”. Retain this research synthesis and the separate [lecturer review record](cap01-lecturer-review.md) pending clarification. This document does not invent lecturer feedback or claim it fulfills an unspecified grading rubric.

**Actual working arrangement (2 October 2026):** the owner and coding assistant perform the work; the owner coordinates this deliverable. Earlier named academic leads were administrative allocations, not verified contributions or available staffing. See the updated [CAP-01 register](cap01-execution.md).

## Purpose and scope

Shopping Copilot combines natural-language shopping assistance, catalogue-grounded advice and controlled browser Actions. The research problem therefore spans three different questions: identifying intent, helping a Shopper make a decision, and executing the selected task correctly. A classification score cannot answer all three. This review examines prior work relevant to those boundaries and motivates the approved dataset and comparison methodology.

The project currently demonstrates one Controlled Storefront. Its [MVP results](../RESULTS.md) distinguish historical live acceptance, current automated checks and informal feedback. Five positive participant reactions motivate the advice feature but do not establish comparative effectiveness. The classical-model development experiments have now been run; AWS delivery, independent unseen evaluation and the final same-input LLM comparison remain open.

## Classical intent classification as a bounded comparison

Scikit-learn's `TfidfVectorizer` learns a vocabulary and inverse document frequencies from training documents, then represents text numerically. It supports word and character n-grams, including character features restricted to word boundaries. Its default word tokenization excludes single-character tokens, a relevant implementation detail when short shopping messages contain numerals. These documented options support an explicit preprocessing experiment rather than assuming that default English-oriented settings suit every input. [Scikit-learn, TfidfVectorizer](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html).

`LogisticRegression` provides regularized classification with sparse inputs and multiclass support under suitable solvers. Its documentation identifies `C` as inverse regularization strength and provides class-weighting options. These properties make it a practical, inspectable comparator for labelled intent data; they do not establish its accuracy on this project's messages. [Scikit-learn, LogisticRegression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html).

The approved [CAP-03 requirements](cap01-requirements.md#graduation-ml-and-deployment-requirements) consequently compare TF-IDF plus Logistic Regression with an LLM on one shared subtask: assigning an intent label to the same self-contained message. Learned preprocessing uses training data only; validation selects settings before unseen evaluation. Context-dependent requests receive separate treatment because a message-only classifier cannot fairly be compared with an LLM receiving extra conversation and page information. This baseline is an offline experiment, not a fallback phrase interpreter or an authority for browser Actions.

## Multilingual coverage and naturally mixed language

MASSIVE separates intent classification from slot filling and evaluates multilingual understanding through a parallel dataset covering 51 languages. Its utterances were produced by professional localization of an English virtual-assistant corpus. This offers a useful example of explicit language coverage and separate understanding metrics. However, translation-based multilingual coverage does not by itself demonstrate performance on spontaneous Egyptian Arabic, typing mistakes or Franco-Arabic shopping conversations. That limitation is an inference about transfer to our target setting, not a claim that MASSIVE was designed to solve it. [FitzGerald et al., 2023](https://aclanthology.org/2023.acl-long.235/).

ArzEn-ST studies Egyptian Arabic-English code switching using a speech-translation corpus derived from informal bilingual interviews, with translations into both languages. It provides direct evidence that naturally mixed Egyptian Arabic-English warrants dedicated data collection and evaluation. Its task is speech and translation, rather than shopping intent classification; its corpus and results cannot be treated as this project's benchmark. [Hamed et al., 2022](https://aclanthology.org/2022.wanlp-1.12/).

For CAP-02, these distinctions motivate collecting original messy requests across Egyptian Arabic, English, Franco-Arabic and mixed-language groups. The project should retain exclusions, corrections, ambiguous references and spelling variation rather than sanitizing them into ideal prompts. Related paraphrases and conversation turns remain in the same split. Existing cases exposed during development stay labelled as exposed. Language-group support counts and annotation disagreements must accompany results so that a small subgroup cannot silently support a broad multilingual claim.

## Grounded shopping assistance and interactive execution

WebShop frames shopping as an interactive task: an agent navigates a simulated ecommerce environment, interprets product requirements, selects options and purchases an item. Its tasks require more than identifying a request category, including reformulating searches and using webpage information. This supports evaluating product selection and completed interaction separately from text classification. However, WebShop's environment, products, training methods and evaluation are distinct from Shopping Copilot; its reported performance is not a baseline score for this repository. [Yao et al., 2022](https://arxiv.org/abs/2207.01206).

ReAct investigates interleaving language-model reasoning and task-specific actions, allowing observations from an environment to inform subsequent decisions. It gives a research precedent for updating decisions from external evidence instead of relying on an initial response alone. This project does not claim to reproduce ReAct: its Structured Intent, deterministic planning and Confirmation boundaries are its own design. ReAct also cannot be cited as proof that generated explanations are factual or that a proposed action is authorized. [Yao et al., 2023](https://arxiv.org/abs/2210.03629).

The project's synthesis is to keep conversational advice grounded in fresh Catalogue Facts while preserving a separate execution boundary. A factual explanation of price or material needs catalogue support; a Styling Suggestion may express a preference but must remain identifiable as opinion. Missing comfort, durability or suitability evidence should remain unknown. This design responds to local feedback asking for comparisons and decision support. Whether explanations improve decisions still requires evaluation; fluent language alone is insufficient evidence.

## Task completion and safety evidence

WebArena supplies reproducible, functional websites and evaluates task completion across several domains. Its emphasis on functional correctness is particularly relevant: an apparently reasonable response or click sequence does not necessarily produce the required final state. The paper motivates environment-level evaluation, but does not validate our implementation or establish independent-store generalisation. [Zhou et al., 2024](https://proceedings.iclr.cc/paper_files/paper/2024/hash/4410c0711e9154a7a2d26f9b3816d1ef-Abstract-Conference.html).

For Shopping Copilot, successful execution must be considered alongside safety, including observed-target validation, off-origin blocking, Sensitive Field exclusion, bound Confirmation and stale/duplicate Action rejection. These are project requirements, not guarantees inherited from a published benchmark. Evaluation should distinguish interpretation errors, unsupported advice, incorrect state transitions and provider failures. Recovery must not automatically replay an Action whose outcome is uncertain. Historical and current evidence must remain separately identified when prompts or schemas change.

## Research questions and planned evidence

The following questions operationalize the review without presupposing a winning model:

1. **Shared intent task:** how do the classifier and LLM differ in accuracy, macro-F1 and per-class errors on the same untouched eligible messages? CAP-03 will report all predefined classes and support counts.
2. **Language variation:** which mistakes occur in each language group, particularly around negation, typos and confusable intentions? CAP-02 supplies reviewed labels and split provenance; small groups remain explicitly limited.
3. **Value of context:** which requests require conversation or Storefront observations to interpret correctly? A separate contextual evaluation will avoid attributing extra information to model superiority.
4. **Advice and action quality:** does advice distinguish verified facts, opinions and unknowns, and does a subsequent Action produce the intended state while preserving safety? These remain application evaluations rather than classifier metrics.
5. **Operational trade-offs:** what quality, latency and measured cost differences arise under recorded configurations, including invalid responses and repairs? Timing comparisons will use the same subtask and disclose hardware and network boundaries.

### Current exploratory evidence and research implications

The [7 October offline comparison](cap03-model-comparison-results.md) tested seven families and 46 candidate configurations on 210 training and 53 validation examples. All examples were synthetic/exposed, and validation selected the configurations; there were zero unseen cases. Frozen multilingual embeddings plus Logistic Regression led at 23/53 correct (43.40%) and macro-F1 0.4304. TF-IDF plus Logistic Regression achieved 20/53 (37.74%) and macro-F1 0.3776. Full confusion matrices, language results, failed predictions and timings are retained in the report and [executed notebook](../notebooks/cap03-model-comparison.ipynb).

These results motivate further data and label-quality work, not a claim of reliable model superiority. Different features include different pretraining exposure and tuning budgets; differences of a few validation examples do not establish generalisation. The fair LLM comparison must still use an independent, frozen set with matched input information. CAP-02 final data and CAP-03 final evaluation remain open; no result here establishes production readiness or independent retailer compatibility.

## Bibliography

Sources were originally accessed **2026-10-01**; the seven primary-source URLs were reopened for this 16 October submission review. Documentation pages are living references; the experiment records its installed library versions separately. Source findings and project results remain distinct.

1. Scikit-learn developers. (n.d.). [TfidfVectorizer: API reference](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html). Official documentation.
2. Scikit-learn developers. (n.d.). [LogisticRegression: API reference](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html). Official documentation.
3. FitzGerald, J., et al. (2023). [MASSIVE: A 1M-Example Multilingual Natural Language Understanding Dataset with 51 Typologically-Diverse Languages](https://aclanthology.org/2023.acl-long.235/). ACL. Preprint first appeared in 2022.
4. Hamed, I., Habash, N., Abdennadher, S., & Vu, N. T. (2022). [ArzEn-ST: A Three-way Speech Translation Corpus for Code-Switched Egyptian Arabic-English](https://aclanthology.org/2022.wanlp-1.12/). WANLP.
5. Yao, S., Chen, H., Yang, J., & Narasimhan, K. (2022). [WebShop: Towards Scalable Real-World Web Interaction with Grounded Language Agents](https://arxiv.org/abs/2207.01206). NeurIPS.
6. Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., & Cao, Y. (2023). [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629). ICLR. Preprint first appeared in 2022.
7. Zhou, S., et al. (2024). [WebArena: A Realistic Web Environment for Building Autonomous Agents](https://proceedings.iclr.cc/paper_files/paper/2024/hash/4410c0711e9154a7a2d26f9b3816d1ef-Abstract-Conference.html). ICLR. Preprint first appeared in 2023.
