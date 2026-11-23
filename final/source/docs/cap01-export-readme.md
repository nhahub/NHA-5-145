# CAP-01 PDF exports

The three review-ready reports were exported on **6 October 2026** for the **AWS ML Engineering** track and **16 October 2026** DEPI deadline. Editable Markdown remains the source of truth. The source documents retain their 2 October content dates; exporting them does not establish lecturer approval or official submission.

| Report                                                        | Output                                                      | Pages |
| ------------------------------------------------------------- | ----------------------------------------------------------- | ----- |
| Project planning and management                               | [Planning PDF](../output/pdf/cap01-project-planning.pdf)    | 8     |
| Literature review, with pending lecturer record as Appendix A | [Literature PDF](../output/pdf/cap01-literature-review.pdf) | 7     |
| Requirements gathering and traceability                       | [Requirements PDF](../output/pdf/cap01-requirements.pdf)    | 8     |

The exporter preserves the source prose, table cells, bibliography, evidence caveats and assigned-role qualifications. Tables with three or more columns become labeled records. The planning Gantt is a vector chart generated directly from the 12 Mermaid task rows, so rebuilding does not depend on the ignored diagram image. Two-column tables repeat their headers when split across pages. PDFs include page numbers, section bookmarks, clickable links and a printed reference/provenance section.

Relative source links use development commit `85369325942010639ab6a765d8402e443beeff1a`. These are supporting development references, not the required Skills Dynamix submission repository. External literature URLs and their original access date remain unchanged; this export did not repeat the research or fetch remote sources.

## Rebuild

Use Python 3.12 or newer with `reportlab`, `pypdf`, `pdfplumber` and `Pillow`, Git available on `PATH`, and the repository history containing the pinned commit. Use Poppler's `pdftoppm` on `PATH` for the full render check. Exact package versions and font hashes are recorded in [the export manifest](../output/pdf/cap01-export-manifest.json). The Windows build uses the installed Arial font files; fonts are embedded in the PDFs but are not copied into the repository.

From the repository root in PowerShell:

```powershell
python -m pip install reportlab pypdf pdfplumber Pillow
python scripts/export_cap01.py --render --font-dir 'C:/Windows/Fonts'
```

`--font-dir` must contain `arial.ttf`, `arialbd.ttf`, `ariali.ttf` and `arialbi.ttf`. Install Poppler separately if it is unavailable. Omitting `--render` rebuilds the PDFs and runs text/link checks, but does not run the required visual verification. Install document tooling into a separate environment; no application dependency files need to change.

The exporter fixes PDF metadata timestamps using ReportLab invariant mode; the visible export date remains 6 October 2026. With unchanged sources, exporter, dependency versions and fonts, rebuilding produces identical PDF bytes. To prepare a future dated package, change the export date deliberately and review all source statuses first. The historical source dates must not be silently replaced by a new export date.

## Verification and retained evidence

The exporter checks every parsed source paragraph/table cell against extracted PDF text and verifies every unique URL has a link annotation. It also checks word bounds inside the page margins when rendering. These checks complement visual review; they cannot replace it.

Full page PNGs, extracted text and four-page contact sheets are retained under ignored `work/pdfbuild/`. The final pass inspected all **23 pages**, including the vector schedule, bibliography, lecturer appendix, repeating table headers and report endings. No clipping, overlapping text or missing glyphs was found. All 330 source text fragments and 22 report-local unique links passed the automated checks. The literature source contains seven primary bibliography entries and the separate lecturer record remains explicitly pending.

The [manifest](../output/pdf/cap01-export-manifest.json) records source SHA-256 hashes, exporter/font hashes, dependency versions, output hashes, page counts, link/text checks and render locations. Keep it beside the PDFs. Rebuilding refreshes the manifest and replaces only this exporter's page/contact-sheet intermediates.

No application runtime, cloud resource, model budget or remote repository was changed by the export. Official upload, lecturer evidence, actual contribution confirmations and any institution-specific file conventions remain separate completion steps.
