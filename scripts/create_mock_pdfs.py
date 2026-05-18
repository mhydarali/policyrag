"""Generate synthetic policy PDFs for PolicyRAG."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
except ImportError as exc:  # pragma: no cover - exercised manually during setup
    raise SystemExit(
        "Missing PDF dependency. Run: python -m pip install reportlab"
    ) from exc

from src.config import MOCK_POLICY_DIR
from src.mock_docs import MOCK_POLICIES


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "PolicyTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            alignment=TA_CENTER,
            spaceAfter=14,
            textColor=colors.HexColor("#1F2937"),
        ),
        "subtitle": ParagraphStyle(
            "PolicySubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#4B5563"),
            spaceAfter=14,
        ),
        "section": ParagraphStyle(
            "SectionHeading",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            spaceBefore=12,
            spaceAfter=6,
            textColor=colors.HexColor("#111827"),
        ),
        "body": ParagraphStyle(
            "PolicyBody",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13.5,
            spaceAfter=7,
            textColor=colors.HexColor("#111827"),
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#4B5563"),
        ),
    }


def _footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawString(0.72 * inch, 0.45 * inch, "PolicyRAG synthetic document")
    canvas.drawRightString(7.78 * inch, 0.45 * inch, f"Page {doc.page}")
    canvas.restoreState()


def build_policy_pdf(policy: dict[str, object], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / str(policy["filename"])
    styles = _styles()

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=LETTER,
        rightMargin=0.72 * inch,
        leftMargin=0.72 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.7 * inch,
        title=str(policy["title"]),
        author="PolicyRAG",
        subject="Synthetic policy document",
    )

    metadata = [
        ["Policy ID", str(policy["policy_id"])],
        ["Owner", str(policy["owner"])],
        ["Effective Date", str(policy["effective_date"])],
        ["Review Cycle", str(policy["review_cycle"])],
    ]
    table = Table(metadata, colWidths=[1.35 * inch, 4.9 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111827")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("LEADING", (0, 0), (-1, -1), 11),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    story = [
        Paragraph(str(policy["title"]), styles["title"]),
        Paragraph("Synthetic policy for local retrieval and citation demos", styles["subtitle"]),
        table,
        Spacer(1, 0.18 * inch),
        Paragraph("Document Summary", styles["section"]),
        Paragraph(str(policy["summary"]), styles["body"]),
        Paragraph(
            "This document is fictional and contains no real client, employee, vendor, or confidential enterprise information.",
            styles["small"],
        ),
        Spacer(1, 0.08 * inch),
    ]

    for section_index, section in enumerate(policy["sections"], start=1):
        if section_index == 4:
            story.append(PageBreak())
        story.append(Paragraph(str(section["heading"]), styles["section"]))
        for paragraph in section["paragraphs"]:
            story.append(Paragraph(str(paragraph), styles["body"]))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output_path


def main() -> None:
    generated = [build_policy_pdf(policy, MOCK_POLICY_DIR) for policy in MOCK_POLICIES]
    print(f"Generated {len(generated)} synthetic policy PDFs in {MOCK_POLICY_DIR}")
    for path in generated:
        print(f"- {path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
