# 6 November: System Analysis and Design submission

Prepared 28 October 2026 for the DEPI AWS ML Engineering track. This is Document 04, revision 2. The first three October reports remain historical submissions.

## Review package

- Main report: `output/pdf/system-analysis-design-2026-10-28.pdf`.
- Portable package: `output/submission/shopping-copilot-system-design-2026-11-06.zip`.
- Editable analysis: `docs/system-analysis-design.md` and `docs/system-design-views.md`.
- Editable diagrams and previews: `docs/diagrams/system-design-20261028/`.
- Skill discovery and applied methodology: `docs/system-design-skills.md`.

The report contains twelve figures covering context, execution boundaries, data flow, physical data stores, Action sequence, Confirmation activity, task states, host lifecycle, module relationships, selected deployment, host isolation and UI wireframes. Its matrix maps all 21 original requirement identifiers to the current design and acceptance status.

The ZIP preserves the PDF, Markdown sources, native draw.io XML, PNG previews, referenced evidence snapshots, exporter snapshot, build manifest and SHA-256 checksums. PDF evidence links are relative to the package's `reports/` directory. The editable Markdown keeps repository-relative links and is intended for the full checkout.

## Rebuild and verify

Run `scripts/export_system_design.py` from a Python environment containing ReportLab, pypdf, pdfplumber and Pillow, with Poppler's `pdftoppm` on PATH. This workstation uses the Codex bundled document runtime; document tooling is separate from the application dependencies. The exporter currently uses Arial from `C:/Windows/Fonts`; use equivalent registered fonts before porting it to another host.

The exporter validates diagram geometry, source-fragment preservation, PDF link annotations and text bounds. It renders all report pages to `work/system-design-20261028/pages/`, plus contact sheets. The manifest records source/output/font/dependency hashes and counts. It is build evidence, not a substitute for visual review.

The diagram sources use a restricted documented XML subset. No draw.io Desktop executable was found; the exporter renders that authored subset directly as PDF vectors and PNG previews. Review native sources in draw.io when making further edits and rebuild both report and previews. Full mxGraph layout equivalence is not claimed.

## Submission boundary

Before uploading, review the final PDF, check the lecturer's requested channel/naming and confirm the team's administrative details if separately required. Package preparation does not establish an upload receipt.

The report distinguishes implemented software, disposable Linux rehearsal, selected deployment design and remaining acceptance work. Native production runtime/systemd acceptance, cloud resource/cost/rollback gates and model qualification remain governed by the newest checkpoint. The approved OpenRouter fallback retains its existing non-resetting $2 cap. No model call, AWS operation, credential transfer or public activation is needed to regenerate these documents.
