# CAP-01: graduation deliverables and ownership

Updated: 2026-10-06. Track: **AWS ML Engineering** (owner-confirmed). State: drafts aligned to supplied DEPI guidelines and [three PDFs exported](cap01-export-readme.md); [editable infographic and image](../output/infographic/README.md) prepared. Lecturer evidence and organization-repository access remain pending. No submission, external message or cloud provisioning has occurred. See the [submission register](depi-guideline-alignment.md).

## Working arrangement clarified — 2 October 2026

The owner clarified that the owner is the only active contributor. The other named members are not available to perform project work. Earlier technical/academic allocations below record the supplied team table and prior assignments; they are not evidence of contributions or active staffing. The owner coordinates all actual deliverables. Do not request help from those members, invent contribution records or make progress depend on their review. Any independent-human-review claim remains unsupported unless real evidence is later obtained.

The session refactor is complete. The owner subsequently approved a limited synthetic-pilot exception on 6 October: 140 messages are mapped to draft annotations, with 103 eligible cases frozen as 82 training / 21 validation / zero unseen. [The offline pilot](cap03-pilot-results.md) is complete; CAP-02 final release and CAP-03 final comparison remain open. These draft-labelled, exposed synthetic examples are not independent gold. A [CAP-04 design recommendation](cap04-aws-design-draft.md) is prepared for later decisions; nothing has been provisioned.

## Goal and boundaries

Turn the approved Controlled Storefront AWS graduation scope into a concrete responsibility, deadline and evidence register. CAP-01 is planning and traceability, not model training or a new application feature. CAP-02 collects/reviews/releases the multilingual dataset; CAP-03 trains the offline TF-IDF + Logistic Regression baseline and compares intent classification with the LLM using the same eligible inputs. Runtime shopping decisions remain with the LLM and deterministic action guards.

## Evidence available

| Deliverable                        | Current evidence                                                                            | Work needed for submission                                                                       |
| ---------------------------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Problem, requirements and scope    | `CONTEXT.md`, local specification, README and MVP results                                   | Align wording with the actual rubric and accepted proposal.                                      |
| User motivation and evaluation     | Informal Ticket 16 findings and explicit scope adjustment                                   | Present qualitative observations and limitations; do not claim a formal study.                   |
| Technical implementation and tests | Versioned application, regression suites, frozen Ticket 15 live reports, final advice check | Pin release/configuration references and explain historical versus current evidence.             |
| ML methodology                     | Prepared dataset/baseline protocols; existing exposed development cases                     | CAP-02 reviewed release, then CAP-03 training/comparison and error analysis.                     |
| Architecture and cloud delivery    | Current local boundaries; approved Controlled Storefront direction                          | CAP-04 reviewed architecture/budget, CAP-05 qualification, CAP-06 deployment, CAP-07 acceptance. |
| Literature review                  | Seven-source synthesis and separate lecturer-review record                                  | Owner review; clarify heading discrepancy and obtain lecturer evidence.                          |
| Individual contributions           | Git history and task evidence                                                               | Map real agreed owners to work and maintain weekly records.                                      |
| Presentation and demonstration     | Working local application                                                                   | CAP-08 submission, AWS demo, limitations and member explanations.                                |

## Team responsibilities supplied by the owner

The owner supplied the team allocation table on 2026-10-01. Names and responsibilities reflect that table; contact addresses are excluded from the public repository. Assigned responsibilities are not claims that future deliverables are already complete.

| Member        | Assigned role                        | Responsibilities and deliverables                                                                                |
| ------------- | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| Ahmed Yasser  | AI Agent & LLM Architecture          | Provider-neutral LLM client, prompt engineering, Structured Intent schema and deterministic safety boundaries.   |
| Ali Amr       | AWS Cloud Architect & Infrastructure | Bedrock Runtime integration using Converse API, hosting architecture, budget monitoring and deployment security. |
| Mohamed Hamdi | Backend & Agent Orchestration        | FastAPI session management, Server-Sent Events, action-planning lifecycle and recovery-state reconciliation.     |
| Ezz Mohamed   | Frontend & Storefront Integration    | TypeScript Bridge and Panel, cross-origin communication, responsive UI and RTL localization.                     |
| Rana Ali      | QA, Safety & Evaluation Runner       | Playwright suites, multilingual intent benchmarking and safety-invariant validation reports.                     |

The project owner coordinates the overall submission. On 2026-10-02, the owner explicitly confirmed the academic leads below; these supersede the earlier request to leave those three assignments pending. They assign responsibility for preparing and coordinating review, not credit for work already performed. Weekly evidence must identify actual contributions.

| Deliverable due 16 October    | Confirmed academic lead |
| ----------------------------- | ----------------------- |
| Project Planning & Management | Mohamed Hamdi           |
| Literature Review             | Ahmed Yasser            |
| Requirements Gathering        | Rana Ali                |

CAP-02 unseen-data custody, independent annotation review and CAP-03 classical-model training ownership remain pending. These responsibilities are not inferred from the academic lead assignments. Ali Amr and Ezz Mohamed retain their supplied technical roles.

## Confirmed DEPI schedule

The owner supplied the Project Documentation Guidelines screenshot and explicitly selected **DEPI**, not DEPI Industry, on 2026-10-01. These are the applicable dates; the Industry column is not this team's schedule.

| Deliverable                              | Confirmed deadline |
| ---------------------------------------- | ------------------ |
| Project Planning & Management            | 16 October 2026    |
| Literature Review                        | 16 October 2026    |
| Requirements Gathering                   | 16 October 2026    |
| System Analysis & Design                 | 6 November 2026    |
| Implementation (Source Code & Execution) | 30 November 2026   |
| Final Presentation, Testing & Reports    | 4 December 2026    |

The immediate target is the three documents due **16 October**. Use completed local evidence and describe unreleased dataset/model/cloud work accurately. The five supplied PDFs confirm the documentation checklist and organization GitHub delivery, but provide no numerical grading weights or editable report template.

## Remaining planning inputs

| Input                                                      | Current state                                                                            | Next action                                                                              |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Applicable schedule                                        | Confirmed: DEPI, dates above                                                             | Use these dates in the deliverable register.                                             |
| Team members and agreed responsibilities                   | Five technical roles and three academic leads confirmed                                  | Resolve dataset custody, independent annotation review and classical-training ownership. |
| First submission deadline, format and location             | 16 October; content guidelines supplied; Skills Dynamix organization repository required | Obtain actual invitation/URL and any export conventions.                                 |
| Official assessment weights and custom-proposal acceptance | Not independently verified                                                               | Record authoritative evidence or mark pending.                                           |
| AWS-specific training/tooling requirements                 | AWS track stated by owner; detailed requirements unconfirmed                             | Clarify mandatory versus optional deliverables.                                          |
| Cloud budget/credits and region                            | Not authorized for provisioning                                                          | Establish a separate budget before CAP-04/06 spending.                                   |

The owner supplied both the team allocation and the schedule, then explicitly selected DEPI. This record supersedes older local notes that described team roles or the schedule as unconfirmed. No contact addresses, guessed dates or claims of instructor approval are added.

## Draft package for 16 October

The owner coordinates submission; nominal leads are not available staffing. The [alignment register](depi-guideline-alignment.md) maps supplied guidelines. Organization-repository access remains pending. These editable drafts are prepared for owner review; none is submitted or instructor-approved:

| Deliverable                   | Review draft                                                                               | Remaining readiness work                                            |
| ----------------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------- |
| Project Planning & Management | [Planning draft](cap01-project-planning.md)                                                | Owner reviews proposed Gantt, resources, risks and KPI definitions. |
| Literature Review             | [Research review](cap01-literature-review.md), [lecturer record](cap01-lecturer-review.md) | Preserve research; obtain feedback and clarify heading.             |
| Requirements Gathering        | [Requirements and traceability](cap01-requirements.md)                                     | Owner reviews stakeholder, story, use-case and acceptance mapping.  |

These are the current drafts. The earlier `depi-milestone-1.md` preparation note is historical and contains superseded schedule, team and Ticket 16 wording; use this register and the new drafts instead. No dataset collection, model training, paid model call, cloud provisioning or external submission occurs in this drafting step.

## System Analysis & Design - 6 November (updated 28 October)

The owner requested a refresh against the substantially implemented project. The [current report](system-analysis-design.md) and [companion](system-design-views.md) replace the 2 October shared-cart/fixture assumptions with per-Shopper commerce, durable SQLite catalogue/allowance, current interfaces, recovery, selected Stockholm networking and native host isolation.

The report includes twelve editable views, selected real classes/members and a matrix covering all 21 requirement IDs.. The [submission guide](system-design-submission.md) identifies the PDF, sources, diagrams, evidence manifest and portable ZIP.

This is prepared documentation for technical review. Native host/runtime/systemd acceptance, actual AWS/model/account/cost/rollback acceptance and the official November upload remain separate. No cloud/model action or new publication is performed by this revision. The historical readiness notes below describe earlier submissions; use the 28 October design sources and newest checkpoint for current architecture.

## Remaining finalization work

1. Owner reviews aligned drafts, proposed internal dates and evidence references.
2. Record lecturer approval/feedback and rubric details when supplied; resolve the review-heading ambiguity.
3. Obtain the organization repository invitation and confirm final file/export conventions.
4. Maintain contribution rows from actual artifacts without assigning past work to nominal members.
5. Review the [three exported PDFs](cap01-export-readme.md) and [editable infographic plus PNG](../output/infographic/README.md), then upload agreed documents and record the official submission commit. Exports are prepared; official submission remains pending.

CAP-01 content alignment is prepared; owner/instructor review and official submission remain pending.

## Readiness update — 7 October 2026

The existing PDF exports preserve the 2 October source snapshots and are not a current experiment report. Before final submission, carry forward the [seven-family comparison](cap03-model-comparison-results.md) and [executed notebook](../notebooks/cap03-model-comparison.ipynb): 210 training / 53 validation / zero unseen examples, all synthetic and exposed, with the best selected validation result 23/53 correct (43.40%). This is exploratory evidence, not a completed independent evaluation or final LLM comparison. CAP-02/03 final gates remain open. The three source documents and their exported PDF hashes are unchanged by this register update.

AWS planning now records the owner's [credit-only, public-link constraints](cap04-credit-only-plan.md); a personal Free-plan account now exists ($100 shown, plan ending 7 April 2027), but no deployment is approved. Update the editable submission sources and regenerate their exports together after owner review of the final package, preserving the distinction between completed local work, exploratory experiments and planned AWS work. The supplied guidelines, 16 October deadline, missing organization-repository invitation and pending lecturer record remain unchanged. Nominal academic assignments do not claim work by absent teammates.
