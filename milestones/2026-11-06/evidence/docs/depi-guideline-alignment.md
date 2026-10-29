# DEPI supplied guidelines: submission alignment

Reviewed: **2 October 2026**; design mapping updated **28 October 2026**. Track confirmed by the owner: **AWS ML Engineering**. Applicable schedule: **DEPI**, not DEPI Industry. This register maps the five supplied PDFs to project artifacts; it does not certify submission or instructor approval.

## Source register

The owner supplied these documents locally. Page numbers below are PDF page numbers. The originals remain outside the repository; this register records their requirements without redistributing the source PDFs.

| Ref | Supplied document                                               | Relevant content                                                                                                                                                              |
| --- | --------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| G1  | `Project DocumentationWith Info-Graph.pdf` (14 pages)           | Page 1: deadlines and GitHub delivery. Pages 1–5: report requirements. Page 5: project infographic. Pages 6–14: infographic guide. Use as the consolidated content checklist. |
| G2  | `R5- Project Documentation Last Updates.pdf` (5 pages)          | Same dated DEPI schedule and documentation checklist, without the infographic addition.                                                                                       |
| G3  | `R5- Project Documentation .pdf` (5 pages)                      | Earlier week-based plan; pages 1–2 call section 2 “Lecturer Review”. Retain for interpreting the heading discrepancy, not for replacing the confirmed dates.                  |
| G4  | `R5- Projects_Instructions_Final - For Trainees .pdf` (3 pages) | Pages 1–2: custom-project lecturer approval, team responsibility evidence, organization-owned GitHub delivery and leader invitation. Page 3: final discussion attendance.     |
| G5  | `Info Graphic Template Guide.pdf` (9 pages)                     | Single landscape 16:9 project-summary slide/image; preferred 2560×1440, minimum 1920×1080; DEPI and confirmed track branding; factual architecture and deliverables only.     |

These are content/design guidelines, not an editable report template. They do not specify report font, margins, page count, filename convention or numerical grading weights. Do not infer those details from the infographic's separate design instructions.

## Confirmed submission dates

| Deliverable                             | DEPI deadline    |
| --------------------------------------- | ---------------- |
| Project Planning & Management           | 16 October 2026  |
| Literature Review                       | 16 October 2026  |
| Requirements Gathering                  | 16 October 2026  |
| System Analysis & Design                | 6 November 2026  |
| Implementation: Source Code & Execution | 30 November 2026 |
| Final Presentation, Testing & Reports   | 4 December 2026  |

Source: G1/G2 page 1, consistent with the owner's previously confirmed schedule. The infographic appears under final deliverables; no separate earlier deadline is stated.

## Content mapping and gaps

| Required content                                                            | Project artifact                                                                                                               | Current readiness / remaining work                                                                                                                     |
| --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Proposal, objectives, scope                                                 | [Planning](cap01-project-planning.md), [requirements](cap01-requirements.md)                                                   | Draft content prepared. Custom-project approval evidence remains pending.                                                                              |
| Gantt, milestones, deliverables, resources, roles                           | [Planning](cap01-project-planning.md)                                                                                          | Proposed internal schedule and actual capacity distinguished from official dates and nominal roles.                                                    |
| Risks and KPIs                                                              | [Planning](cap01-project-planning.md)                                                                                          | Risk register and measurement definitions provided; planned measurements are not results.                                                              |
| Literature / lecturer review                                                | [Research review](cap01-literature-review.md), [lecturer record](cap01-lecturer-review.md)                                     | Preserve both pending clarification of the inconsistent heading. No invented feedback or grading weights.                                              |
| Stakeholders, stories, use cases, functional and quality requirements       | [Requirements](cap01-requirements.md), [design use cases](system-analysis-design.md#2-stakeholders-requirements-and-use-cases) | Mapped to acceptance evidence; informal feedback limitations retained.                                                                                 |
| Architecture, data model, DFD, sequence, activity, state and class diagrams | [Design](system-analysis-design.md), [design supplement](system-design-views.md)                                               | Updated: per-Shopper volatile commerce, physical SQLite catalogue/ledger, twelve editable views and all 21 requirement IDs. See the 28 October report. |
| UI wireframes and guidelines                                                | [Design supplement](system-design-views.md)                                                                                    | Schematic wireframes and implemented CSS/interaction references; no new accessibility-certification claim.                                             |
| Deployment/component diagrams, technology stack, APIs                       | [Design](system-analysis-design.md), [supplement](system-design-views.md)                                                      | Selected Stockholm network, cloud dossier and host isolation documented. Native host and actual cloud/model acceptance remain open.                    |
| Source, version control, execution instructions                             | [README](../README.md), [repository](https://github.com/Homd11/shopping-copilot)                                               | Development evidence exists; organization submission URL/invitation remains unprovided.                                                                |
| Test plan, cases, automation, bug resolutions                               | [Results](../RESULTS.md), [design traceability](system-analysis-design.md#11-requirement-to-design-traceability)               | Local historical evidence exists; cloud acceptance remains CAP-07.                                                                                     |
| User manual, final slides, optional video, infographic                      | [Infographic brief](project-infographic-brief.md), CAP-08                                                                      | Brief prepared; final user guide, presentation and infographic exports remain to be produced. Video is optional in G1/G2.                              |

## Submission destination and unresolved inputs

G4 pages 1–2 specifies a repository created under **Skills Dynamix's organization**, with the project leader invited to upload the project. The personal development repository is not evidence of official submission. Obtain the organization repository URL/invitation or explicit instructor clarification; no repository transfer, deletion or remote change is implied by this review.

| Input                                         | Status                                                                                         |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Official track name                           | Owner-confirmed: AWS ML Engineering.                                                           |
| Organization repository and leader access     | Required arrangement identified; actual URL/invitation not supplied.                           |
| Custom proposal approval                      | Positive feedback was reported earlier; formal lecturer approval evidence not supplied.        |
| Literature versus lecturer review             | Heading conflict in G1/G2 versus G3; keep research synthesis and lecturer record separately.   |
| Numerical grading weights                     | Not supplied; the guides ask for criteria but do not provide a breakdown.                      |
| Editable report template / required file type | Not supplied; Markdown drafts remain editable sources until export requirements are confirmed. |
| Individual contribution evidence              | Record actual work only. Administrative assignments do not establish authorship.               |

## Readiness checklist

- [x] Export three CAP-01 PDFs with editable Markdown sources and a validated one-slide infographic; see [exports](cap01-export-readme.md) and [infographic](../output/infographic/README.md). Exported 6 October; official acceptance and final submission remain pending.
- [x] Record supplied requirements and confirmed DEPI deadlines.
- [x] Align planning, research review and requirements drafts to the checklist.
- [x] Supply additional local-system design views and infographic content brief.
- [ ] Obtain or record lecturer feedback, custom-project approval and grading guidance.
- [ ] Obtain access to the organization submission repository.
- [ ] Confirm final report/export conventions and complete owner content review.
- [ ] Resolve CAP-04 cloud design decisions before finalizing the 6 November design package.
- [ ] Produce the full final presentation and user manual; refresh infographic status labels before final submission.
- [ ] Upload permitted project artifacts and record the official submission commit/link.
- [ ] Confirm final-discussion date, time and joining arrangements; attend the required discussion. G4 page 3 states that absence counts as not submitting the graduation project. The exact appointment is not established by the 4 December document deadline.

Content preparation does not close CAP-01's external review/submission work, CAP-02's dataset release, or any cloud gate.

## 28 October design revision

The [6 November submission guide](system-design-submission.md) identifies the updated PDF, editable diagrams, evidence manifest and portable package. This updates the design deliverable; historical October submission/approval notes above retain their original date and are not new claims about missing invitations. The owner supplied the official repository and authorized the earlier October push in this conversation. No new November upload or instructor acceptance is claimed. Numerical grading weights and actual contribution evidence remain separate inputs.
