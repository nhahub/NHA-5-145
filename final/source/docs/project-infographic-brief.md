# Shopping Copilot: project infographic content

Prepared: **2 October 2026**. This is the content/layout brief, not the final image or presentation export. Sources: [planning](cap01-project-planning.md), [design](system-analysis-design.md), [results](../RESULTS.md), [dataset status](capstone-dataset.md), and the supplied guides indexed in [submission alignment](depi-guideline-alignment.md).

Export update, **6 October 2026**: the [2560×1440 image and editable slide](../output/infographic/README.md) are available and visually checked. Final comparison and AWS delivery remain roadmap work; the separate [synthetic pilot](cap03-pilot-results.md) does not complete their acceptance gates.

## Required canvas and identity

- One landscape slide/image, 16:9; preferred 2560×1440, minimum 1920×1080.
- Header: **DEPI — Digital Egypt Pioneers Initiative**; **Track: AWS ML Engineering** (confirmed by owner on 2 October).
- Project title: **Shopping Copilot**.
- Summary: **Arabic-first product advice and controlled shopping actions**.
- Use the supplied official logo if extracted cleanly; otherwise use a DEPI wordmark. Keep branding compact and text readable.

## Left-to-right content

| Block              | Short content                                                                       | Status treatment                                                                         |
| ------------------ | ----------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Shopper need       | Compare choices; express needs naturally; keep control                              | Project motivation, not a measured market claim.                                         |
| Local solution     | Catalogue-grounded advice; product discovery; cart edits + Undo                     | Implemented local MVP.                                                                   |
| Execution boundary | LLM interprets; runtime checks targets and stock; Confirmation for guarded changes  | Implemented. Avoid suggesting that Confirmation is required for every reversible edit.   |
| Architecture       | Panel ↔ Agent ↔ model provider; Panel ↔ Bridge inside Storefront                 | Show provider as interpretation/advice service; Actions reach Storefront through Bridge. |
| Graduation work    | Reviewed dataset; TF-IDF + Logistic Regression comparison; qualified AWS deployment | Explicitly **planned / in progress**; no completed training or cloud deployment claim.   |

Use an icon, a short heading and two to four keywords per block. Draw the real component relationships rather than inserting the guide's example LangGraph, database or cache layers.

## Stack and evidence

Implemented stack badges: **Python · FastAPI · TypeScript · HTTP/SSE · OpenRouter · GitHub**. Optional model label: **Gemini 2.5 Flash via OpenRouter — local release configuration**, not a statement of AWS model qualification. Planned badges must be separate: **AWS Bedrock · scikit-learn**.

Evidence note, if space allows: **Local MVP tagged; automated and recorded live evidence available**. Avoid squeezing unexplained test totals onto the slide. The five-person informal feedback is not a quantitative satisfaction score; synthetic dataset messages are not participant observations.

Timeline: **16 Oct: planning / review / requirements → 6 Nov: design → 30 Nov: implementation → 4 Dec: final reports / presentation**. These are official deadlines, not completed milestones.

Bottom outcomes: **Local demo + source + documentation** (available); **ML comparison + AWS demo** (planned). Scope footer: **One Controlled Storefront · fictional checkout · AWS delivery pending**.

## Visual direction and export checks

White/light-gray canvas, deep-blue headings, purple/cyan connections and orange for planned work; green only for explicitly completed items. Use a small consistent outline-icon set, aligned roadmap blocks and a separate compact architecture flow. Keep the title and track name readable at presentation size.

Before export, recheck current project status, label every planned result, verify all text fits and inspect the rendered 16:9 image. Produce the single image and an editable slide/source if requested; do not claim this brief itself satisfies the final infographic deliverable.
