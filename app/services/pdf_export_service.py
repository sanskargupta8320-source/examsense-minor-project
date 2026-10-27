import io
import logging
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger("examsense.pdf_export")

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        HRFlowable,
        KeepTogether,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("ReportLab not available. PDF export fallback mode.")


def generate_study_plan_pdf(
    subject_dict: Dict[str, Any],
    topics: List[Dict[str, Any]],
    repeated_questions: List[Dict[str, Any]],
    stats: Dict[str, Any],
) -> io.BytesIO:
    """
    Generates a high-quality, professional ExamSense Study Plan PDF.
    
    Includes:
    - Subject details & Exam preparation summary
    - Prioritized Topic Study Matrix (High / Medium / Low) with action items
    - Verified Repeated Questions across examination cycles
    - Viva and Exam scoring strategies
    """
    buffer = io.BytesIO()

    if not REPORTLAB_AVAILABLE:
        # Fallback text buffer if ReportLab is not ready
        text = f"EXAMSENSE STUDY PLAN\nSubject: {subject_dict.get('name')} ({subject_dict.get('code')})\n"
        text += f"Date: {datetime.now().strftime('%Y-%m-%d')}\n\nTOPICS BY PRIORITY:\n"
        for t in topics:
            text += f"[{t.get('priority_level')}] {t.get('name')} - Score: {t.get('priority_score')} - Freq: {t.get('frequency')}x\n"
        buffer.write(text.encode("utf-8"))
        buffer.seek(0)
        return buffer

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#4F46E5"),  # Indigo
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        "DocSubTitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#4B5563"),  # Gray-600
        spaceAfter=12,
    )

    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#1E1B4B"),  # Deep Indigo
        spaceBefore=14,
        spaceAfter=8,
    )

    cell_style = ParagraphStyle(
        "CellNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#1F2937"),
    )

    cell_bold = ParagraphStyle(
        "CellBold",
        parent=cell_style,
        fontName="Helvetica-Bold",
    )

    story = []

    # 1. Header Banner
    story.append(Paragraph("ExamSense | AI Exam Intelligence", title_style))
    tagline = '<i>"Kya padhna hai, ab AI batayega."</i>'
    meta_info = f"<b>Subject:</b> {subject_dict.get('name')} ({subject_dict.get('code')}) &nbsp;|&nbsp; <b>Generated:</b> {datetime.now().strftime('%d %B %Y')}"
    story.append(Paragraph(f"{tagline}<br/>{meta_info}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#6366F1"), spaceAfter=14))

    # 2. Executive Summary Metrics
    high_count = sum(1 for t in topics if t.get("priority_level") == "High")
    med_count = sum(1 for t in topics if t.get("priority_level") == "Medium")
    low_count = sum(1 for t in topics if t.get("priority_level") == "Low")
    total_q = stats.get("total_questions", len(topics))
    total_papers = stats.get("total_papers", 4)

    summary_data = [
        [
            Paragraph("<b>Analyzed Papers</b>", cell_bold),
            Paragraph("<b>Total Questions</b>", cell_bold),
            Paragraph("<b>High Priority Topics</b>", cell_bold),
            Paragraph("<b>Medium Priority</b>", cell_bold),
            Paragraph("<b>Repeated Groups</b>", cell_bold),
        ],
        [
            Paragraph(f"{total_papers} Exam Cycles", cell_style),
            Paragraph(f"{total_q} Questions", cell_style),
            Paragraph(f"<font color='#DC2626'><b>{high_count} Topics (Must Study)</b></font>", cell_style),
            Paragraph(f"{med_count} Topics", cell_style),
            Paragraph(f"{len(repeated_questions)} Recurring Patterns", cell_style),
        ],
    ]
    summary_table = Table(summary_data, colWidths=[105, 105, 110, 100, 100])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F4F6")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 14))

    # 3. Prioritized Topic Table
    story.append(Paragraph("1. High-Yield Topic Priority Matrix", section_heading))
    
    topic_table_data = [
        [
            Paragraph("<b>Priority</b>", cell_bold),
            Paragraph("<b>Topic Name</b>", cell_bold),
            Paragraph("<b>Frequency</b>", cell_bold),
            Paragraph("<b>Total Marks</b>", cell_bold),
            Paragraph("<b>Years Asked</b>", cell_bold),
            Paragraph("<b>Score</b>", cell_bold),
        ]
    ]

    for t in topics:
        plevel = t.get("priority_level", "Medium")
        color_code = "#DC2626" if plevel == "High" else ("#D97706" if plevel == "Medium" else "#059669")
        years_str = ", ".join(str(y) for y in t.get("years_asked", []))

        topic_table_data.append([
            Paragraph(f"<font color='{color_code}'><b>{plevel}</b></font>", cell_style),
            Paragraph(t.get("name", ""), cell_style),
            Paragraph(f"{t.get('frequency', 0)} times", cell_style),
            Paragraph(f"{t.get('total_marks', 0)}M", cell_style),
            Paragraph(years_str, cell_style),
            Paragraph(f"<b>{t.get('priority_score', 0)}/100</b>", cell_style),
        ])

    topic_table = Table(topic_table_data, colWidths=[65, 195, 65, 65, 75, 55])
    topic_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2FF")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(topic_table)
    story.append(Spacer(1, 14))

    # 4. Repeated Questions Section
    if repeated_questions:
        story.append(Paragraph("2. Verified Recurring & Duplicate Questions (TF-IDF Similarity)", section_heading))
        story.append(Paragraph(
            "These questions have repeated across university exam years with high semantic similarity. Memorize these first!",
            subtitle_style,
        ))

        rep_data = [
            [
                Paragraph("<b>#</b>", cell_bold),
                Paragraph("<b>Recurring Question Pattern</b>", cell_bold),
                Paragraph("<b>Years</b>", cell_bold),
                Paragraph("<b>Match</b>", cell_bold),
            ]
        ]

        for i, rq in enumerate(repeated_questions[:8]):
            years_str = ", ".join(str(y) for y in rq.get("years", []))
            rep_data.append([
                Paragraph(str(i + 1), cell_style),
                Paragraph(rq.get("canonical_question", ""), cell_style),
                Paragraph(years_str, cell_style),
                Paragraph(f"{rq.get('similarity_score', 85)}%", cell_style),
            ])

        rep_table = Table(rep_data, colWidths=[25, 360, 75, 60])
        rep_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FEF3C7")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#FDE68A")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(rep_table)
        story.append(Spacer(1, 14))

    # 5. Exam Strategy & Disclaimer Box
    disclaimer_html = (
        "<b>Exam Preparation Strategy:</b><br/>"
        "1. Complete all <b>High Priority</b> topics first — they account for ~60% of question paper weightage.<br/>"
        "2. Prepare neat diagrams and standard definitions for the <b>Repeated Questions</b>.<br/>"
        "3. <i>Disclaimer:</i> This study plan is algorithmically generated based on past examination frequencies and mathematical trend analysis. It is designed to maximize revision efficiency and does not constitute an official university paper leak."
    )
    disclaimer_p = Paragraph(disclaimer_html, subtitle_style)
    disclaimer_box = Table([[disclaimer_p]], colWidths=[520])
    disclaimer_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#D1D5DB")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(disclaimer_box)

    # Build Document
    doc.build(story)
    buffer.seek(0)
    return buffer
