"""Generate branded PDF digest: Daily Intelligence Report.

Professional layout following real-world intelligence report conventions:
- Cover page with branding
- Executive summary with statistics dashboard
- Top findings at-a-glance table
- Section deep-dives with card-style finding blocks
- Appendix with source citations
- Branded header/footer on every page
"""

import io
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
    KeepTogether,
)

from app.config import get_settings
from app.schemas.finding import FindingOut

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Color palette — corporate navy/blue theme
# ---------------------------------------------------------------------------
NAVY = colors.HexColor("#0F172A")
DARK_BLUE = colors.HexColor("#1E3A5F")
ACCENT_BLUE = colors.HexColor("#2563EB")
LIGHT_BLUE = colors.HexColor("#DBEAFE")
PALE_BLUE = colors.HexColor("#EFF6FF")
SLATE_700 = colors.HexColor("#334155")
SLATE_500 = colors.HexColor("#64748B")
SLATE_400 = colors.HexColor("#94A3B8")
GRAY_100 = colors.HexColor("#F1F5F9")
GRAY_200 = colors.HexColor("#E2E8F0")
GRAY_50 = colors.HexColor("#F8FAFC")
WHITE = colors.white
GREEN = colors.HexColor("#16A34A")
AMBER = colors.HexColor("#D97706")
RED = colors.HexColor("#DC2626")

SECTION_TITLES = {
    "release": "Releases & Provider Updates",
    "research": "Research Publications",
    "benchmark": "Benchmarks & Leaderboards",
    "other": "Other Notable Updates",
}

SECTION_ICONS = {
    "release": "\u25b6",
    "research": "\u25c6",
    "benchmark": "\u25a0",
    "other": "\u25cf",
}

CATEGORY_COLORS = {
    "release": ACCENT_BLUE,
    "research": colors.HexColor("#7C3AED"),
    "benchmark": colors.HexColor("#0891B2"),
    "other": SLATE_500,
}

PAGE_W, PAGE_H = letter
MARGIN_L = 0.85 * inch
MARGIN_R = 0.85 * inch
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R


def _hex(color) -> str:
    """Convert a ReportLab color to #RRGGBB string for use in Paragraph HTML."""
    if hasattr(color, "hexval"):
        hv = color.hexval()
        if hv.startswith("0x"):
            return "#" + hv[2:].upper()
        return hv
    return "#64748B"


def _confidence_label(conf: float) -> str:
    if conf >= 0.85:
        return "Very High"
    if conf >= 0.70:
        return "High"
    if conf >= 0.55:
        return "Moderate"
    if conf >= 0.40:
        return "Low"
    return "Very Low"


def _confidence_color(conf: float) -> colors.HexColor:
    if conf >= 0.70:
        return GREEN
    if conf >= 0.50:
        return AMBER
    return RED


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
def _build_styles():
    s = {}

    s["cover_title"] = ParagraphStyle(
        "CoverTitle",
        fontName="Helvetica-Bold",
        fontSize=32,
        leading=38,
        textColor=NAVY,
        alignment=TA_CENTER,
        spaceAfter=4,
    )
    s["cover_subtitle"] = ParagraphStyle(
        "CoverSubtitle",
        fontName="Helvetica",
        fontSize=14,
        leading=20,
        textColor=SLATE_500,
        alignment=TA_CENTER,
        spaceAfter=2,
    )
    s["cover_date"] = ParagraphStyle(
        "CoverDate",
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=18,
        textColor=ACCENT_BLUE,
        alignment=TA_CENTER,
        spaceAfter=4,
    )
    s["cover_meta"] = ParagraphStyle(
        "CoverMeta",
        fontName="Helvetica",
        fontSize=10,
        leading=15,
        textColor=SLATE_400,
        alignment=TA_CENTER,
        spaceAfter=2,
    )

    s["h1"] = ParagraphStyle(
        "H1",
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=26,
        textColor=NAVY,
        spaceAfter=10,
        spaceBefore=4,
    )
    s["h2"] = ParagraphStyle(
        "H2",
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=22,
        textColor=DARK_BLUE,
        spaceAfter=8,
        spaceBefore=14,
    )
    s["h3"] = ParagraphStyle(
        "H3",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=NAVY,
        spaceAfter=4,
        spaceBefore=2,
    )

    s["body"] = ParagraphStyle(
        "Body",
        fontName="Helvetica",
        fontSize=10,
        leading=14.5,
        textColor=SLATE_700,
        spaceAfter=6,
    )
    s["body_sm"] = ParagraphStyle(
        "BodySmall",
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=SLATE_500,
        spaceAfter=3,
    )
    s["label"] = ParagraphStyle(
        "Label",
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=SLATE_500,
        spaceAfter=2,
    )
    s["meta"] = ParagraphStyle(
        "Meta",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=SLATE_400,
        spaceAfter=2,
    )
    s["link"] = ParagraphStyle(
        "Link",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=ACCENT_BLUE,
        spaceAfter=2,
    )
    s["evidence"] = ParagraphStyle(
        "Evidence",
        fontName="Helvetica-Oblique",
        fontSize=9,
        leading=13,
        textColor=SLATE_500,
        leftIndent=12,
        borderPadding=4,
        spaceAfter=4,
    )
    s["tag"] = ParagraphStyle(
        "Tag",
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=ACCENT_BLUE,
        spaceAfter=2,
    )
    s["stat_value"] = ParagraphStyle(
        "StatValue",
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=ACCENT_BLUE,
        alignment=TA_CENTER,
    )
    s["stat_label"] = ParagraphStyle(
        "StatLabel",
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=SLATE_500,
        alignment=TA_CENTER,
    )
    s["table_header"] = ParagraphStyle(
        "TblHeader",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=WHITE,
    )
    s["table_cell"] = ParagraphStyle(
        "TblCell",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=SLATE_700,
    )
    s["table_cell_bold"] = ParagraphStyle(
        "TblCellBold",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=12,
        textColor=NAVY,
    )
    s["footer_text"] = ParagraphStyle(
        "FooterText",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=SLATE_500,
        alignment=TA_CENTER,
    )
    return s


# ---------------------------------------------------------------------------
# Header / Footer
# ---------------------------------------------------------------------------
def _header_footer(canvas, doc, date_str: str, total_findings: int):
    canvas.saveState()

    # Header line
    canvas.setStrokeColor(ACCENT_BLUE)
    canvas.setLineWidth(1.5)
    canvas.line(MARGIN_L, PAGE_H - 0.52 * inch, PAGE_W - MARGIN_R, PAGE_H - 0.52 * inch)

    canvas.setFont("Helvetica-Bold", 8.5)
    canvas.setFillColor(NAVY)
    canvas.drawString(MARGIN_L, PAGE_H - 0.46 * inch, "FRONTIER AI RADAR")

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(SLATE_400)
    canvas.drawRightString(
        PAGE_W - MARGIN_R,
        PAGE_H - 0.46 * inch,
        f"Daily Intelligence Digest  |  {date_str}",
    )

    # Footer
    canvas.setStrokeColor(GRAY_200)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_L, 0.55 * inch, PAGE_W - MARGIN_R, 0.55 * inch)

    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(SLATE_400)
    canvas.drawString(
        MARGIN_L,
        0.38 * inch,
        f"Frontier AI Radar — {total_findings} findings  |  Confidential",
    )
    canvas.drawRightString(PAGE_W - MARGIN_R, 0.38 * inch, f"Page {doc.page}")

    canvas.restoreState()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _accent_rule():
    return HRFlowable(
        width="100%", thickness=1.5, color=ACCENT_BLUE, spaceAfter=8, spaceBefore=4
    )


def _light_rule():
    return HRFlowable(
        width="100%", thickness=0.5, color=GRAY_200, spaceAfter=6, spaceBefore=6
    )


def _stat_cell(value: str, label: str, styles):
    return Table(
        [
            [Paragraph(value, styles["stat_value"])],
            [Paragraph(label, styles["stat_label"])],
        ],
        colWidths=[1.4 * inch],
        rowHeights=[30, 16],
        style=TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        ),
    )


def _category_badge(category: str, styles) -> Paragraph:
    cat_color = CATEGORY_COLORS.get(category, SLATE_500)
    return Paragraph(
        f'<font color="{_hex(cat_color)}"><b>{category.upper()}</b></font>',
        styles["meta"],
    )


# ---------------------------------------------------------------------------
# PDF Generator
# ---------------------------------------------------------------------------
class PDFGenerator:
    """Render professional Daily Frontier AI Radar Digest."""

    def __init__(self):
        self.settings = get_settings()
        self.storage = Path(self.settings.local_storage_path)
        self.storage.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        run_id: int,
        report_date: datetime,
        executive_summary: str,
        what_changed: str,
        why_it_matters: str,
        findings_by_section: dict[str, List[FindingOut]],
        top_findings: Optional[List[FindingOut]] = None,
        sota_findings: Optional[List[FindingOut]] = None,
    ) -> str:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            rightMargin=MARGIN_R,
            leftMargin=MARGIN_L,
            topMargin=0.7 * inch,
            bottomMargin=0.7 * inch,
        )
        st = _build_styles()

        date_display = report_date.strftime("%B %d, %Y")
        date_header = report_date.strftime("%Y-%m-%d")

        all_findings: List[FindingOut] = []
        for key in ("release", "research", "benchmark", "other"):
            all_findings.extend(findings_by_section.get(key) or [])
        total = len(all_findings)
        top = top_findings or []

        n_release = len(findings_by_section.get("release") or [])
        n_research = len(findings_by_section.get("research") or [])
        n_benchmark = len(findings_by_section.get("benchmark") or [])
        n_other = len(findings_by_section.get("other") or [])

        flow: list = []

        # =====================================================================
        # COVER PAGE
        # =====================================================================
        flow.append(Spacer(1, 1.8 * inch))
        flow.append(
            HRFlowable(
                width="40%",
                thickness=2.5,
                color=ACCENT_BLUE,
                spaceAfter=16,
                spaceBefore=0,
            )
        )
        flow.append(Paragraph("FRONTIER AI RADAR", st["cover_title"]))
        flow.append(Spacer(1, 0.08 * inch))
        flow.append(Paragraph("Daily Intelligence Digest", st["cover_subtitle"]))
        flow.append(Spacer(1, 0.35 * inch))
        flow.append(
            HRFlowable(
                width="20%", thickness=1, color=GRAY_200, spaceAfter=14, spaceBefore=0
            )
        )
        flow.append(Paragraph(date_display, st["cover_date"]))
        flow.append(Spacer(1, 0.5 * inch))
        flow.append(Paragraph(f"{total} findings  |  Run #{run_id}", st["cover_meta"]))
        flow.append(
            Paragraph("Generated by Multi-Agent Intelligence System", st["cover_meta"])
        )
        flow.append(
            Paragraph(
                "Audience: Research, Product &amp; Strategy Teams", st["cover_meta"]
            )
        )
        flow.append(PageBreak())

        # =====================================================================
        # EXECUTIVE SUMMARY
        # =====================================================================
        flow.append(Paragraph("Executive Summary", st["h1"]))
        flow.append(_accent_rule())

        # --- Statistics bar ---
        stats_data = [
            [
                _stat_cell(str(total), "TOTAL FINDINGS", st),
                _stat_cell(str(n_release), "RELEASES", st),
                _stat_cell(str(n_research), "RESEARCH", st),
                _stat_cell(str(n_benchmark), "BENCHMARKS", st),
                _stat_cell(str(n_other), "OTHER", st),
            ]
        ]
        stats_table = Table(stats_data, colWidths=[CONTENT_W / 5] * 5)
        stats_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                    ("BOX", (0, 0), (-1, -1), 0.5, LIGHT_BLUE),
                    ("LINEAFTER", (0, 0), (-2, -1), 0.5, LIGHT_BLUE),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        flow.append(stats_table)
        flow.append(Spacer(1, 0.25 * inch))

        # --- Top findings table ---
        if top:
            flow.append(Paragraph("Top Findings at a Glance", st["h3"]))
            flow.append(Spacer(1, 0.08 * inch))
            hdr = [
                Paragraph("#", st["table_header"]),
                Paragraph("Finding", st["table_header"]),
                Paragraph("Source", st["table_header"]),
                Paragraph("Type", st["table_header"]),
                Paragraph("Confidence", st["table_header"]),
            ]
            rows = [hdr]
            for i, fo in enumerate(top[:7], 1):
                src_url = str(fo.source_url)
                pub = fo.publisher or "—"
                conf_hex = _hex(_confidence_color(fo.confidence))
                rows.append(
                    [
                        Paragraph(str(i), st["table_cell"]),
                        Paragraph(f"<b>{fo.title}</b>", st["table_cell_bold"]),
                        Paragraph(
                            f'<a href="{src_url}" color="#2563EB">{pub}</a>',
                            st["table_cell"],
                        ),
                        _category_badge(fo.category, st),
                        Paragraph(
                            f'<font color="{conf_hex}"><b>{fo.confidence:.0%}</b></font> {_confidence_label(fo.confidence)}',
                            st["table_cell"],
                        ),
                    ]
                )
            col_w = [0.28 * inch, 2.6 * inch, 1.3 * inch, 0.8 * inch, 1.22 * inch]
            tbl = Table(rows, colWidths=col_w, repeatRows=1)
            tbl.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), DARK_BLUE),
                        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, GRAY_50]),
                        ("GRID", (0, 0), (-1, -1), 0.4, GRAY_200),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 5),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            flow.append(tbl)
            flow.append(Spacer(1, 0.25 * inch))

        # --- Narrative summary ---
        if executive_summary and executive_summary != "No new updates today.":
            for line in executive_summary.split("\n"):
                line = line.strip()
                if not line:
                    continue
                flow.append(Paragraph(line, st["body"]))
            flow.append(Spacer(1, 0.15 * inch))

        # --- What changed / Why it matters ---
        if what_changed:
            flow.append(Paragraph("What Changed Since Yesterday", st["h3"]))
            flow.append(Paragraph(what_changed, st["body"]))
            flow.append(Spacer(1, 0.1 * inch))

        if why_it_matters:
            flow.append(Paragraph("Why It Matters", st["h3"]))
            flow.append(Paragraph(why_it_matters, st["body"]))

        flow.append(PageBreak())

        # =====================================================================
        # SECTION DEEP DIVES
        # =====================================================================
        for section_key in ("release", "research", "benchmark", "other"):
            findings = findings_by_section.get(section_key) or []
            if not findings:
                continue

            section_title = SECTION_TITLES.get(section_key, section_key.title())
            icon = SECTION_ICONS.get(section_key, "\u25cf")
            cat_color = CATEGORY_COLORS.get(section_key, SLATE_500)
            cat_hex = _hex(cat_color)

            flow.append(
                Paragraph(
                    f'<font color="{cat_hex}">{icon}</font>  {section_title}  '
                    f'<font color="#94A3B8" size="11">({len(findings)} finding{"s" if len(findings) != 1 else ""})</font>',
                    st["h1"],
                )
            )
            flow.append(
                HRFlowable(
                    width="100%",
                    thickness=2,
                    color=cat_color,
                    spaceAfter=12,
                    spaceBefore=2,
                )
            )

            for idx, f in enumerate(findings[:50]):
                card = self._build_finding_card(f, idx + 1, st, section_key)
                flow.append(KeepTogether(card))
                flow.append(Spacer(1, 0.06 * inch))

            flow.append(PageBreak())

        # =====================================================================
        # SOTA WATCH
        # =====================================================================
        if sota_findings:
            flow.append(Paragraph("SOTA Watch", st["h1"]))
            flow.append(_accent_rule())
            flow.append(
                Paragraph(
                    f"{len(sota_findings)} finding(s) in this run claim state-of-the-art results.",
                    st["body_sm"],
                )
            )
            flow.append(Spacer(1, 0.12 * inch))
            for si, sf in enumerate(sota_findings, 1):
                sf_url = str(sf.source_url)
                ent_str = ", ".join((sf.entities or [])[:5]) or "—"
                sota_block = [
                    Paragraph(
                        f'<font color="#0F172A"><b>{si}. {sf.title}</b></font>  '
                        f'<font color="#94A3B8" size="8">[{sf.category}]</font>',
                        st["body_sm"],
                    ),
                    Paragraph(
                        f'<font color="#64748B">Entity: {ent_str}  |  '
                        f'Confidence: {sf.confidence:.2f}  |  '
                        f'SOTA Confidence: {(sf.sota_confidence or 0):.2f}</font>',
                        st["meta"],
                    ),
                    Paragraph(
                        f'<a href="{sf_url}" color="#2563EB">{sf_url}</a>',
                        st["meta"],
                    ),
                    _light_rule(),
                ]
                flow.append(KeepTogether(sota_block))
            flow.append(PageBreak())

        # =====================================================================
        # APPENDIX
        # =====================================================================
        flow.append(Paragraph("Appendix — Sources &amp; Evidence", st["h1"]))
        flow.append(_accent_rule())
        flow.append(
            Paragraph(
                f"Complete reference list of {total} findings with source links and supporting evidence.",
                st["body_sm"],
            )
        )
        flow.append(Spacer(1, 0.15 * inch))

        for idx, f in enumerate(all_findings[:100], 1):
            f_url = str(f.source_url)
            evidence = f.evidence or f.summary_short or ""
            ref_block = [
                Paragraph(
                    f'<font color="#0F172A"><b>{idx}. {f.title}</b></font>  '
                    f'<font color="#94A3B8" size="8">[{f.category}]</font>',
                    st["body_sm"],
                ),
                Paragraph(
                    f'<a href="{f_url}" color="#2563EB">{f_url}</a>',
                    st["meta"],
                ),
            ]
            if evidence:
                ref_block.append(Paragraph(f'<i>"{evidence}"</i>', st["evidence"]))
            ref_block.append(_light_rule())
            flow.append(KeepTogether(ref_block))

        # --- Final footer ---
        flow.append(Spacer(1, 0.3 * inch))
        flow.append(
            HRFlowable(
                width="30%", thickness=1, color=GRAY_200, spaceAfter=10, spaceBefore=0
            )
        )
        flow.append(
            Paragraph(
                f"Generated by Frontier AI Radar  |  {total} findings  |  {date_display}",
                st["footer_text"],
            )
        )

        # Build
        def on_page(canvas, doc_ref):
            _header_footer(canvas, doc_ref, date_header, total)

        doc.build(flow, onFirstPage=on_page, onLaterPages=on_page)

        buf.seek(0)
        filename = (
            f"frontier_ai_radar_{report_date.strftime('%Y_%m_%d')}_run{run_id}.pdf"
        )
        path = self.storage / filename
        path.write_bytes(buf.read())
        try:
            if path.resolve().is_relative_to(Path.cwd().resolve()):
                return str(path.relative_to(Path.cwd()))
        except (ValueError, OSError):
            pass
        return str(self.storage / filename)

    def _build_finding_card(
        self,
        f: FindingOut,
        num: int,
        st: dict,
        section_key: str,
    ) -> list:
        """Build a visually distinct card block for a single finding."""
        elements = []
        f_url = str(f.source_url)
        cat_color = CATEGORY_COLORS.get(section_key, SLATE_500)
        cat_hex = _hex(cat_color)
        conf_hex = _hex(_confidence_color(f.confidence))

        # --- Card top: colored left-border via a small table ---
        title_para = Paragraph(f"<b>{f.title}</b>", st["h3"])
        meta_parts = []
        if f.publisher:
            meta_parts.append(f"<b>Source:</b> {f.publisher}")
        meta_parts.append(
            f'<b>Confidence:</b> <font color="{conf_hex}">{f.confidence:.0%} ({_confidence_label(f.confidence)})</font>'
        )
        meta_parts.append(f'<font color="{cat_hex}"><b>{f.category.upper()}</b></font>')
        meta_line = Paragraph("  |  ".join(meta_parts), st["meta"])

        header_content = Table(
            [[title_para], [meta_line]],
            colWidths=[CONTENT_W - 0.15 * inch],
            style=TableStyle(
                [
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ]
            ),
        )

        card_table = Table(
            [[header_content]],
            colWidths=[CONTENT_W],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), GRAY_50),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.5, GRAY_200),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ]
            ),
        )
        elements.append(card_table)
        elements.append(Spacer(1, 0.04 * inch))

        # --- Summary ---
        if f.summary_short:
            elements.append(Paragraph(f.summary_short, st["body"]))

        # --- What changed (summary_long) ---
        if f.summary_long:
            elements.append(Spacer(1, 0.03 * inch))
            elements.append(Paragraph("<b>Details</b>", st["label"]))
            long_text = (
                f.summary_long
                if isinstance(f.summary_long, str)
                else str(f.summary_long)
            )
            for line in long_text.split("\n"):
                line = line.strip()
                if line:
                    elements.append(Paragraph(line, st["body_sm"]))

        # --- Why it matters ---
        if f.why_it_matters:
            elements.append(Spacer(1, 0.03 * inch))
            elements.append(Paragraph("<b>Why It Matters</b>", st["label"]))
            elements.append(Paragraph(f.why_it_matters, st["body"]))

        # --- Evidence ---
        if f.evidence:
            elements.append(Spacer(1, 0.03 * inch))
            elements.append(Paragraph("<b>Evidence</b>", st["label"]))
            elements.append(Paragraph(f'<i>"{f.evidence}"</i>', st["evidence"]))

        # --- Tags & entities row ---
        tag_parts = []
        if f.tags:
            tags_str = ", ".join(f.tags[:12])
            tag_parts.append(f"<b>Tags:</b> {tags_str}")
        if f.entities:
            ent_str = ", ".join(f.entities[:12])
            tag_parts.append(f"<b>Entities:</b> {ent_str}")
        if tag_parts:
            elements.append(Spacer(1, 0.02 * inch))
            elements.append(Paragraph("  |  ".join(tag_parts), st["meta"]))

        # --- Source link ---
        elements.append(Spacer(1, 0.02 * inch))
        elements.append(
            Paragraph(
                f'<a href="{f_url}" color="#2563EB">{f_url}</a>',
                st["link"],
            )
        )

        # --- Card bottom divider ---
        elements.append(Spacer(1, 0.06 * inch))
        elements.append(_light_rule())

        return elements
