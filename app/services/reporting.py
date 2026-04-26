"""PDF report generation for ReportRx analytics."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.analytics import build_analytics_summary, get_view_label

MAX_REPORT_TABLE_ROWS = 10


def _make_pie(path: Path, title: str, items: List[Dict[str, int | str]]) -> None:
    labels = [str(item["name"]) for item in items]
    counts = [int(item["count"]) for item in items]

    fig, ax = plt.subplots(figsize=(8.4, 3.8), dpi=180)
    if counts:
        ax.pie(counts, startangle=90, counterclock=False)
        ax.legend(
            labels,
            loc="lower center",
            bbox_to_anchor=(0.5, -0.10),
            ncol=min(4, max(1, len(labels))),
            frameon=False,
            fontsize=9,
        )
    else:
        ax.text(0.5, 0.5, "No data available", ha="center", va="center", fontsize=12)
    ax.set_title(title, fontsize=14, pad=10)
    ax.axis("equal")
    fig.tight_layout(rect=[0.02, 0.05, 0.98, 0.95])
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _make_association_bar(path: Path, items: List[Dict[str, int | str]]) -> None:
    labels = [str(item["drug_name"]) for item in items]
    counts = [int(item["count"]) for item in items]

    fig, ax = plt.subplots(figsize=(8.4, 3.8), dpi=180)
    if counts:
        bars = ax.bar(labels, counts, color="#2563eb")
        ax.set_ylim(0, max(counts) + 1)
        ax.grid(axis="y", alpha=0.35)
        ax.set_title("Top Drug-ADR Association", fontsize=14, pad=10)
        ax.set_ylabel("Count", fontsize=10)
        ax.tick_params(axis="x", rotation=15, labelsize=9)
        for bar, item in zip(bars, items):
            ax.text(
                bar.get_x() + (bar.get_width() / 2),
                bar.get_height() + 0.05,
                str(item["top_adr"]),
                ha="center",
                va="bottom",
                fontsize=8,
                rotation=18,
            )
    else:
        ax.text(0.5, 0.5, "No data available", ha="center", va="center", fontsize=12)
        ax.set_title("Top Drug-ADR Association", fontsize=14, pad=10)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.tight_layout(rect=[0.02, 0.05, 0.98, 0.95])
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _header_footer(canvas, doc) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor("#D7D7D7"))
    canvas.setLineWidth(0.5)
    canvas.line(0.65 * inch, height - 0.55 * inch, width - 0.65 * inch, height - 0.55 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawString(0.65 * inch, 0.45 * inch, "ReportRx | Analytics Report")
    canvas.drawRightString(width - 0.65 * inch, 0.45 * inch, f"Page {doc.page}")
    canvas.restoreState()


def _build_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="AppTitle",
            parent=styles["Title"],
            fontSize=25,
            leading=29,
            alignment=1,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Subtitle",
            parent=styles["Normal"],
            fontSize=12,
            leading=15,
            alignment=1,
            textColor=colors.HexColor("#475569"),
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Generated",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            alignment=1,
            textColor=colors.HexColor("#64748b"),
            spaceAfter=16,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            fontSize=14,
            leading=18,
            alignment=1,
            spaceBefore=4,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Small",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Summary",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            alignment=0,
        )
    )
    return styles


def _summary_box(styles, summary: Dict) -> Table:
    rows = [
        ["Current View", summary["view_label"]],
        ["Reports Included", str(summary["filtered_report_count"])],
        ["Generated On", datetime.now().strftime("%B %d, %Y %I:%M %p")],
    ]
    wrapped = [[Paragraph(f"<b>{label}</b>", styles["Summary"]), Paragraph(value, styles["Summary"])] for label, value in rows]
    table = Table(wrapped, colWidths=[1.8 * inch, 4.6 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#1e3a8a")),
                ("INNERGRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eff6ff")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def _section(styles, chart_path: Path, table_title: str, columns: List[str], rows: List[List[str]], col_widths: List[float]) -> List:
    story: List = []
    story.append(Image(str(chart_path), width=7.15 * inch, height=3.15 * inch))
    story.append(Spacer(1, 0.22 * inch))
    story.append(Paragraph(table_title, styles["SectionTitle"]))

    merged_rows = [[Paragraph(f"<b>{col}</b>", styles["Small"]) for col in columns] + [Paragraph("<b>NOTES</b>", styles["Small"])]]
    for row in rows:
        merged_rows.append([Paragraph(str(cell), styles["Small"]) for cell in row] + [""])

    notes_width = 1.6 * inch
    table = Table(merged_rows, colWidths=col_widths + [notes_width], repeatRows=1)

    table_style = [
        ("BOX", (0, 0), (-1, -1), 0.7, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("ALIGN", (1, 1), (len(columns) - 1, -1), "CENTER"),
        ("INNERGRID", (0, 0), (len(columns) - 1, -1), 0.45, colors.black),
        ("LINEBEFORE", (len(columns), 0), (len(columns), -1), 0.7, colors.black),
        ("SPAN", (len(columns), 1), (len(columns), len(merged_rows) - 1)),
        ("VALIGN", (len(columns), 1), (len(columns), len(merged_rows) - 1), "TOP"),
    ]

    table.setStyle(TableStyle(table_style))
    story.append(table)
    return story


def build_analytics_report_pdf(view: str) -> bytes:
    summary = build_analytics_summary(view)
    if not summary["has_data"]:
        raise ValueError(f'No analytics data available for the "{get_view_label(view)}" view.')

    styles = _build_styles()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        medicine_pie = tmp_path / "medicines.png"
        association_bar = tmp_path / "associations.png"
        reaction_pie = tmp_path / "reactions.png"

        _make_pie(medicine_pie, "Top Medicines Detected", summary["medicine_chart"])
        _make_association_bar(association_bar, summary["association_chart"])
        _make_pie(reaction_pie, "Top ADR Symptoms Detected", summary["reaction_chart"])

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=0.65 * inch,
            leftMargin=0.65 * inch,
            topMargin=0.72 * inch,
            bottomMargin=0.65 * inch,
        )

        story: List = []

        def title_block() -> None:
            story.append(Paragraph("ReportRx", styles["AppTitle"]))
            story.append(Paragraph("Analytics Report", styles["Subtitle"]))
            story.append(Paragraph(f'Current View: {summary["view_label"]}', styles["Subtitle"]))
            story.append(Paragraph(f'Generated on: {datetime.now().strftime("%B %d, %Y %I:%M %p")}', styles["Generated"]))

        title_block()
        story.append(_summary_box(styles, summary))
        story.append(Spacer(1, 0.28 * inch))
        story.extend(
            _section(
                styles,
                medicine_pie,
                "Top Medicines",
                ["Drug Name", "Count"],
                [
                    [item["name"], str(item["count"])]
                    for item in summary["medicine_table"][:MAX_REPORT_TABLE_ROWS]
                ],
                [3.55 * inch, 1.0 * inch],
            )
        )
        story.append(PageBreak())

        title_block()
        story.extend(
            _section(
                styles,
                association_bar,
                "Top Drug-ADR Association",
                ["Drug Name", "Top ADR", "Count"],
                [
                    [item["drug_name"], item["top_adr"], str(item["count"])]
                    for item in summary["association_table"][:MAX_REPORT_TABLE_ROWS]
                ],
                [1.55 * inch, 2.15 * inch, 0.8 * inch],
            )
        )
        story.append(PageBreak())

        title_block()
        story.extend(
            _section(
                styles,
                reaction_pie,
                "Top ADR Symptoms",
                ["ADR Name", "Count"],
                [
                    [item["name"], str(item["count"])]
                    for item in summary["reaction_table"][:MAX_REPORT_TABLE_ROWS]
                ],
                [3.55 * inch, 1.0 * inch],
            )
        )

        doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
        return buffer.getvalue()
