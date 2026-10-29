# Shopping Copilot - DEPI graduation documentation

Digital Egypt Pioneers Initiative (DEPI) | AWS ML Engineering

Official submission repository: [nhahub/NHA-5-145](https://github.com/nhahub/NHA-5-145).

## Reports

| Document | Deadline | Report |
| --- | --- | --- |
| 01 - Project Planning and Management | 16 October 2026 | [Planning PDF](reports/01-project-planning-and-management.pdf) (9 pages) |
| 02 - Literature Review | 16 October 2026 | [Literature PDF](reports/02-literature-review.pdf) (7 pages) |
| 03 - Requirements Gathering | 16 October 2026 | [Requirements PDF](reports/03-requirements-gathering.pdf) (12 pages) |
| 04 - System Analysis and Design | 6 November 2026 | [Design PDF](milestones/2026-11-06/reports/04-system-analysis-and-design.pdf) (23 pages) |

The first three reports and their editable sources and original provenance remain unchanged from the 16 October submission, commit `f4e8d3ddb27049702eaf0346c1578f6e036424af`.

## 6 November submission

Prepared 28 October; added to this repository on 30 October 2026, on the owner's instruction.

- [Complete downloadable ZIP](packages/shopping-copilot-system-design-2026-11-06.zip).
- [Editable analysis and design](milestones/2026-11-06/sources/system-analysis-design.md) and [companion views](milestones/2026-11-06/sources/system-design-views.md).
- [Twelve editable draw.io diagrams and PNG previews](milestones/2026-11-06/diagrams).
- [Build manifest](milestones/2026-11-06/provenance/export-manifest.json), [visual review](milestones/2026-11-06/provenance/visual-review.json) and [milestone checksums](milestones/2026-11-06/checksums.sha256).
- [Submission/rebuild guide](milestones/2026-11-06/sources/system-design-submission.md) and [skill discovery record](milestones/2026-11-06/sources/system-design-skills.md).

The design includes all 21 requirement IDs, current per-Shopper state, physical SQLite storage, interfaces, safety/recovery, selected Stockholm AWS topology, native host isolation and ML evaluation evidence. Relative evidence links in the PDF resolve inside the milestone folder; download/extract the ZIP when a browser PDF viewer cannot open them. Markdown sources retain development-repository paths and are intended to be edited from the complete checkout. Evidence snapshots are supplied for review; the milestone folder is not a runnable application checkout.

The milestone README, source statuses and manifest describe preparation as of 28 October. This repository's commit history records the later delivery; it does not establish instructor acceptance. Root `checksums.sha256` covers the current repository files except itself, including both milestones and the ZIP. Original October export provenance is preserved at `provenance/export-manifest.json`.

## Evidence scope

The Controlled Storefront local MVP is complete under its recorded acceptance decisions. The offline ML experiment uses synthetic/exposed training and reused validation data, with zero unseen examples; it is exploratory. Final independent evaluation, fair LLM comparison, native production host acceptance and AWS deployment remain open as recorded in the report. Document delivery does not change those gates or authorize model/cloud spending.

The owner confirms lecturer approval and repository invitation received; no further approval date/wording or grading weights were supplied. Actual contributions remain distinct from administrative assignments.
