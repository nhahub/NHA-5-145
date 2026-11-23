"""Reproducible CAP-01 PDF exports from the canonical Markdown documents.

Standalone document tooling; no application runtime dependencies are changed.
See docs/cap01-export-readme.md for dependencies and verification instructions.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import importlib.metadata
import json
import re
import subprocess
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

import pdfplumber
from PIL import Image as PILImage
from PIL import ImageDraw
from pypdf import PdfReader
from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output/pdf"
WORK = ROOT / "work/pdfbuild"
EXPORT_DATE = "6 October 2026"
REVISION = "8536932"
REPOSITORY = "https://github.com/Homd11/shopping-copilot"
WIDTH, HEIGHT = A4
MARGIN = 48
CONTENT_WIDTH = WIDTH - MARGIN * 2
NAVY = colors.HexColor("#15334B")
TEAL = colors.HexColor("#087E8B")
INK = colors.HexColor("#24323D")
MUTED = colors.HexColor("#52616D")
PALE = colors.HexColor("#EFF5F7")
LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
SPECS = [
    (
        "cap01-project-planning",
        "Project Planning\nand Management",
        "01",
        ["docs/cap01-project-planning.md"],
    ),
    (
        "cap01-literature-review",
        "Literature Review",
        "02",
        ["docs/cap01-literature-review.md", "docs/cap01-lecturer-review.md"],
    ),
    (
        "cap01-requirements",
        "Requirements Gathering\nand Traceability",
        "03",
        ["docs/cap01-requirements.md"],
    ),
]


def normalize(value: str) -> str:
    return value.translate(
        str.maketrans(
            {
                "—": "-",
                "–": "-",
                "‑": "-",
                "−": "-",
                "“": '"',
                "”": '"',
                "‘": "'",
                "’": "'",
                "\u00a0": " ",
            }
        )
    )


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def styles() -> dict[str, ParagraphStyle]:
    base = dict(
        fontName="Report", fontSize=10.3, leading=15, textColor=INK, spaceAfter=8, alignment=TA_LEFT
    )
    result = {"body": ParagraphStyle("body", **base)}
    for name, updates in {
        "h1": dict(
            fontName="ReportBold",
            fontSize=21,
            leading=26,
            textColor=NAVY,
            spaceBefore=7,
            spaceAfter=15,
            keepWithNext=True,
        ),
        "h2": dict(
            fontName="ReportBold",
            fontSize=15,
            leading=20,
            textColor=NAVY,
            spaceBefore=17,
            spaceAfter=9,
            keepWithNext=True,
        ),
        "h3": dict(
            fontName="ReportBold",
            fontSize=11.5,
            leading=16,
            textColor=TEAL,
            spaceBefore=12,
            spaceAfter=7,
            keepWithNext=True,
        ),
        "small": dict(fontSize=8.6, leading=12, textColor=MUTED, spaceAfter=6),
        "record": dict(fontSize=10, leading=14, spaceAfter=5),
        "record_title": dict(
            fontName="ReportBold",
            fontSize=10.8,
            leading=15,
            textColor=TEAL,
            spaceBefore=3,
            spaceAfter=6,
            keepWithNext=True,
        ),
        "list": dict(leftIndent=17, firstLineIndent=-17),
        "url": dict(fontSize=8, leading=11, textColor=MUTED, splitLongWords=True, spaceAfter=7),
        "link_title": dict(
            fontName="ReportBold",
            fontSize=9,
            leading=12,
            textColor=TEAL,
            spaceBefore=2,
            spaceAfter=3,
            keepWithNext=True,
        ),
    }.items():
        result[name] = ParagraphStyle(name, parent=result["body"], **updates)
    return result


class Gantt(Flowable):
    """Draw vector schedule directly from the preserved Mermaid task rows."""

    def __init__(self, code: str):
        super().__init__()
        self.width = CONTENT_WIDTH
        self.tasks = []
        section = ""
        for raw in code.splitlines():
            line = raw.strip()
            if line.startswith("section "):
                section = line[8:]
            match = re.match(r"(.+?)\s*:\s*(\w+),\s*(\d{4}-\d{2}-\d{2}),\s*(\d+)d", line)
            if match:
                label, identifier, start, days = match.groups()
                self.tasks.append(
                    (
                        section,
                        normalize(label.strip()),
                        identifier == "milestone",
                        date.fromisoformat(start),
                        int(days),
                    )
                )
        if len(self.tasks) != 12:
            raise ValueError(
                "Expected 12 Mermaid schedule entries; review the exporter for changed syntax"
            )
        self.height = 430

    def draw(self):
        c = self.canv
        start = min(t[3] for t in self.tasks)
        end = max(t[3] + timedelta(days=t[4]) for t in self.tasks)
        left, right, top = 244, self.width - 5, self.height - 36
        span = (end - start).days

        def x(day):
            return left + (day - start).days / span * (right - left)

        c.setFont("ReportBold", 9)
        c.setFillColor(NAVY)
        c.drawString(0, self.height - 13, "Proposed graduation work windows")
        c.setFont("Report", 8)
        c.setFillColor(MUTED)
        c.drawString(0, self.height - 27, "Planning estimates; official deadlines are diamonds")
        for i, tick in enumerate(
            [start, date(2026, 10, 16), date(2026, 11, 6), date(2026, 11, 30), end]
        ):
            xx = x(tick)
            c.setStrokeColor(colors.HexColor("#CFDCE1"))
            c.line(xx, 24, xx, top - 20)
            c.setFont("Report", 7.1)
            label = tick.strftime("%d %b")
            if i == 0:
                c.drawString(xx, top - 10, label)
            elif i == 4:
                c.drawRightString(xx, 10, label)
            else:
                c.drawCentredString(xx, top - 10, label)
        y = top - 35
        last_section = None
        for section, label, milestone, begins, days in self.tasks:
            if section != last_section:
                c.setFillColor(NAVY)
                c.setFont("ReportBold", 8.7)
                c.drawString(0, y, section)
                y -= 21
                last_section = section
            c.setFillColor(INK)
            c.setFont("Report", 8.2)
            c.drawString(0, y, label)
            c.setFillColor(MUTED)
            c.setFont("Report", 7.2)
            date_label = begins.strftime("%d %b")
            if not milestone:
                date_label += " - " + (begins + timedelta(days=days)).strftime("%d %b")
            c.drawRightString(left - 8, y - 10, date_label)
            c.setFillColor(TEAL if not milestone else NAVY)
            xx = x(begins)
            if milestone:
                p = c.beginPath()
                p.moveTo(xx, y + 6)
                p.lineTo(xx + 4, y + 2)
                p.lineTo(xx, y - 2)
                p.lineTo(xx - 4, y + 2)
                p.close()
                c.drawPath(p, fill=1, stroke=0)
            else:
                c.roundRect(
                    xx, y - 2, x(begins + timedelta(days=days)) - xx, 8, 2, fill=1, stroke=0
                )
            y -= 23


class ReportDoc(BaseDocTemplate):
    def __init__(self, filename: Path, title: str, total_pages: int | None = None):
        super().__init__(
            str(filename),
            pagesize=A4,
            leftMargin=MARGIN,
            rightMargin=MARGIN,
            topMargin=54,
            bottomMargin=49,
            title=f"Shopping Copilot - {title}",
            author="Shopping Copilot project",
            subject=(
                "DEPI AWS ML Engineering | CAP-01 | Review-ready export; "
                "official submission pending"
            ),
            pageCompression=1,
        )
        self.short_title = title.replace("\n", " ")
        self.total_pages = total_pages
        self.addPageTemplates(
            PageTemplate(
                id="report",
                frames=Frame(
                    MARGIN,
                    49,
                    CONTENT_WIDTH,
                    HEIGHT - 103,
                    leftPadding=0,
                    rightPadding=0,
                    topPadding=0,
                    bottomPadding=0,
                ),
                onPage=self.decorate,
            )
        )

    def decorate(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D5E2E8"))
        canvas.setLineWidth(0.6)
        canvas.line(MARGIN, HEIGHT - 37, WIDTH - MARGIN, HEIGHT - 37)
        canvas.line(MARGIN, 37, WIDTH - MARGIN, 37)
        canvas.setFont("Report", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, HEIGHT - 27, "SHOPPING COPILOT  /  DEPI")
        canvas.drawRightString(WIDTH - MARGIN, HEIGHT - 27, "AWS ML Engineering")
        canvas.drawString(MARGIN, 24, "Review-ready export | 6 October 2026")
        total = f" of {self.total_pages}" if self.total_pages else ""
        canvas.drawRightString(WIDTH - MARGIN, 24, f"Page {doc.page}{total}")
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in ("h1", "h2"):
            title = flowable.getPlainText()
            key = "section-" + hashlib.sha256(f"{self.page}-{title}".encode()).hexdigest()[:16]
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(title, key, 0)


class Builder:
    def __init__(self, source_names: list[str], title: str, number: str):
        self.sources = source_names
        self.title = title
        self.number = number
        self.style = styles()
        self.links: dict[str, str] = {}
        self.fragments: list[str] = []
        self.revision = subprocess.check_output(
            ["git", "rev-parse", REVISION], cwd=ROOT, text=True
        ).strip()

    def resolve(self, target: str, source: str) -> str:
        if target.startswith(("https://", "http://")):
            return target
        path, sep, anchor = target.partition("#")
        resolved = (ROOT / source).parent.joinpath(path).resolve().relative_to(ROOT).as_posix()
        return f"{REPOSITORY}/blob/{self.revision}/{quote(resolved, safe='/')}" + (
            f"#{anchor}" if sep else ""
        )

    def inline(self, text: str, source: str) -> str:
        value = html.escape(normalize(text))

        def link(match):
            label, target = html.unescape(match[1]), html.unescape(match[2])
            url = self.resolve(target, source)
            self.links.setdefault(url, label)
            return (
                f'<a href="{html.escape(url, quote=True)}" color="#087E8B">{html.escape(label)}</a>'
            )

        value = LINK_PATTERN.sub(link, value)
        value = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)
        value = re.sub(r"`([^`]+)`", r'<font name="ReportBold">\1</font>', value)
        return value

    def paragraph(self, text: str, source: str, style="body"):
        plain = LINK_PATTERN.sub(r"\1", normalize(text)).replace("**", "").replace("`", "")
        self.fragments.append(plain)
        return Paragraph(self.inline(text, source), self.style[style])

    def table(self, lines: list[str], source: str):
        rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
        headers, data = rows[0], rows[2:]
        if len(headers) == 2:
            cells = [
                [self.paragraph(cell, source, "record") for cell in row] for row in [headers] + data
            ]
            table = Table(
                cells,
                colWidths=[CONTENT_WIDTH * 0.35, CONTENT_WIDTH * 0.65],
                hAlign="LEFT",
                repeatRows=1,
            )
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), PALE),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 9),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#D5E2E8")),
                    ]
                )
            )
            return [table, Spacer(1, 10)]
        result = []
        for row in data:
            if len(row) != len(headers):
                raise ValueError(f"Malformed table in {source}")
            record = [self.paragraph(f"{headers[0]}: {row[0]}", source, "record_title")]
            for label, content in zip(headers[1:], row[1:], strict=True):
                record.append(self.paragraph(f"**{label}:** {content}", source, "record"))
            record.append(Spacer(1, 8))
            result.append(KeepTogether(record))
        return result

    def markdown(self, source: str, appendix=False):
        lines = (ROOT / source).read_text(encoding="utf-8-sig").splitlines()
        result = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            if line.startswith("```mermaid"):
                i += 1
                code = []
                while i < len(lines) and not lines[i].startswith("```"):
                    code.append(lines[i])
                    i += 1
                result.append(
                    KeepTogether(
                        [
                            Gantt("\n".join(code)),
                            Paragraph(
                                "Figure 1. Proposed work windows from the planning source. "
                                "End dates are derived from the stated duration; "
                                "gates remain binding if windows slip.",
                                self.style["small"],
                            ),
                        ]
                    )
                )
            elif line.startswith("|"):
                table = []
                while i < len(lines) and lines[i].strip().startswith("|"):
                    table.append(lines[i])
                    i += 1
                result.extend(self.table(table, source))
                continue
            elif line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                heading = line[level:].strip()
                if heading == "Bibliography":
                    result.append(PageBreak())
                if appendix and level == 1:
                    heading = "Appendix A. " + heading
                result.append(self.paragraph(heading, source, "h" + str(min(level, 3))))
            elif re.match(r"\d+\. |[-*] ", line):
                result.append(self.paragraph(line, source, "list"))
            else:
                para = [line]
                while (
                    i + 1 < len(lines)
                    and lines[i + 1].strip()
                    and not re.match(r"[#|`]|\d+\. |[-*] ", lines[i + 1].strip())
                ):
                    i += 1
                    para.append(lines[i].strip())
                result.append(self.paragraph(" ".join(para), source))
            i += 1
        return result

    def story(self):
        self.fragments = []
        self.links = {}
        title_style = ParagraphStyle(
            "cover", parent=self.style["h1"], fontSize=32, leading=39, spaceAfter=26
        )
        story = [
            Spacer(1, 64),
            Paragraph(f"CAP-01 / DOCUMENT {self.number}", self.style["h3"]),
            Spacer(1, 18),
            Paragraph(self.title.replace("\n", "<br/>"), title_style),
            Paragraph("Shopping Copilot", self.style["h2"]),
            Paragraph(
                "Arabic-first shopping advice and guarded Storefront actions", self.style["body"]
            ),
            Spacer(1, 27),
        ]
        cover_rows = [
            ["Programme", "Digital Egypt Pioneers Initiative (DEPI)"],
            ["Track", "AWS ML Engineering"],
            ["Submission deadline", "16 October 2026"],
            ["Export date", EXPORT_DATE],
            ["Source document date", "2 October 2026"],
            ["Release status", "Review-ready export; official submission pending"],
        ]
        table = Table(
            [
                [Paragraph(a, self.style["small"]), Paragraph(b, self.style["body"])]
                for a, b in cover_rows
            ],
            colWidths=[145, CONTENT_WIDTH - 145],
        )
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 0), (-1, -1), PALE),
                    ("LEFTPADDING", (0, 0), (-1, -1), 13),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story += [
            table,
            Spacer(1, 25),
            Paragraph(
                "Prepared from the editable project documents. Lecturer approval evidence, "
                "official organization-repository access and grading details remain pending. "
                "Nominal responsibilities are not evidence of individual contributions.",
                self.style["small"],
            ),
        ]
        if len(self.sources) > 1:
            story.append(
                Paragraph(
                    "Includes the separate pending lecturer review and approval record "
                    "as Appendix A.",
                    self.style["small"],
                )
            )
        story.append(PageBreak())
        for index, source in enumerate(self.sources):
            if index:
                story.append(PageBreak())
            story.extend(self.markdown(source, appendix=index > 0))
        story += [
            PageBreak() if len(self.sources) > 1 else Spacer(1, 17),
            Paragraph("Export references and provenance", self.style["h1"]),
            Paragraph(
                f"Source content dates are preserved. This PDF was exported on {EXPORT_DATE}; "
                "it is not an approval or official-upload record. Repository links below use "
                f"the fixed development snapshot {self.revision}. They identify supporting "
                "evidence, not the official submission destination. External bibliography "
                "URLs are preserved as supplied and were not re-verified during export.",
                self.style["small"],
            ),
        ]
        for name in self.sources:
            story.append(
                Paragraph(
                    f"<b>Editable source:</b> {html.escape(name)}<br/>"
                    f"<b>SHA-256:</b> {digest(ROOT / name)}",
                    self.style["url"],
                )
            )
        story.append(Paragraph("Linked sources", self.style["h2"]))
        for index, (url, label) in enumerate(self.links.items(), 1):
            story.append(
                KeepTogether(
                    [
                        Paragraph(f"{index}. {html.escape(label)}", self.style["link_title"]),
                        Paragraph(
                            f'<a href="{html.escape(url, quote=True)}">{html.escape(url)}</a>',
                            self.style["url"],
                        ),
                    ]
                )
            )
        return story


def compact(text: str) -> str:
    return re.sub(r"\s+", "", normalize(text))


def verify(path: Path, builder: Builder) -> dict:
    reader = PdfReader(path)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    normalized = compact(text)
    missing = [part for part in builder.fragments if compact(part) not in normalized]
    if missing:
        raise AssertionError(f"Source text omitted in {path.name}: {missing}")
    if any(page.mediabox.width != reader.pages[0].mediabox.width for page in reader.pages):
        raise AssertionError("Inconsistent page sizes")
    links = [
        obj.get_object().get("/A", {}).get("/URI")
        for page in reader.pages
        for obj in page.get("/Annots", [])
    ]
    absent_links = set(builder.links) - set(links)
    if absent_links:
        raise AssertionError(f"Missing hyperlink annotations: {absent_links}")
    (WORK / f"{path.stem}.txt").write_text(text, encoding="utf-8")
    return {
        "page_count": len(reader.pages),
        "source_text_fragments_verified": len(builder.fragments),
        "unique_links_verified": len(builder.links),
        "page_size": "A4 portrait",
        "text_preservation": "passed",
        "hyperlinks": "passed",
    }


def render(path: Path) -> dict:
    target = WORK / path.stem
    target.mkdir(parents=True, exist_ok=True)
    if target.resolve().parent != WORK.resolve():
        raise ValueError("Rendering target must be a direct child of work/pdfbuild")
    for pattern in ("page-*.png", "contact-*.jpg"):
        for old_file in target.glob(pattern):
            old_file.unlink()
    subprocess.run(
        ["pdftoppm", "-r", "110", "-png", str(path), str(target / "page")],
        check=True,
        capture_output=True,
    )
    pages = sorted(target.glob("page-*.png"))
    with pdfplumber.open(path) as pdf:
        words = [word for page in pdf.pages for word in page.extract_words()]
    for word in words:
        x_min, y_min, x_max, y_max = [word[a] for a in ("x0", "top", "x1", "bottom")]
        if not (
            MARGIN - 1 <= x_min <= x_max <= WIDTH - MARGIN + 1
            and 15 <= y_min <= y_max <= HEIGHT - 15
        ):
            raise AssertionError(f"Out-of-bounds text in {path.name}: {word['text']}")
    sheets = []
    for group in range(0, len(pages), 4):
        sheet = PILImage.new("RGB", (1120, 1650), "#dce5e9")
        draw = ImageDraw.Draw(sheet)
        for local, page in enumerate(pages[group : group + 4]):
            im = PILImage.open(page).convert("RGB")
            im.thumbnail((535, 777))
            x, y = 15 + (local % 2) * 555, 34 + (local // 2) * 820
            sheet.paste(im, (x, y))
            draw.text((x, y - 20), f"{path.stem} / page {group + local + 1}", fill="#15334B")
        name = target / f"contact-{group // 4 + 1}.jpg"
        sheet.save(name, quality=90)
        sheets.append(name.relative_to(ROOT).as_posix())
    return {
        "renderer": "Poppler pdftoppm, 110 dpi",
        "rendered_pages": len(pages),
        "word_bounding_boxes_verified": len(words),
        "contact_sheets": sheets,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--font-dir",
        type=Path,
        default=Path("C:/Windows/Fonts"),
        help="Directory containing arial.ttf, arialbd.ttf, ariali.ttf, arialbi.ttf",
    )
    parser.add_argument(
        "--render",
        action="store_true",
        help="Render all pages and build contact sheets with Poppler",
    )
    args = parser.parse_args()
    for name, file in [
        ("Report", "arial.ttf"),
        ("ReportBold", "arialbd.ttf"),
        ("ReportItalic", "ariali.ttf"),
        ("ReportBoldItalic", "arialbi.ttf"),
    ]:
        pdfmetrics.registerFont(TTFont(name, str(args.font_dir / file)))
    pdfmetrics.registerFontFamily(
        "Report",
        normal="Report",
        bold="ReportBold",
        italic="ReportItalic",
        boldItalic="ReportBoldItalic",
    )
    rl_config.invariant = 1
    OUTPUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    manifest = {
        "export_date": "2026-10-06",
        "track": "AWS ML Engineering",
        "deadline": "2026-10-16",
        "status": "review-ready export; official submission and lecturer approval pending",
        "repository": REPOSITORY,
        "pinned_link_commit": None,
        "exporter": {
            "path": "scripts/export_cap01.py",
            "sha256": digest(Path(__file__)),
            "python_dependencies": {
                name: importlib.metadata.version(name)
                for name in ["reportlab", "pypdf", "pillow", "pdfplumber"]
            },
        },
        "fonts": {
            name: digest(args.font_dir / name)
            for name in ["arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf"]
        },
        "notes": [
            "Markdown substance preserved; wide tables use labeled records.",
            "Mermaid Gantt task rows are rendered as a native vector schedule.",
            "Source dates and pending approvals remain unchanged.",
            "External references preserved without new web research.",
            "PDF metadata timestamps use ReportLab invariant mode for deterministic rebuilds.",
        ],
        "outputs": [],
    }
    for stem, title, number, sources in SPECS:
        builder = Builder(sources, title, number)
        path = OUTPUT / f"{stem}.pdf"
        ReportDoc(path, title).build(builder.story())
        count = len(PdfReader(path).pages)
        ReportDoc(path, title, total_pages=count).build(builder.story())
        checks = verify(path, builder)
        if args.render:
            checks.update(render(path))
        manifest["pinned_link_commit"] = builder.revision
        manifest["outputs"].append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": digest(path),
                "bytes": path.stat().st_size,
                "sources": [
                    {"path": source, "sha256": digest(ROOT / source)} for source in sources
                ],
                "checks": checks,
            }
        )
        print(
            f"{path.name}: {checks['page_count']} pages; "
            f"{checks['source_text_fragments_verified']} text fragments and "
            f"{checks['unique_links_verified']} links verified"
        )
    (OUTPUT / "cap01-export-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
