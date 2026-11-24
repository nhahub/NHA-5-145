# Shopping Copilot - DEPI graduation project

Digital Egypt Pioneers Initiative (DEPI) | AWS ML Engineering

Official submission repository: [nhahub/NHA-5-145](https://github.com/nhahub/NHA-5-145).

## Source code

The complete application is in [`final/source/`](final/source/): the Agent (Python/FastAPI), Bridge, Panel and Storefront (TypeScript/Node), the evaluation and browser test suites, the AWS deployment code and the design documents. Setup and run instructions are in [final/source/README.md](final/source/README.md).

```sh
git clone https://github.com/nhahub/NHA-5-145.git
cd NHA-5-145/final/source
```

The [final submission](final/README.md) also holds the presentation, the demo video and the infographic.

## Reports

| Document | Deadline | Report |
| --- | --- | --- |
| 01 - Project Planning and Management | 16 October 2026 | [Planning PDF](reports/01-project-planning-and-management.pdf) (9 pages) |
| 02 - Literature Review | 16 October 2026 | [Literature PDF](reports/02-literature-review.pdf) (7 pages) |
| 03 - Requirements Gathering | 16 October 2026 | [Requirements PDF](reports/03-requirements-gathering.pdf) (12 pages) |
| 04 - System Analysis and Design | 6 November 2026 | [Design PDF](milestones/2026-11-06/reports/04-system-analysis-and-design.pdf) (23 pages) |
| Final submission - source code, presentation, demo video, infographic | 23 November 2026 | [Final submission](final/README.md) |

The first three reports and their editable sources and original provenance remain unchanged from the 16 October submission, commit `b8b8f78058028abd2c4df62d5dbd22d1524d0a27`.

## 23 November final submission

- [Final submission index](final/README.md): what is included and what changed since the defense.
- [Presentation (PowerPoint)](final/presentation/Shopping-Copilot-Graduation-Defense-2026-11-24.pptx) and [PDF copy](final/presentation/Shopping-Copilot-Graduation-Defense-2026-11-24.pdf).
- [Demo video](final/video/shopping-copilot-demo-2026-11-23.mp4), recorded on the deployed site with the real model.
- [Infographic](final/infographic/shopping-copilot-infographic.png) ([PDF](final/infographic/shopping-copilot-infographic.pdf)).
- [Source code](final/source/README.md): the complete application, tests, evaluation suite and deployment code.

## 6 November submission

Prepared 28 October; added to this repository on 30 October 2026, on the owner's instruction.

- [Complete downloadable ZIP](packages/shopping-copilot-system-design-2026-11-06.zip).
- [Editable analysis and design](milestones/2026-11-06/sources/system-analysis-design.md) and [companion views](milestones/2026-11-06/sources/system-design-views.md).
- [Twelve editable draw.io diagrams and PNG previews](milestones/2026-11-06/diagrams).
- [Build manifest](milestones/2026-11-06/provenance/export-manifest.json), [visual review](milestones/2026-11-06/provenance/visual-review.json) and [milestone checksums](milestones/2026-11-06/checksums.sha256).
- [Submission/rebuild guide](milestones/2026-11-06/sources/system-design-submission.md).

The design includes all 21 requirement IDs, current per-Shopper state, physical SQLite storage, interfaces, safety/recovery, selected Stockholm AWS topology, native host isolation and ML evaluation evidence. Relative evidence links in the PDF resolve inside the milestone folder; download/extract the ZIP when a browser PDF viewer cannot open them. Markdown sources retain development-repository paths and are intended to be edited from the complete checkout. Evidence snapshots are supplied for review; the milestone folder is not a runnable application checkout.

The milestone README, source statuses and manifest describe preparation as of 28 October. This repository's commit history records the later delivery; it does not establish instructor acceptance. Root `checksums.sha256` covers the current repository files except itself, including both milestones and the ZIP. Original October export provenance is preserved at `provenance/export-manifest.json`.

## Evidence scope

The Controlled Storefront local MVP is complete under its recorded acceptance decisions. The offline ML experiment uses synthetic/exposed training and reused validation data, with zero unseen examples; it is exploratory. Final independent evaluation, fair LLM comparison, native production host acceptance and AWS deployment remain open as recorded in the report. Document delivery does not change those gates or authorize model/cloud spending.

The owner confirms lecturer approval and repository invitation received; no further approval date/wording or grading weights were supplied. Actual contributions remain distinct from administrative assignments.
