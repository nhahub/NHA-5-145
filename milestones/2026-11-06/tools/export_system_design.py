"""Build the source-backed November design report and editable diagram set.

Document tooling only. No application, provider or AWS connection is imported.
"""

from __future__ import annotations

import hashlib
import html
import importlib.metadata
import json
import math
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pdfplumber
from PIL import Image as PILImage
from pypdf import PdfReader
from reportlab import rl_config
from reportlab.lib import colors
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
DIAGRAMS = ROOT / "docs/diagrams/system-design-20261028"
OUTPUT = ROOT / "output/pdf/system-analysis-design-2026-10-28.pdf"
WORK = ROOT / "work/system-design-20261028"
WIDTH, HEIGHT = A4
MARGIN = 45
CONTENT = WIDTH - 2 * MARGIN
INK = colors.HexColor("#183447")
TEAL = colors.HexColor("#087E8B")
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
SOURCES = ["docs/system-analysis-design.md", "docs/system-design-views.md"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(text):
    return text.translate(str.maketrans({"—": "-", "–": "-", "’": "'", "“": '"', "”": '"'}))


def compact(text):
    return re.sub(r"\s+", "", clean(text))


def plain(text):
    return LINK.sub(r"\1", clean(text)).replace("**", "").replace("`", "")


class Diagram:
    def __init__(self, stem, title, width=1000, height=640):
        self.stem, self.title, self.width, self.height = stem, title, width, height
        self.file = ET.Element("mxfile", host="local", type="device")
        page = ET.SubElement(self.file, "diagram", id=stem, name=title)
        model = ET.SubElement(page, "mxGraphModel", pageWidth=str(width), pageHeight=str(height))
        self.root = ET.SubElement(model, "root")
        ET.SubElement(self.root, "mxCell", id="0")
        ET.SubElement(self.root, "mxCell", id="1", parent="0")
        self.positions = {}
        self.count = 0
        self.box("title", title, 20, 12, width - 40, 45, "text", 25)

    def box(self, key, label, x, y, w, h, shape="box", size=18, fill="#EFF6F8"):
        assert key not in self.positions
        self.positions[key] = (x, y, w, h)
        shape_style = {
            "box": "rounded=1;",
            "actor": "ellipse;",
            "decision": "rhombus;",
            "data": "rounded=0;",
            "text": "text;strokeColor=none;fillColor=none;",
            "boundary": "rounded=0;dashed=1;",
        }[shape]
        style = (
            shape_style + f"whiteSpace=wrap;html=1;fontSize={size};"
            f"fontColor=#183447;fillColor={fill};strokeColor=#738E9B;"
        )
        if shape == "text":
            style += "strokeColor=none;fillColor=none;"
        cell = ET.SubElement(
            self.root,
            "mxCell",
            id=key,
            value=html.escape(label).replace("\n", "<br>"),
            style=style,
            vertex="1",
            parent="1",
            kind=shape,
        )
        ET.SubElement(
            cell,
            "mxGeometry",
            x=str(x),
            y=str(y),
            width=str(w),
            height=str(h),
            **{"as": "geometry"},
        )

    def line(self, key, points, label="", label_pos=None, dashed=False, arrow=True):
        self.count += 1
        cell = ET.SubElement(
            self.root,
            "mxCell",
            id=key,
            value="",
            edge="1",
            parent="1",
            style=(
                "edgeStyle=none;html=1;strokeColor=#456A7B;strokeWidth=1.5;"
                f"endArrow={'block' if arrow else 'none'};dashed={int(dashed)};"
            ),
        )
        geometry = ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})
        # Explicit endpoints support sequence lifelines and fixed wireframe callouts.
        for point, name in [(points[0], "sourcePoint"), (points[-1], "targetPoint")]:
            ET.SubElement(geometry, "mxPoint", x=str(point[0]), y=str(point[1]), **{"as": name})
        if len(points) > 2:
            waypoints = ET.SubElement(geometry, "Array", **{"as": "points"})
            for x, y in points[1:-1]:
                ET.SubElement(waypoints, "mxPoint", x=str(x), y=str(y))
        if label:
            x, y = label_pos or (
                (points[0][0] + points[-1][0]) / 2 - 75,
                (points[0][1] + points[-1][1]) / 2 - 13,
            )
            self.box(key + "-label", label, x, y, 150, 28, "text", 15)

    def connect(self, source, target, label="", label_pos=None, dashed=False):
        a, b = self.positions[source], self.positions[target]
        ac = (a[0] + a[2] / 2, a[1] + a[3] / 2)
        bc = (b[0] + b[2] / 2, b[1] + b[3] / 2)
        dx, dy = bc[0] - ac[0], bc[1] - ac[1]
        if abs(dx) > abs(dy):
            start = (a[0] + (a[2] if dx > 0 else 0), ac[1])
            end = (b[0] + (0 if dx > 0 else b[2]), bc[1])
        else:
            start = (ac[0], a[1] + (a[3] if dy > 0 else 0))
            end = (bc[0], b[1] + (0 if dy > 0 else b[3]))
        self.line(f"edge-{self.count}", [start, end], label, label_pos, dashed)

    def save(self):
        path = DIAGRAMS / f"{self.stem}.drawio"
        ET.indent(self.file, space="  ")
        ET.ElementTree(self.file).write(path, encoding="utf-8", xml_declaration=True)
        tree = ET.parse(path)
        cells = tree.findall(".//mxCell")
        ids = [cell.attrib["id"] for cell in cells]
        assert len(ids) == len(set(ids))
        assert "<!--" not in path.read_text(encoding="utf-8")
        for cell in cells:
            if cell.get("vertex") == "1":
                g = cell.find("mxGeometry")
                x, y, w, h = (float(g.get(k)) for k in ["x", "y", "width", "height"])
                assert 0 <= x <= x + w <= self.width and 0 <= y <= y + h <= self.height
        return path


def define_diagrams():
    diagrams = []

    d = Diagram("01-context", "01 / System context", height=510)
    d.box("shopper", "Shopper\nRequests, selects, confirms", 30, 195, 240, 105, "actor")
    d.box(
        "system",
        "Shopping Copilot\nControlled Storefront\nAdvice + guarded Actions",
        370,
        185,
        260,
        125,
    )
    d.box(
        "provider",
        "External provider\nInterpretation / transcription\nNo execution authority",
        730,
        185,
        240,
        125,
    )
    d.box("owner", "Project owner\nContent, evidence, operation", 380, 375, 240, 90, "actor")
    d.connect("shopper", "system", "requests", (245, 210))
    d.connect("system", "provider", "HTTPS", (605, 210))
    d.connect("owner", "system", "maintains", (510, 325))
    diagrams.append(d)

    d = Diagram("02-containers", "02 / Application execution boundaries", height=640)
    d.box("panel", "Panel / TypeScript\nChat, decisions, SSE", 40, 100, 250, 95)
    d.box("ui", "Storefront + Bridge\nEmbedded browser document", 710, 100, 250, 95)
    d.box("agent", "Agent / FastAPI\nOwn sessions and task policy", 40, 290, 250, 100)
    d.box("store", "Storefront / Express\nOwn per-Shopper commerce", 710, 290, 250, 100)
    d.box("model", "Configured model\nStructured proposals", 40, 500, 250, 90)
    d.box("ledger", "Allowance ledger\nSQLite / durable", 375, 500, 250, 90, "data")
    d.box("db", "Catalogue\nSQLite / durable", 710, 500, 250, 90, "data")
    d.connect("panel", "ui", "postMessage", (420, 125))
    d.connect("panel", "agent", "HTTP / SSE", (165, 225))
    d.connect("ui", "store", "shopping HTTP", (785, 225))
    d.connect("agent", "store", "private evidence", (420, 320))
    d.connect("agent", "model", "HTTPS", (150, 430))
    d.connect("agent", "ledger", "reserve / settle", (275, 450))
    d.connect("store", "db", "read / import", (785, 430))
    diagrams.append(d)

    d = Diagram("03-data-flow", "03 / Request, evidence and observed outcome", height=630)
    for key, label, x, y in [
        ("input", "1 / Panel + Bridge\nOwned request / safe Snapshot", 45, 105),
        ("interpret", "2 / Interpret + validate\nLLM is not authority", 385, 105),
        ("provider", "External model\nBounded context", 725, 105),
        ("catalogue", "Catalogue evidence\nCurrent revision / facts", 725, 310),
        ("plan", "3 / Plan + confirm\nTargets, bounds, freshness", 385, 310),
        ("effect", "4 / Storefront effect\nExact variant / revision", 45, 310),
        ("state", "Task / event memory\nResult identity + cursor", 385, 510),
    ]:
        d.box(key, label, x, y, 230, 85)
    d.connect("input", "interpret", "message", (245, 125))
    d.connect("interpret", "provider", "HTTPS", (585, 125))
    d.connect("catalogue", "interpret", "facts", (670, 235))
    d.connect("interpret", "plan", "valid intent", (475, 235))
    d.connect("plan", "effect", "checked Action", (245, 330))
    d.connect("effect", "input", "result + Snapshot", (50, 235))
    d.connect("plan", "state", "record / match", (475, 440))
    d.box(
        "note",
        "Advice returns read-only text/cards through the Panel; it cannot mutate.",
        60,
        560,
        270,
        48,
        "text",
        16,
    )
    diagrams.append(d)

    d = Diagram(
        "04-data-model", "04 / Physical catalogue and separate inference ledger", height=660
    )
    d.box("meta", "catalogue_meta\nPK id = 1\nschema_version, revision", 30, 100, 235, 125, "data")
    d.box(
        "products",
        "products\nPK id; ordinal, revision\ndocument, category, type\n"
        "price_minor, available\nabsent facts, added_at",
        350,
        95,
        300,
        180,
        "data",
    )
    d.box(
        "attrs",
        "product_attributes\nPK product_id, kind, value\n"
        "FK product_id -> products\npresent; ON DELETE CASCADE",
        725,
        95,
        250,
        180,
        "data",
        17,
    )
    d.box(
        "fts",
        "product_fts / FTS5\nid UNINDEXED, text\n"
        "Maintained by repository\nNo declared SQL foreign key",
        350,
        355,
        300,
        130,
        "data",
        17,
    )
    d.connect("products", "attrs", "1 to many", (600, 165))
    d.connect("products", "fts", "indexes text", (495, 300), True)
    d.box(
        "policy",
        "Separate inference.sqlite\npolicy: identity, allowance\nenabled, version",
        30,
        515,
        390,
        105,
        "data",
        17,
    )
    d.box(
        "attempts",
        "attempts\nPK id; reservation, charged\nsettled (integer nanodollars)",
        570,
        515,
        390,
        105,
        "data",
        17,
    )
    d.box("no_fk", "Same ledger; no declared SQL FK", 400, 555, 170, 45, "text", 14)
    diagrams.append(d)

    d = Diagram("05-action-sequence", "05 / One validated cart-change sequence", height=690)
    xs = [85, 250, 415, 580, 745, 910]
    for x, label in zip(
        xs, ["Shopper", "Panel", "Agent", "Model", "Bridge", "Storefront"], strict=True
    ):
        d.box(label, label, x - 65, 85, 130, 60, size=18)
        d.line(label + "-life", [(x, 145), (x, 655)], dashed=True, arrow=False)
    messages = [
        (0, 1, "1 Request"),
        (1, 4, "2 Current Snapshot"),
        (1, 2, "3 Owned message + observation"),
        (2, 3, "4 Interpret bounded context"),
        (3, 2, "5 Proposed intent / target"),
        (2, 1, "6 Validated Action + identity"),
        (1, 4, "7 Execute if current"),
        (4, 5, "8 Permitted control / revision"),
        (5, 4, "9 Authoritative effect"),
        (4, 1, "10 Result + fresh Snapshot"),
        (1, 2, "11 Match task / Action / sequence"),
        (2, 1, "12 Verified completion"),
    ]
    for index, (a, b, text) in enumerate(messages):
        y = 175 + index * 40
        d.line("message-" + str(index), [(xs[a], y), (xs[b], y)])
        width = max(320, abs(xs[b] - xs[a]))
        center = (xs[a] + xs[b]) / 2
        d.box(
            "text-" + str(index),
            text,
            max(10, center - width / 2),
            y - 27,
            min(width, 980),
            25,
            "text",
            15,
        )
    diagrams.append(d)

    d = Diagram("06-confirmation", "06 / Guarded Mutation activity", height=640)
    d.box("request", "Supported guarded request", 350, 85, 300, 70)
    d.box("offer", "Offer exact effect +\ncurrent state signature", 350, 205, 300, 80)
    d.box("decision", "Fresh matching\nConfirmation?", 395, 350, 210, 105, "decision", 18)
    d.box("reject", "Expired / changed / cancelled\nNo mutation", 35, 360, 265, 90)
    d.box("execute", "Bridge + Storefront\nRecheck and consume once", 700, 360, 265, 90)
    d.box("result", "Match actual ActionResult\nComplete or reconcile", 700, 535, 265, 75)
    d.connect("request", "offer", "describe", (510, 165))
    d.connect("offer", "decision", "Shopper answer", (510, 305))
    d.connect("decision", "reject", "no", (275, 365))
    d.connect("decision", "execute", "yes", (590, 365))
    d.connect("execute", "result", "observed effect", (805, 475))
    diagrams.append(d)

    d = Diagram("07-task-state", "07 / Shopping Task principal states", height=650)
    for key, label, x, y in [
        ("interpret", "interpreting", 365, 95),
        ("question", "awaiting_answer", 30, 285),
        ("action", "awaiting_action_result", 700, 285),
        ("paused", "paused", 365, 480),
        ("done", "completed", 710, 520),
        ("cancel", "cancelled / Stop", 30, 520),
    ]:
        d.box(key, label, x, y, 260, 75, "actor", 19)
    d.connect("interpret", "question", "ask / confirm", (170, 205))
    d.line("answer-edge", [(290, 315), (325, 315), (325, 150), (365, 150)], "answer", (220, 235))
    d.connect("interpret", "action", "dispatch", (635, 205))
    d.connect("action", "done", "goal verified", (800, 415))
    d.connect("action", "paused", "failure / uncertain", (590, 415))
    d.connect("paused", "interpret", "eligible retry", (475, 350))
    d.connect("question", "cancel", "Stop", (100, 425))
    d.box(
        "note",
        "Stop cancels active/paused work.\nLate results never restart a finished task.",
        310,
        585,
        390,
        55,
        "text",
        15,
    )
    diagrams.append(d)

    d = Diagram(
        "08-host-lifecycle", "08 / Durable host lifecycle (prepared, not activated)", height=650
    )
    for key, label, x, y in [
        ("stopped", "Stopped\nInvitation-gated wake", 30, 95),
        ("start", "Starting\nGeneration + command", 370, 95),
        ("ready", "Ready\nFive signed checks", 710, 95),
        ("work", "Active work leases\nProtect uncertain work", 710, 310),
        ("drain", "Draining\nNo new work", 370, 510),
        ("stop", "Stopping / observed\nNever blind command retry", 30, 510),
        ("failed", "Failed / unavailable\nKeep authority and holds", 30, 310),
    ]:
        d.box(key, label, x, y, 260, 90)
    d.connect("stopped", "start", "valid wake", (245, 120))
    d.connect("start", "ready", "signed ready", (585, 120))
    d.connect("ready", "work", "admit", (805, 230))
    d.connect("work", "drain", "idle / no work", (590, 450))
    d.connect("drain", "stop", "stop intent", (245, 535))
    d.connect("start", "failed", "deadline / failure", (195, 235))
    d.box(
        "note",
        "Polling is not activity.\nUnknown command/lease outcomes\n"
        "remain protected; no quota reset.",
        300,
        310,
        385,
        100,
        "text",
        17,
    )
    diagrams.append(d)

    d = Diagram("09-module-view", "09 / Selected classes and facade composition", height=730)
    d.box(
        "facade",
        "SessionStore\ncreate(), submit_message()\naccept_result(), reconcile()\nstop()",
        25,
        90,
        285,
        165,
        "data",
        17,
    )
    d.box(
        "runtime",
        "TaskRuntime\nsessions, planner, clock\nconfirmation_registrar\nShared task-module context",
        360,
        90,
        280,
        165,
        "data",
        17,
    )
    d.box(
        "registry",
        "SessionRegistry\ncreate(), get()\nassert_lease(), takeover()\nCapacity / idle expiry",
        700,
        90,
        280,
        165,
        "data",
        17,
    )
    d.connect("facade", "runtime")
    d.connect("runtime", "registry")
    d.box(
        "task",
        "ActiveTask\ntask_id, status\naction, confirmation\nmutation_proposal",
        25,
        430,
        285,
        170,
        "data",
        17,
    )
    d.box(
        "ledger",
        "ConfirmationLedger\noffer(), can_confirm()\nconfirm(), invalidate()\n"
        "One current bounded offer",
        360,
        430,
        280,
        170,
        "data",
        17,
    )
    d.box(
        "session",
        "Session\nsession_id\nactive_task, last_task\nevents, accepted_results\n"
        "requires_reconciliation",
        700,
        430,
        280,
        190,
        "data",
        17,
    )
    d.connect("registry", "session", "owns 0..N", (845, 325))
    d.line(
        "task-reference",
        [(740, 430), (740, 355), (165, 355), (165, 430)],
        "active / last",
        (380, 315),
    )
    d.connect("task", "ledger", "0..1", (265, 475))
    d.box(
        "note",
        "Selected real members; active_task and last_task are 0..1 each.\n"
        "Task modules receive TaskRuntime. Session/Task records remain process memory.",
        125,
        650,
        750,
        60,
        "text",
        17,
    )
    diagrams.append(d)

    d = Diagram(
        "10-cloud-deployment", "10 / Selected Stockholm design - no resources applied", height=720
    )
    d.box("browser", "Invited Shopper browser", 30, 85, 270, 75, "actor")
    d.box("cf", "Generated CloudFront HTTPS\nWaiting page + wake/status", 370, 85, 270, 85, size=17)
    d.box(
        "lambda", "Startup Lambda / IAM URL\nController Lambda (worker)", 710, 85, 260, 85, size=17
    )
    d.box("s3", "Private S3 waiting assets\nOAC, no public bucket", 370, 285, 270, 85, "data", 17)
    d.box(
        "dynamo",
        "DynamoDB authority\nInvitation / generation / leases",
        710,
        285,
        260,
        85,
        "data",
        17,
    )
    d.box(
        "proxy",
        "app.scpilot.tech + store.scpilot.tech\nRetained EIP -> Caddy HTTPS",
        30,
        495,
        350,
        95,
        size=16,
    )
    d.box(
        "apps",
        "One Linux EC2 candidate\nAgent + Storefront / loopback\nPersistent catalogue + ledger",
        460,
        490,
        320,
        110,
        size=17,
    )
    d.box(
        "provider",
        "Explicit provider\nBedrock candidate /\nOpenRouter fallback",
        790,
        595,
        190,
        95,
        size=16,
    )
    d.connect("browser", "cf", "startup", (245, 105))
    d.connect("cf", "lambda", "OAC control", (595, 110))
    d.connect("cf", "s3", "OAC assets", (470, 210))
    d.connect("lambda", "dynamo", "atomic state", (800, 210))
    d.connect("browser", "proxy", "shopping HTTPS", (35, 300))
    d.connect("proxy", "apps", "local routes", (345, 520))
    d.connect("apps", "provider", "HTTPS", (750, 580))
    d.box(
        "note",
        "Control is separate from shopping ingress. Actual IAM, DNS, TLS,\n"
        "model, credits and exact apply/rollback approval remain gates.",
        390,
        395,
        560,
        65,
        "text",
        16,
    )
    diagrams.append(d)

    d = Diagram("11-host-isolation", "11 / Prepared native host identities and state", height=650)
    d.box(
        "metadata",
        "Root metadata barrier\nAllows only trusted root / Agent\nRequired by application units",
        340,
        85,
        340,
        105,
        size=18,
    )
    for key, label, x in [
        ("agent", "Agent / copilot\nPrivate host config + ledger\nReadiness key; role access", 30),
        ("store", "Store / copilot-store\nOwn service-key copy\nCatalogue writer + WAL", 370),
        ("proxy", "Caddy / copilot-proxy\nNo application keys\nCertificate state only", 710),
    ]:
        d.box(key, label, x, 310, 270, 115, size=17)
    for target in ["agent", "store", "proxy"]:
        d.connect("metadata", target, dashed=True)
    d.box(
        "catalogue",
        "Store-owned catalogue directory\nAgent supplementary group + read-only access\n"
        "No Agent sidecar creation or catalogue writes",
        215,
        505,
        570,
        110,
        "data",
        18,
    )
    d.connect("agent", "catalogue", "read only", (155, 455))
    d.connect("store", "catalogue", "own writes", (485, 455))
    diagrams.append(d)

    d = Diagram(
        "12-wireframes", "12 / Interaction wireframes - schematic, not screenshots", height=690
    )
    d.box("desktop", "Desktop / separate browser origins", 20, 85, 615, 40, "text", 20)
    d.box(
        "store",
        "Embedded Storefront\nProducts / selected variant\nManual login and payment",
        25,
        145,
        330,
        360,
        size=21,
    )
    d.box(
        "chat",
        "Conversation / status\nVerified product cards\nExact Confirmation effect\nVisible Undo",
        375,
        145,
        255,
        255,
        size=19,
    )
    d.box("composer", "Editable request\nSend / reachable Stop", 375, 425, 255, 100, size=18)
    d.box("mobile", "Mobile", 710, 85, 250, 40, "text", 20)
    d.box("mstatus", "Status / Storefront access", 710, 145, 250, 60, size=17)
    d.box(
        "mchat",
        "Scrollable conversation\nCards / clarification\nConfirmation / Undo",
        710,
        225,
        250,
        265,
        size=19,
    )
    d.box("mcompose", "Composer + Send + Stop", 710, 515, 250, 80, size=16)
    d.box(
        "note",
        "RTL, keyboard focus and announced state are design requirements.\n"
        "This view does not claim measured accessibility certification.",
        25,
        565,
        615,
        75,
        "text",
        17,
    )
    diagrams.append(d)
    return [diagram.save() for diagram in diagrams]


def read_style(value):
    return dict(part.split("=", 1) for part in value.split(";") if "=" in part)


def draw_diagram(canvas, path):
    model = ET.parse(path).find(".//mxGraphModel")
    height = float(model.get("pageHeight"))
    cells = model.findall("./root/mxCell")
    for cell in [c for c in cells if c.get("edge") == "1"]:
        style = read_style(cell.get("style"))
        g = cell.find("mxGeometry")
        a = g.find("mxPoint[@as='sourcePoint']")
        b = g.find("mxPoint[@as='targetPoint']")
        points = [a, *g.findall("Array[@as='points']/mxPoint"), b]
        coords = [(float(p.get("x")), height - float(p.get("y"))) for p in points]
        x1, y1 = coords[-2]
        x2, y2 = coords[-1]
        canvas.setStrokeColor(colors.HexColor("#456A7B"))
        canvas.setLineWidth(1.5)
        canvas.setDash(5, 4) if style.get("dashed") == "1" else canvas.setDash()
        line = canvas.beginPath()
        line.moveTo(*coords[0])
        for point in coords[1:]:
            line.lineTo(*point)
        canvas.drawPath(line)
        if style.get("endArrow") != "none":
            angle = math.atan2(y2 - y1, x2 - x1)
            p = canvas.beginPath()
            p.moveTo(x2, y2)
            for offset in [0.45, -0.45]:
                p.lineTo(x2 - 10 * math.cos(angle + offset), y2 - 10 * math.sin(angle + offset))
            p.close()
            canvas.setFillColor(colors.HexColor("#456A7B"))
            canvas.drawPath(p, fill=1, stroke=0)
    canvas.setDash()
    for cell in [c for c in cells if c.get("vertex") == "1"]:
        style = read_style(cell.get("style"))
        g = cell.find("mxGeometry")
        x, y, w, h = [float(g.get(k)) for k in ["x", "y", "width", "height"]]
        bottom = height - y - h
        kind = cell.get("kind")
        fill = style.get("fillColor", "#EFF6F8")
        if kind != "text":
            canvas.setFillColor(colors.HexColor(fill))
            canvas.setStrokeColor(colors.HexColor("#738E9B"))
            canvas.setLineWidth(1)
            if kind == "actor":
                canvas.ellipse(x, bottom, x + w, bottom + h, fill=1, stroke=1)
            elif kind == "decision":
                p = canvas.beginPath()
                p.moveTo(x + w / 2, bottom + h)
                p.lineTo(x + w, bottom + h / 2)
                p.lineTo(x + w / 2, bottom)
                p.lineTo(x, bottom + h / 2)
                p.close()
                canvas.drawPath(p, fill=1, stroke=1)
            else:
                canvas.roundRect(x, bottom, w, h, 9 if kind == "box" else 0, fill=1, stroke=1)
        label = html.unescape(cell.get("value")).replace("<br>", "\n")
        font_size = float(style.get("fontSize", 18))
        s = ParagraphStyle(
            "figure",
            fontName="Design",
            fontSize=font_size,
            leading=font_size * 1.25,
            textColor=INK,
            alignment=1,
        )
        para = Paragraph("<br/>".join(html.escape(line) for line in label.splitlines()), s)
        tw, th = para.wrap(w - 14, h - 8)
        if th > h - 5:
            raise ValueError(f"Figure label overflow: {path.name}/{cell.get('id')}")
        para.drawOn(canvas, x + 7, bottom + (h - th) / 2)


class DiagramFlowable(Flowable):
    def __init__(self, path):
        super().__init__()
        self.path = path
        model = ET.parse(path).find(".//mxGraphModel")
        self.raw_width = float(model.get("pageWidth"))
        self.raw_height = float(model.get("pageHeight"))
        self.width = CONTENT
        self.scale = CONTENT / self.raw_width
        self.height = self.raw_height * self.scale

    def draw(self):
        self.canv.saveState()
        self.canv.scale(self.scale, self.scale)
        draw_diagram(self.canv, self.path)
        self.canv.restoreState()


def export_figures(paths):
    from reportlab.pdfgen.canvas import Canvas

    for path in paths:
        model = ET.parse(path).find(".//mxGraphModel")
        w, h = float(model.get("pageWidth")), float(model.get("pageHeight"))
        pdf = WORK / (path.stem + ".pdf")
        c = Canvas(str(pdf), pagesize=(w, h), invariant=1)
        draw_diagram(c, path)
        c.save()
        subprocess.run(
            [
                "pdftoppm",
                "-singlefile",
                "-scale-to",
                "1800",
                "-png",
                str(pdf),
                str(path.with_suffix("")),
            ],
            check=True,
            capture_output=True,
        )


class DesignDoc(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(
            str(path),
            pagesize=A4,
            title="Shopping Copilot - System Analysis and Design",
            author="Shopping Copilot project",
            allowSplitting=1,
        )
        frame = Frame(
            MARGIN,
            45,
            CONTENT,
            HEIGHT - 100,
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        self.addPageTemplates(PageTemplate(id="main", frames=frame, onPage=self.decorate))

    def decorate(self, c, doc):
        c.setFont("Design", 8)
        c.setFillColor(colors.HexColor("#52616D"))
        c.drawString(MARGIN, HEIGHT - 28, "SHOPPING COPILOT / SYSTEM ANALYSIS AND DESIGN")
        c.drawRightString(WIDTH - MARGIN, HEIGHT - 28, "AWS ML Engineering")
        c.drawString(MARGIN, 23, "Revision 2 / 28 October 2026 / due 6 November")
        c.drawRightString(WIDTH - MARGIN, 23, f"Page {doc.page}")

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in {"heading", "section"}:
            title = flowable.getPlainText()
            key = "section-" + hashlib.sha256(f"{self.page}:{title}".encode()).hexdigest()[:18]
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(title, key, 0)


class Report:
    def __init__(self):
        self.fragments = []
        self.links = set()
        self.figure_names = []
        self.styles = {
            "body": ParagraphStyle(
                "body", fontName="Design", fontSize=10, leading=14.5, spaceAfter=8, textColor=INK
            ),
            "heading": ParagraphStyle(
                "heading",
                fontName="DesignBold",
                fontSize=23,
                leading=28,
                spaceAfter=15,
                textColor=INK,
            ),
            "section": ParagraphStyle(
                "section",
                fontName="DesignBold",
                fontSize=16,
                leading=21,
                spaceBefore=15,
                spaceAfter=9,
                keepWithNext=True,
                textColor=INK,
            ),
            "sub": ParagraphStyle(
                "sub",
                fontName="DesignBold",
                fontSize=12,
                leading=16,
                spaceBefore=12,
                spaceAfter=7,
                keepWithNext=True,
                textColor=TEAL,
            ),
            "cell": ParagraphStyle(
                "cell", fontName="Design", fontSize=8.3, leading=11.2, spaceAfter=0, textColor=INK
            ),
            "caption": ParagraphStyle(
                "caption", fontName="Design", fontSize=8.5, leading=12, spaceAfter=12, textColor=INK
            ),
        }

    def inline(self, text, source):
        text = html.escape(clean(text))

        def replace(match):
            label, target = html.unescape(match[1]), html.unescape(match[2])
            if not target.startswith(("http://", "https://")):
                p, _, anchor = target.partition("#")
                absolute = (ROOT / source).parent / p
                if not absolute.exists():
                    raise ValueError(f"Missing linked source: {source}/{target}")
                # Portable source package link, no fabricated remote revision.
                target = "../evidence/" + absolute.resolve().relative_to(ROOT).as_posix()
                if anchor:
                    target += "#" + anchor
            self.links.add(target)
            return (
                f'<a href="{html.escape(target, quote=True)}" '
                f'color="#087E8B">{html.escape(label)}</a>'
            )

        text = LINK.sub(replace, text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"`([^`]+)`", r"<b>\1</b>", text)
        return text

    def para(self, text, source, style="body"):
        self.fragments.append(plain(text))
        return Paragraph(self.inline(text, source), self.styles[style])

    def table(self, lines, source):
        rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
        rows = [rows[0]] + rows[2:]
        count = len(rows[0])
        if any(len(row) != count for row in rows):
            raise ValueError("Inconsistent table")
        if count == 4 and rows[0][0] == "ID":
            widths = [43, 63, CONTENT - 159, 53]
        elif count == 4:
            widths = [72, 113, CONTENT - 265, 80]
        else:
            widths = [90, CONTENT * 0.43, CONTENT - 90 - CONTENT * 0.43]
        if count != len(widths):
            widths = [CONTENT / count] * count
        cells = [[self.para(cell, source, "cell") for cell in row] for row in rows]
        table = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DAE9EE")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F5F8FA")],
                    ),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9D9D9")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        return [table, Spacer(1, 10)]

    def markdown(self, source):
        lines = (ROOT / source).read_text(encoding="utf-8").splitlines()
        result = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            if line.startswith("```mermaid"):
                # The matching context/container views are embedded as native vectors.
                while i + 1 < len(lines) and not lines[i + 1].startswith("```"):
                    i += 1
                i += 2
                result.append(
                    self.para(
                        "Mermaid editing source is retained in the companion Markdown.",
                        source,
                        "caption",
                    )
                )
                continue
            if line.startswith("!["):
                match = re.fullmatch(r"!\[([^\]]+)\]\(([^)]+)\)", line)
                caption, name = match.groups()
                path = (ROOT / source).parent / name
                native = path.with_suffix(".drawio")
                self.figure_names.append(native.relative_to(ROOT).as_posix())
                headings = []
                while result and isinstance(result[-1], Paragraph):
                    if result[-1].style.name not in {"section", "sub"}:
                        break
                    headings.insert(0, result.pop())
                result.append(
                    KeepTogether(
                        headings
                        + [
                            Spacer(1, 8),
                            DiagramFlowable(native),
                            self.para(caption, source, "caption"),
                        ]
                    )
                )
            elif line.startswith("|"):
                block = []
                while i < len(lines) and lines[i].strip().startswith("|"):
                    block.append(lines[i])
                    i += 1
                result.extend(self.table(block, source))
                continue
            elif line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                result.append(
                    self.para(
                        line[level:].strip(),
                        source,
                        "heading" if level == 1 else "section" if level == 2 else "sub",
                    )
                )
            else:
                parts = [line]
                if not re.match(r"[-*] |\d+\. ", line):
                    while (
                        i + 1 < len(lines)
                        and lines[i + 1].strip()
                        and not re.match(r"[#|!`]|[-*] |\d+\. ", lines[i + 1].strip())
                    ):
                        i += 1
                        parts.append(lines[i].strip())
                result.append(self.para(" ".join(parts), source))
            i += 1
        return result

    def story(self):
        cover = [
            Spacer(1, 72),
            Paragraph("DOCUMENT 04 / DEPI", self.styles["sub"]),
            Spacer(1, 22),
            Paragraph(
                "System Analysis<br/>and Design",
                ParagraphStyle("cover", parent=self.styles["heading"], fontSize=34, leading=40),
            ),
            Paragraph("Shopping Copilot", self.styles["section"]),
            Paragraph(
                "Arabic-first shopping advice and guarded Storefront actions", self.styles["body"]
            ),
            Spacer(1, 30),
        ]
        cover.extend(
            self.table(
                [
                    "| Field | Value |",
                    "| --- | --- |",
                    "| Track | AWS ML Engineering |",
                    "| Revision / prepared | 2 / 28 October 2026 |",
                    "| Submission deadline | 6 November 2026 |",
                    "| Graduation target | Controlled Storefront; native Linux host; "
                    "Stockholm Free-plan AWS deployment |",
                    "| Evidence status | Implemented local software and rehearsed host boundaries; "
                    "actual cloud/model acceptance remains open |",
                ],
                SOURCES[0],
            )
        )
        cover += [
            Spacer(1, 15),
            Paragraph(
                "Architecture, data model, behavior, interfaces, deployment, safety, wireframes "
                "and requirement traceability. Includes editable diagram sources "
                "and a source/evidence manifest.",
                self.styles["body"],
            ),
            PageBreak(),
        ]
        return cover + self.markdown(SOURCES[0]) + [PageBreak()] + self.markdown(SOURCES[1])


def register_fonts():
    for name, filename in [("Design", "arial.ttf"), ("DesignBold", "arialbd.ttf")]:
        pdfmetrics.registerFont(TTFont(name, str(Path("C:/Windows/Fonts") / filename)))
    pdfmetrics.registerFontFamily(
        "Design", normal="Design", bold="DesignBold", italic="Design", boldItalic="DesignBold"
    )


def verify_pdf(report):
    reader = PdfReader(OUTPUT)
    bodies = []
    for index, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        prefix = (
            "SHOPPING COPILOT / SYSTEM ANALYSIS AND DESIGN\nAWS ML Engineering\n"
            "Revision 2 / 28 October 2026 / due 6 November\n" + f"Page {index}\n"
        )
        if not text.startswith(prefix):
            raise ValueError(f"Unexpected page furniture {index}")
        bodies.append(text.removeprefix(prefix))
    all_text = compact("\n".join(bodies))
    absent = [part for part in report.fragments if compact(part) not in all_text]
    if absent:
        raise ValueError(f"Omitted source fragments: {absent[:3]}")
    expected_ids = {
        f"{prefix}-{i:02d}"
        for prefix, count in [("FR", 9), ("SQ", 7), ("GR", 5)]
        for i in range(1, count + 1)
    }
    requirements = (ROOT / "docs/cap01-requirements.md").read_text(encoding="utf-8")
    matrix = (ROOT / SOURCES[0]).read_text(encoding="utf-8")
    for name, source in [("requirements", requirements), ("design", matrix)]:
        found_ids = set(re.findall(r"\b(?:FR|SQ|GR)-\d{2}\b", source))
        if found_ids != expected_ids:
            raise ValueError(f"Incomplete requirement IDs in {name}: {found_ids ^ expected_ids}")
    if not all(identifier in all_text for identifier in expected_ids):
        raise ValueError("Requirement ID missing from PDF")
    annotations = {
        a.get_object().get("/A", {}).get("/URI") for p in reader.pages for a in p.get("/Annots", [])
    }
    if report.links - annotations:
        raise ValueError(f"Missing link annotations: {report.links - annotations}")
    with pdfplumber.open(OUTPUT) as pdf:
        words = [word for page in pdf.pages for word in page.extract_words()]
        for word in words:
            if not (
                MARGIN - 1 <= word["x0"] <= word["x1"] <= WIDTH - MARGIN + 1
                and 14 <= word["top"] <= word["bottom"] <= HEIGHT - 14
            ):
                raise ValueError(f"Out-of-bounds text: {word['text']}")
    return {
        "page_count": len(reader.pages),
        "source_fragments": len(report.fragments),
        "unique_links": len(report.links),
        "word_bounds_checked": len(words),
        "embedded_figures": len(report.figure_names),
        "requirement_ids": sorted(expected_ids),
    }


def render_report():
    pages = WORK / "pages"
    pages.mkdir(exist_ok=True)
    for old in pages.glob("page-*.png"):
        old.unlink()
    subprocess.run(
        ["pdftoppm", "-r", "110", "-png", str(OUTPUT), str(pages / "page")],
        check=True,
        capture_output=True,
    )
    images = sorted(pages.glob("page-*.png"))
    for start in range(0, len(images), 4):
        sheet = PILImage.new("RGB", (1150, 1670), "#DDE7EB")
        for j, path in enumerate(images[start : start + 4]):
            image = PILImage.open(path).convert("RGB")
            image.thumbnail((550, 810))
            sheet.paste(image, (15 + (j % 2) * 570, 15 + (j // 2) * 830))
        sheet.save(WORK / f"contact-{start // 4 + 1}.jpg")


def main():
    register_fonts()
    rl_config.invariant = 1
    DIAGRAMS.mkdir(parents=True, exist_ok=True)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    paths = define_diagrams()
    export_figures(paths)
    report = Report()
    DesignDoc(OUTPUT).build(report.story())
    checks = verify_pdf(report)
    render_report()
    review_path = OUTPUT.with_suffix(".review.json")
    review = json.loads(review_path.read_text(encoding="utf-8")) if review_path.exists() else {}
    reviewed = (
        review.get("pdf_sha256") == sha(OUTPUT)
        and review.get("pages_reviewed") == list(range(1, checks["page_count"] + 1))
        and review.get("figures_reviewed") == list(range(1, 13))
    )
    sources = SOURCES + ["docs/system-design-skills.md", "docs/system-design-submission.md"]
    evidence = [
        "AGENTS.md",
        "CONTEXT.md",
        "PROJECT_CHECKPOINT.md",
        "docs/cap06-host-isolation.md",
        "docs/cap06-apply-proposal.md",
        "docs/cap06-apply-inventory.json",
        "docs/cap05-bedrock.md",
        "docs/cap03-model-comparison-results.md",
        "docs/research/2026-10-15-gemini-replacement.md",
        "store/src/catalogue-db.ts",
        "agent/inference/ledger.py",
        "agent/session_state.py",
        "agent/llm/intent_pipeline.py",
        "agent/advice.py",
        "deploy/Caddyfile.public",
    ]
    manifest = {
        "prepared_on": "2026-10-28",
        "deadline": "2026-11-06",
        "revision": 2,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT)
        .decode()
        .strip(),
        "scope": (
            "Controlled Storefront; selected Stockholm host; "
            "no cloud activation or new runtime claim"
        ),
        "output": {
            "path": OUTPUT.relative_to(ROOT).as_posix(),
            "sha256": sha(OUTPUT),
            "checks": checks,
        },
        "sources": [{"path": p, "sha256": sha(ROOT / p)} for p in sources],
        "evidence": [{"path": p, "sha256": sha(ROOT / p)} for p in evidence],
        "diagrams": [
            {
                "path": p.relative_to(ROOT).as_posix(),
                "sha256": sha(p),
                "preview_sha256": sha(p.with_suffix(".png")),
            }
            for p in paths
        ],
        "exporter": {"path": "scripts/export_system_design.py", "sha256": sha(__file__)},
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in ["reportlab", "pypdf", "pdfplumber", "pillow"]
        },
        "fonts": {
            name: sha(Path("C:/Windows/Fonts") / name) for name in ["arial.ttf", "arialbd.ttf"]
        },
        "renderer": (
            "Local restricted draw.io XML subset to ReportLab vectors; "
            "Poppler previews. No desktop CLI used."
        ),
        "visual_review": (
            {"record": review_path.name, "sha256": sha(review_path), "status": "reviewed"}
            if reviewed
            else {"status": "pending", "instruction": "Inspect all rendered pages before delivery."}
        ),
    }
    manifest_path = OUTPUT.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    package = ROOT / "output/submission/system-design-2026-11-06"
    import shutil

    for directory in ["reports", "sources", "diagrams", "evidence", "provenance", "tools"]:
        (package / directory).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(OUTPUT, package / "reports/04-system-analysis-and-design.pdf")
    for source in sources:
        shutil.copyfile(ROOT / source, package / "sources" / Path(source).name)
    # Preserve each referenced evidence file at its repository-relative path.
    linked = set(evidence)
    for source in SOURCES:
        for target in LINK.findall((ROOT / source).read_text(encoding="utf-8")):
            destination = target[1]
            if not destination.startswith(("https:", "http:", "#")):
                p = ((ROOT / source).parent / destination.split("#")[0]).resolve()
                linked.add(p.relative_to(ROOT).as_posix())
    for source in linked:
        target = package / "evidence" / source
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / source, target)
    for p in paths:
        shutil.copyfile(p, package / "diagrams" / p.name)
        shutil.copyfile(p.with_suffix(".png"), package / "diagrams" / p.with_suffix(".png").name)
    shutil.copyfile(manifest_path, package / "provenance/export-manifest.json")
    review_copy = package / "provenance/visual-review.json"
    if reviewed:
        shutil.copyfile(review_path, review_copy)
    else:
        review_copy.unlink(missing_ok=True)
    shutil.copyfile(Path(__file__), package / "tools/export_system_design.py")
    (package / "README.md").write_text(
        "# Shopping Copilot - System Analysis and Design\n\n"
        "DEPI / AWS ML Engineering. Prepared 28 October 2026; due 6 November 2026.\n\n"
        f"Report: reports/04-system-analysis-and-design.pdf ({checks['page_count']} pages). "
        "Includes 12 vector views and all 21 requirement IDs.\n\n"
        "sources/: editable reports and methodology. diagrams/: editable draw.io XML and PNGs. "
        "evidence/: snapshot of referenced source records, preserving repository paths. "
        "provenance/: hashes/build checks. tools/: exporter snapshot for a full checkout.\n\n"
        "The main PDF's relative evidence links resolve within this package. Markdown source links "
        "retain repository layout; use the full checkout to edit/rebuild. "
        "No credentials, raw participant records or live state databases are included. "
        "This is a local prepared package, not official "
        "submission or cloud/model acceptance. See the report for remaining gates.\n",
        encoding="utf-8",
    )
    files = sorted(p for p in package.rglob("*") if p.is_file() and p.name != "checksums.sha256")
    (package / "checksums.sha256").write_text(
        "".join(sha(p) + "  " + p.relative_to(package).as_posix() + "\n" for p in files),
        encoding="utf-8",
    )
    archive = package.parent / "shopping-copilot-system-design-2026-11-06.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(package.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(package).as_posix())
    print(json.dumps({"pdf": str(OUTPUT), "archive": str(archive), **checks}, indent=2))


if __name__ == "__main__":
    main()
