# Skills selected for the 6 November design deliverable

Discovery date: 28 October 2026. Requested workflow: `find-skills`. The skills.sh leaderboard was checked first through Agent Reach's Jina web route, followed by three CLI searches: `npx --yes skills find "system architecture documentation"`, `"c4 architecture diagram"` and `"requirements engineering"`. Repository metadata was checked through the GitHub CLI. Counts below are observations on this date, not quality guarantees.

| Candidate                                                 | Reported installs | Source repository stars | Assessment                                                                                          |
| --------------------------------------------------------- | ----------------- | ----------------------- | --------------------------------------------------------------------------------------------------- |
| softaworks/agent-toolkit: c4-architecture                 | 4.2K              | 2,598                   | Selected: distinguish context, execution boundaries and components; keep diagrams focused           |
| onewave-ai/claude-skills: technical-writer                | 1K                | 393                     | Selected: write for reviewers, ground statements in source and make acceptance limitations explicit |
| spillwavesolutions/design-doc-mermaid: design-doc-mermaid | 83.5K             | 179                     | Inspected alternative; broad template/tooling overlaps installed diagram tooling                    |

All three repositories were active/non-archived at inspection. They are third-party sources, not official DEPI or AWS instructions. The selected skill files were read directly; no global skills, plugins or application dependencies were installed. Existing Draw.io and PDF skills supply editable diagram authoring and render/inspect verification. Their output conventions are adapted to the repository's existing document paths and preserve the approved project scope.

## What was applied

- C4: context before execution details, explicit technologies, directional labeled relationships, focused diagrams and a clear distinction between a component and a deployable process. The report includes C4-style views plus the UML/DFD/data/wireframe material required by DEPI.
- Technical writing: infer the audience as DEPI reviewers and a developer defending the implementation; use source-backed facts, explain decisions and distinguish implemented, rehearsed, selected and unaccepted work.
- Draw.io: retain editable XML diagrams with unique cell IDs and valid geometry. Desktop CLI discovery checked PATH, default/per-user paths, registry and other drive defaults; no executable was found. The local exporter therefore renders the authored XML's documented shape subset directly to vector/PDF and PNG. No draw.io Desktop export or full mxGraph renderer compatibility is claimed.
- PDF: preserve text, references, tables and figure labels; render every page, inspect it, check margins and bind source/output hashes in a manifest.

## Sources and optional installation commands

- [C4 Architecture skill](https://skills.sh/softaworks/agent-toolkit/c4-architecture), [source](https://github.com/softaworks/agent-toolkit/blob/main/skills/c4-architecture/SKILL.md). Optional: `npx skills add softaworks/agent-toolkit@c4-architecture -g -y`.
- [Technical Writer skill](https://skills.sh/onewave-ai/claude-skills/technical-writer), [source](https://github.com/OneWave-AI/claude-skills/blob/main/technical-writer/SKILL.md). Optional: `npx skills add onewave-ai/claude-skills@technical-writer -g -y`.
- [Design Doc Mermaid alternative](https://skills.sh/spillwavesolutions/design-doc-mermaid/design-doc-mermaid), [source](https://github.com/SpillwaveSolutions/design-doc-mermaid/blob/main/SKILL.md). Optional: `npx skills add spillwavesolutions/design-doc-mermaid@design-doc-mermaid -g -y`.

Popularity informed discovery; repository/code inspection and suitability determined use. No skill authorizes runtime changes, cloud provisioning, external publication, inference spending or a change to the owner's gates.
