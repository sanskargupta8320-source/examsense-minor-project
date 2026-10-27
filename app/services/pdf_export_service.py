import io
import os
import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.services.ai_service import get_topic_deep_dive, generate_model_answers

logger = logging.getLogger("examsense.pdf_export")

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        HRFlowable,
        KeepTogether,
        PageBreak,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("ReportLab not available. PDF export fallback mode.")


FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"


def setup_unicode_fonts():
    """Registers system TrueType fonts supporting Unicode math symbols."""
    global FONT_REGULAR, FONT_BOLD
    if not REPORTLAB_AVAILABLE:
        return

    candidates = [
        ("SegoeUI", "C:/Windows/Fonts/segoeui.ttf", "SegoeUI-Bold", "C:/Windows/Fonts/segoeuib.ttf"),
        ("Arial", "C:/Windows/Fonts/arial.ttf", "Arial-Bold", "C:/Windows/Fonts/arialbd.ttf"),
        ("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans-Bold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("LiberationSans", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "LiberationSans-Bold", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ]
    for reg_name, reg_path, bold_name, bold_path in candidates:
        if os.path.exists(reg_path):
            try:
                pdfmetrics.registerFont(TTFont(reg_name, reg_path))
                if os.path.exists(bold_path):
                    pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                    FONT_BOLD = bold_name
                else:
                    FONT_BOLD = reg_name
                FONT_REGULAR = reg_name
                logger.info(f"ReportLab registered TrueType font: {reg_name}")
                return
            except Exception as e:
                logger.warning(f"Could not register font {reg_name}: {e}")


if REPORTLAB_AVAILABLE:
    setup_unicode_fonts()


if REPORTLAB_AVAILABLE:
    class NumberedCanvas(canvas.Canvas):
        """Two-pass canvas for dynamic total page number and headers/footers."""
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            num_pages = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self.draw_page_number(num_pages)
                super().showPage()
            super().save()

        def draw_page_number(self, page_count):
            self.saveState()
            self.setFont(FONT_REGULAR, 8)
            self.setFillColor(colors.HexColor("#6B7280"))
            self.drawRightString(A4[0] - 36, 18, f"Page {self._pageNumber} of {page_count}")
            self.drawString(36, 18, "ExamSense — Master Study & Solution Guide | For Every Student, Every Exam.")
            self.setStrokeColor(colors.HexColor("#E5E7EB"))
            self.setLineWidth(0.5)
            self.line(36, 28, A4[0] - 36, 28)
            self.restoreState()


def clean_and_format_math_for_pdf(text: str) -> str:
    """
    Parses LaTeX and technical math expressions into clean Unicode notation with
    ReportLab <super> and <sub> tags, safely escaping XML for ReportLab Paragraph.
    """
    if not text:
        return ""
    s = str(text).strip()

    # Common LaTeX replacements
    latex_map = [
        (r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1 / \2)"),
        (r"\\sqrt\{([^{}]+)\}", r"√(\1)"),
        (r"\\sqrt", "√"),
        (r"\\int_\{([^{}]+)\}\^\{([^{}]+)\}", r"∫(\1 to \2)"),
        (r"\\int", "∫"),
        (r"\\sum_\{([^{}]+)\}\^\{([^{}]+)\}", r"∑(\1 to \2)"),
        (r"\\sum", "∑"),
        (r"\\prod", "∏"),
        (r"\\alpha", "α"),
        (r"\\beta", "β"),
        (r"\\gamma", "γ"),
        (r"\\Gamma", "Γ"),
        (r"\\delta", "δ"),
        (r"\\Delta", "Δ"),
        (r"\\theta", "θ"),
        (r"\\lambda", "λ"),
        (r"\\mu", "μ"),
        (r"\\pi", "π"),
        (r"\\sigma", "σ"),
        (r"\\omega", "ω"),
        (r"\\leq", "≤"),
        (r"\\geq", "≥"),
        (r"\\neq", "≠"),
        (r"\\approx", "≈"),
        (r"\\pm", "±"),
        (r"\\times", "×"),
        (r"\\div", "÷"),
        (r"\\cdot", "·"),
        (r"\\infty", "∞"),
        (r"\\rightarrow", "→"),
        (r"\\leftarrow", "←"),
        (r"\\leftrightarrow", "↔"),
        (r"\\Rightarrow", "⇒"),
        (r"\\Leftarrow", "⇐"),
        (r"\\partial", "∂"),
        (r"\\nabla", "∇"),
        (r"\\in", "∈"),
        (r"\\notin", "∉"),
    ]
    for pat, repl in latex_map:
        s = re.sub(pat, repl, s)

    # Strip dollar signs
    s = s.replace("$$", "").replace("$", "")

    # Superscript and Subscript
    s = re.sub(r"\^\{([^{}]+)\}", r"<super>\1</super>", s)
    s = re.sub(r"\^([0-9a-zA-Z\+\-]+)", r"<super>\1</super>", s)
    s = re.sub(r"_\{([^{}]+)\}", r"<sub>\1</sub>", s)
    s = re.sub(r"_([0-9a-zA-Z\+\-]+)", r"<sub>\1</sub>", s)

    # XML Escape while preserving allowed ReportLab tags
    placeholders = []
    def save_tag(m):
        placeholders.append(m.group(0))
        return f"__RLTAG_{len(placeholders)-1}__"

    s = re.sub(r"</?(?:b|i|super|sub|font[^>]*)>", save_tag, s, flags=re.IGNORECASE)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for idx, tag in enumerate(placeholders):
        s = s.replace(f"__RLTAG_{idx}__", tag)

    return s.strip()


def clean_pdf_text(text: str) -> str:
    """Wrapper ensuring math and XML formatting are applied cleanly."""
    return clean_and_format_math_for_pdf(text)


def _build_cheatsheet_story(
    subject_dict: Dict[str, Any],
    topics: List[Dict[str, Any]],
    repeated_questions: List[Dict[str, Any]],
    stats: Dict[str, Any],
    st: Dict[str, Any],
    language: str = "en",
) -> List[Any]:
    """Generates Mode 2: 1-Night Before Exam Ultra-Compact Formula Matrix & Survival Guide."""
    story = []

    # 1. Header Banner
    story.append(Paragraph("ExamSense | 1-Night Before Exam Cheat-Sheet", st["title"]))
    tagline = '<i>"Ultra-Compact Formula Matrix, Key Axioms, and Last-Minute Survival Guide."</i>'
    exam_level = clean_pdf_text(subject_dict.get("exam_type") or "General Examination")
    meta_info = (
        f"<b>Subject:</b> {clean_pdf_text(subject_dict.get('name'))} ({clean_pdf_text(subject_dict.get('code'))}) &nbsp;|&nbsp; "
        f"<b>Exam Level:</b> {exam_level} &nbsp;|&nbsp; "
        f"<b>Date:</b> {datetime.now().strftime('%d %B %Y')}"
    )
    story.append(Paragraph(f"{tagline}<br/>{meta_info}", st["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#D97706"), spaceAfter=8))

    # 2. Executive High-Priority Summary Table
    story.append(Paragraph("<b>1. High-Yield Topic Matrix (Priority Ranking)</b>", st["sub_heading"]))
    top_topics = sorted(topics, key=lambda t: t.get("priority_score", 0), reverse=True)[:8]
    summary_rows = [
        [
            Paragraph("<b>Topic</b>", st["cell_bold"]),
            Paragraph("<b>Priority</b>", st["cell_bold"]),
            Paragraph("<b>Freq</b>", st["cell_bold"]),
            Paragraph("<b>Weightage</b>", st["cell_bold"]),
            Paragraph("<b>Core Focus / Formula Concept</b>", st["cell_bold"]),
        ]
    ]
    for t in top_topics:
        level_color = "#DC2626" if t.get("priority_level") == "High" else "#D97706"
        summary_rows.append([
            Paragraph(f"<b>{clean_pdf_text(t.get('name', ''))}</b>", st["cell_bold"]),
            Paragraph(f"<font color='{level_color}'><b>{t.get('priority_level')}</b></font>", st["cell_bold"]),
            Paragraph(f"{t.get('frequency', 1)}x", st["cell"]),
            Paragraph(f"{t.get('total_marks', 7)}M", st["cell"]),
            Paragraph(clean_pdf_text(f"Key Governing Equations & Laws for {t.get('name', '')}"), st["cell"]),
        ])
    sum_tbl = Table(summary_rows, colWidths=[140, 60, 45, 55, 220])
    sum_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FEF3C7")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#FDE68A")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(sum_tbl)
    story.append(Spacer(1, 8))

    # 3. High-Priority Formula & Principle Cheat Cards
    story.append(Paragraph("<b>2. Ultra-Dense Formula & Axiom Cheat Cards</b>", st["sub_heading"]))
    from app.services.ai_service import get_topic_deep_dive
    for idx, t in enumerate(top_topics[:6]):
        t_name = t.get("name", "")
        dive = get_topic_deep_dive(t_name, subject_dict.get("name", ""), language=language, exam_type=subject_dict.get("exam_type", "General"))
        formulas = dive.get("key_formulas", [])
        if not formulas:
            formulas = [f"Governing Relation for {t_name}", "Standard Formulation: y = f(x) + C"]
        formula_html = "<br/>".join([f"• <b>{clean_pdf_text(f)}</b>" for f in formulas[:3]])

        tips = dive.get("exam_tips", [])
        tips_html = "<br/>".join([f"• {clean_pdf_text(tip)}" for tip in tips[:2]]) if tips else "• State all assumptions clearly and specify SI units."

        card_content = [
            [
                Paragraph(f"<b>#{idx + 1} {clean_pdf_text(t_name)}</b> &nbsp; <font color='#B45309'>[{t.get('priority_level')} | Score: {int(t.get('priority_score', 0))}/100]</font>", st["sub_heading"])
            ],
            [
                Paragraph(f"<b>📐 Key Formulas:</b><br/>{formula_html}", st["formula"])
            ],
            [
                Paragraph(f"<b>💡 Must-Remember Axioms & Pitfalls:</b><br/>{tips_html}", st["tip"])
            ]
        ]
        card_tbl = Table(card_content, colWidths=[520])
        card_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#ECFDF5")),
            ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#FFFBEB")),
            ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#D1D5DB")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(card_tbl)
        story.append(Spacer(1, 5))

    # 4. 10-Point Night-Before Exam Survival Protocol
    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>3. Final Night Exam Survival Protocol (Last 12 Hours)</b>", st["sub_heading"]))
    protocol_points = [
        "☐ <b>1.</b> Review all High-Priority governing equations and sign conventions.",
        "☐ <b>2.</b> Write down SI units for every calculated numerical quantity.",
        "☐ <b>3.</b> Memorize exact diagram labels, circuit symbols, and standard notations.",
        "☐ <b>4.</b> Allocate exam time strictly: 1.5 minutes per mark (e.g. 10 mins for 7-mark question).",
        "☐ <b>5.</b> State all assumptions clearly at the start of derivation/design problems.",
        "☐ <b>6.</b> Double check calculator radian vs degree modes before starting numericals.",
        "☐ <b>7.</b> Pack approved pens, pencils, ruler, eraser, and admit card/hall ticket.",
        "☐ <b>8.</b> Maintain high legibility: underline final numerical values with units.",
        "☐ <b>9.</b> Sleep at least 6-7 hours tonight: memory consolidation is critical for recall.",
        "☐ <b>10.</b> Stay calm: you have revised the highest-probability questions first!",
    ]
    p_rows = []
    for i in range(0, len(protocol_points), 2):
        p_rows.append([
            Paragraph(protocol_points[i], st["cell"]),
            Paragraph(protocol_points[i+1] if i+1 < len(protocol_points) else "", st["cell"]),
        ])
    prot_tbl = Table(p_rows, colWidths=[260, 260])
    prot_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#E5E7EB")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#F3F4F6")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(prot_tbl)

    # 5. Disclaimer Box
    story.append(Spacer(1, 10))
    disclaimer_html = (
        "<b>Academic Disclaimer:</b> This 1-Night Cheat-Sheet provides high-density last-minute revision summary. "
        "Review full textbook notes and verified formulas for comprehensive exam mastery."
    )
    disclaimer_box = Table([[Paragraph(disclaimer_html, st["subtitle"])]], colWidths=[520])
    disclaimer_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#D1D5DB")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(disclaimer_box)

    return story


def _build_mock_paper_story(
    subject_dict: Dict[str, Any],
    topics: List[Dict[str, Any]],
    repeated_questions: List[Dict[str, Any]],
    stats: Dict[str, Any],
    st: Dict[str, Any],
    language: str = "en",
) -> List[Any]:
    """Generates Mode 3: AI Predicted Mock Question Paper (70 Marks) with Official Answer Key."""
    story = []

    # 1. Official Examination Paper Cover Header
    header_data = [
        [Paragraph("<font size=11 color='#1E1B4B'><b>CONFIDENTIAL & PREDICTIVE MODEL EXAMINATION 2024-2025</b></font>", st["sub_heading"])],
        [Paragraph(f"<b>COURSE:</b> {clean_pdf_text(subject_dict.get('name'))} &nbsp;&nbsp;&nbsp;&nbsp; <b>CODE:</b> {clean_pdf_text(subject_dict.get('code'))}", st["body_bold"])],
        [Paragraph(f"<b>EXAMINATION LEVEL:</b> {clean_pdf_text(subject_dict.get('exam_type', 'General'))} &nbsp;&nbsp;|&nbsp;&nbsp; <b>TIME ALLOWED:</b> 3 HOURS &nbsp;&nbsp;|&nbsp;&nbsp; <b>MAX MARKS:</b> 70", st["body"])],
    ]
    hdr_tbl = Table(header_data, colWidths=[520])
    hdr_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF2FF")),
        ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#4338CA")),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(hdr_tbl)
    story.append(Spacer(1, 6))

    # Instructions Box
    instructions_text = (
        "<b>GENERAL INSTRUCTIONS:</b><br/>"
        "1. All sections are compulsory. Internal choices are provided in Section B and Section C.<br/>"
        "2. Section A contains 5 short questions (2 marks each = 10 Marks).<br/>"
        "3. Section B contains 4 descriptive questions (5 marks each = 20 Marks).<br/>"
        "4. Section C contains 4 comprehensive/numerical questions (10 marks each = 40 Marks).<br/>"
        "5. Assume suitable values for any missing data and state them clearly. Non-programmable calculators permitted."
    )
    ins_tbl = Table([[Paragraph(instructions_text, st["cell"])]], colWidths=[520])
    ins_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#D1D5DB")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(ins_tbl)
    story.append(Spacer(1, 8))

    # Gather questions from topics
    all_paper_qs = []
    for t in topics:
        for q in t.get("questions", []):
            all_paper_qs.append(q)

    top_t_names = [t.get("name", "") for t in topics]

    # Section A: 5 Questions (2 Marks each)
    story.append(Paragraph("<b>SECTION A (5 &times; 2 = 10 Marks) — Short Concept Questions</b>", st["sub_heading"]))
    sec_a_qs = []
    for i in range(5):
        t_name = top_t_names[i % len(top_t_names)] if top_t_names else f"Core Concept {i+1}"
        q_text = f"State the fundamental principle governing <b>{t_name}</b> and write its mathematical formulation."
        sec_a_qs.append(q_text)
        story.append(Paragraph(f"<b>Q.{i+1}</b> &nbsp; {clean_pdf_text(q_text)} <font color='#6B7280'>[2 Marks]</font>", st["body"]))
        story.append(Spacer(1, 3))

    story.append(Spacer(1, 6))

    # Section B: 4 Questions (5 Marks each)
    story.append(Paragraph("<b>SECTION B (4 &times; 5 = 20 Marks) — Descriptive & Analytical</b>", st["sub_heading"]))
    sec_b_qs = []
    b_source_qs = [q for q in all_paper_qs if 4 <= q.get("marks", 7) <= 7]
    if len(b_source_qs) < 4:
        b_source_qs = all_paper_qs
    for i in range(4):
        if i < len(b_source_qs):
            q_text = b_source_qs[i].get("question_text", "")
        else:
            t_name = top_t_names[(i+2) % len(top_t_names)] if top_t_names else "High-Yield Topic"
            q_text = f"Explain the operating mechanism, working principle and key assumptions for {t_name} with a neat diagram."
        sec_b_qs.append(q_text)
        story.append(Paragraph(f"<b>Q.{i+6}</b> &nbsp; {clean_pdf_text(q_text)} <font color='#6B7280'>[5 Marks]</font>", st["body"]))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 6))

    # Section C: 4 Questions (10 Marks each) with OR choices
    story.append(Paragraph("<b>SECTION C (4 &times; 10 = 40 Marks) — Comprehensive & Derivations</b>", st["sub_heading"]))
    sec_c_qs = []
    for i in range(4):
        q_num = i + 10
        t_a = top_t_names[(i * 2) % len(top_t_names)] if top_t_names else "High-Yield Topic A"
        t_b = top_t_names[(i * 2 + 1) % len(top_t_names)] if top_t_names else "High-Yield Topic B"
        q_a_text = f"Derive the complete governing equation for <b>{t_a}</b>. State initial conditions, solve for steady-state response, and interpret the physical significance."
        q_b_text = f"Explain the architecture, design considerations, and step-by-step implementation for <b>{t_b}</b> with a numerical example."
        sec_c_qs.append((q_a_text, q_b_text))

        c_box = [
            [Paragraph(f"<b>Q.{q_num}(a)</b> &nbsp; {clean_pdf_text(q_a_text)} <font color='#4338CA'>[10 Marks]</font>", st["body"])],
            [Paragraph("<font color='#6B7280'><b>— OR —</b></font>", st["cell_bold"])],
            [Paragraph(f"<b>Q.{q_num}(b)</b> &nbsp; {clean_pdf_text(q_b_text)} <font color='#4338CA'>[10 Marks]</font>", st["body"])],
        ]
        c_tbl = Table(c_box, colWidths=[520])
        c_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
            ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#E5E7EB")),
            ("ALIGN", (0, 1), (-1, 1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(c_tbl)
        story.append(Spacer(1, 5))

    # PAGE BREAK FOR OFFICIAL ANSWER KEY
    story.append(PageBreak())

    # 2. OFFICIAL AI PREDICTED ANSWER KEY & MARKING SCHEME
    story.append(Paragraph("<b>OFFICIAL AI PREDICTED ANSWER KEY & MARKING SCHEME</b>", st["title"]))
    story.append(Paragraph("<i>Standardized University Evaluation Criteria & Step-by-Step Scoring Guide</i>", st["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#059669"), spaceAfter=8))

    story.append(Paragraph("<b>Answer Key: Section A (Short Concepts)</b>", st["sub_heading"]))
    for i, q_text in enumerate(sec_a_qs):
        story.append(Paragraph(f"<b>Ans Q.{i+1}:</b> <i>Concept:</i> State formal definition accurately with governing equation. <font color='#059669'>[1 Mark for definition, 1 Mark for formula with variables defined]</font>", st["body"]))
        story.append(Spacer(1, 3))

    story.append(Spacer(1, 5))
    story.append(Paragraph("<b>Answer Key: Section B (Descriptive Solutions)</b>", st["sub_heading"]))
    for i, q_text in enumerate(sec_b_qs):
        b_key = (
            f"<b>Ans Q.{i+6}:</b><br/>"
            f"• <b>Step 1 (Principle):</b> State the core operational mechanism. <font color='#059669'>[1 Mark]</font><br/>"
            f"• <b>Step 2 (Diagram / Flow):</b> Labelled schematic diagram or system architecture. <font color='#059669'>[2 Marks]</font><br/>"
            f"• <b>Step 3 (Working & Significance):</b> Analytical derivation / bulleted working. <font color='#059669'>[2 Marks]</font>"
        )
        story.append(Paragraph(b_key, st["body"]))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 5))
    story.append(Paragraph("<b>Answer Key: Section C (Comprehensive Derivations & Mark Distribution)</b>", st["sub_heading"]))
    for i, (q_a, q_b) in enumerate(sec_c_qs):
        c_key = (
            f"<b>Ans Q.{i+10}(a) / (b):</b><br/>"
            f"• <b>Phase 1 (System Modeling & Axioms):</b> Define assumptions, governing laws, and initial boundary parameters. <font color='#059669'>[2.5 Marks]</font><br/>"
            f"• <b>Phase 2 (Mathematical Derivation):</b> Step-by-step algebraic substitution, integration/differentiation, and intermediate cancellation. <font color='#059669'>[4.0 Marks]</font><br/>"
            f"• <b>Phase 3 (Final Expression & Physical Meaning):</b> Final boxed result with correct dimensions, SI units, and edge-case limits. <font color='#059669'>[3.5 Marks]</font>"
        )
        story.append(Paragraph(c_key, st["body"]))
        story.append(Spacer(1, 4))

    # Disclaimer Box
    story.append(Spacer(1, 10))
    disclaimer_html = (
        "<b>Academic Disclaimer:</b> This Predictive Model Examination and Marking Scheme is algorithmically "
        "formulated from historical exam trends to simulate real examination conditions. Master all curriculum topics."
    )
    disclaimer_box = Table([[Paragraph(disclaimer_html, st["subtitle"])]], colWidths=[520])
    disclaimer_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#D1D5DB")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(disclaimer_box)

    return story


def generate_study_plan_pdf(
    subject_dict: Dict[str, Any],
    topics: List[Dict[str, Any]],
    repeated_questions: List[Dict[str, Any]],
    stats: Dict[str, Any],
    suggested_questions: Optional[List[Dict[str, Any]]] = None,
    sections: Optional[List[str]] = None,
    language: str = "en",
    mode: str = "master",
) -> io.BytesIO:
    """
    Generates study materials in 3 distinct smart export modes:
    - Mode 1 ('master'): Comprehensive Multi-Page Master Study & Solution Guide
    - Mode 2 ('cheatsheet'): 1-Night Before Exam Ultra-Compact Formula Matrix & Survival Guide
    - Mode 3 ('mock'): AI Predicted Mock Question Paper (70 Marks) with Official Answer Key
    """
    buffer = io.BytesIO()

    if not REPORTLAB_AVAILABLE:
        text = f"EXAMSENSE STUDY GUIDE ({mode.upper()})\nSubject: {subject_dict.get('name')} ({subject_dict.get('code')})\n"
        text += f"Date: {datetime.now().strftime('%Y-%m-%d')}\n\nTOPICS BY PRIORITY:\n"
        for t in topics:
            text += f"[{t.get('priority_level')}] {t.get('name')} - Score: {t.get('priority_score')}\n"
        buffer.write(text.encode("utf-8"))
        buffer.seek(0)
        return buffer

    # Active sections filter
    active_sections = set(sections) if sections else {"summary", "topics", "repeated", "questions", "plan"}

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=42,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName=FONT_BOLD,
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#4338CA"),
        spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        "DocSubTitle",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#4B5563"),
        spaceAfter=10,
    )
    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName=FONT_BOLD,
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#1E1B4B"),
        spaceBefore=14,
        spaceAfter=6,
    )
    sub_heading = ParagraphStyle(
        "SubHeading",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#312E81"),
        spaceBefore=6,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "BodyStyle",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1F2937"),
    )
    body_bold = ParagraphStyle(
        "BodyBold",
        parent=body_style,
        fontName=FONT_BOLD,
    )
    cell_style = ParagraphStyle(
        "CellNormal",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#1F2937"),
    )
    cell_bold = ParagraphStyle(
        "CellBold",
        parent=cell_style,
        fontName=FONT_BOLD,
    )
    formula_style = ParagraphStyle(
        "FormulaStyle",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#065F46"),
    )
    tip_style = ParagraphStyle(
        "TipStyle",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#92400E"),
    )
    st = {
        "title": title_style,
        "subtitle": subtitle_style,
        "section_heading": section_heading,
        "sub_heading": sub_heading,
        "body": body_style,
        "body_bold": body_bold,
        "cell": cell_style,
        "cell_bold": cell_bold,
        "formula": formula_style,
        "tip": tip_style,
    }

    if mode == "cheatsheet":
        story = _build_cheatsheet_story(subject_dict, topics, repeated_questions, stats, st, language)
        doc.build(story, canvasmaker=NumberedCanvas)
        buffer.seek(0)
        return buffer
    elif mode == "mock":
        story = _build_mock_paper_story(subject_dict, topics, repeated_questions, stats, st, language)
        doc.build(story, canvasmaker=NumberedCanvas)
        buffer.seek(0)
        return buffer

    story = []

    # -----------------------------------------------------------------------
    # 1. Header Banner & Cover
    # -----------------------------------------------------------------------
    story.append(Paragraph("ExamSense | Master Study & Solution Guide", title_style))
    tagline = '<i>"Comprehensive AI-Powered Exam Blueprint, Concept Deep-Dives & Step-by-Step Solutions."</i>'

    exam_level = clean_pdf_text(subject_dict.get("exam_type") or "General Examination")
    source_type = subject_dict.get("source") or ("demo" if subject_dict.get("is_demo") else "papers")
    source_badge = "Based on Uploaded Papers" if source_type == "papers" else ("AI Curriculum Estimate" if source_type == "ai_estimate" else "Sample Demo Data")

    meta_info = (
        f"<b>Subject:</b> {clean_pdf_text(subject_dict.get('name'))} ({clean_pdf_text(subject_dict.get('code'))}) &nbsp;|&nbsp; "
        f"<b>Level:</b> {exam_level} &nbsp;|&nbsp; "
        f"<b>Analysis:</b> {source_badge} &nbsp;|&nbsp; "
        f"<b>Date:</b> {datetime.now().strftime('%d %B %Y')}"
    )
    story.append(Paragraph(f"{tagline}<br/>{meta_info}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#6366F1"), spaceAfter=10))

    # -----------------------------------------------------------------------
    # 2. Executive Dashboard (if "summary" in active_sections)
    # -----------------------------------------------------------------------
    high_topics = [t for t in topics if t.get("priority_level") == "High"]
    med_topics = [t for t in topics if t.get("priority_level") == "Medium"]
    low_topics = [t for t in topics if t.get("priority_level") == "Low"]

    total_q = stats.get("total_questions", sum(len(t.get("questions", [])) for t in topics) or len(topics))
    total_papers = stats.get("total_papers", 1)

    if "summary" in active_sections:
        summary_data = [
            [
                Paragraph("<b>Papers Analyzed</b>", cell_bold),
                Paragraph("<b>Total Questions</b>", cell_bold),
                Paragraph("<b>High Priority Topics</b>", cell_bold),
                Paragraph("<b>Medium Priority</b>", cell_bold),
                Paragraph("<b>Repeated Groups</b>", cell_bold),
            ],
            [
                Paragraph(f"{total_papers} Exam Papers", cell_style),
                Paragraph(f"{total_q} Questions", cell_style),
                Paragraph(f"<font color='#DC2626'><b>{len(high_topics)} Must-Study</b></font>", cell_style),
                Paragraph(f"{len(med_topics)} Important", cell_style),
                Paragraph(f"{len(repeated_questions)} Recurring Groups", cell_style),
            ],
        ]
        summary_table = Table(summary_data, colWidths=[105, 105, 110, 100, 100])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 8))

        # Top 5 Focus Callout Card
        top5 = topics[:5]
        if top5:
            top5_items = "<br/>".join([
                f"• <b>{clean_pdf_text(t.get('name'))}</b> — Score: <b>{t.get('priority_score', 0)}/100</b> [{t.get('priority_level')}] "
                f"({t.get('frequency', 1)}x asked, {t.get('total_marks', 0)} Marks)"
                for t in top5
            ])
            top5_box_html = f"<b>🎯 Core Focus Areas (Highest Predicted Yield):</b><br/>{top5_items}"
            top5_p = Paragraph(top5_box_html, cell_style)
            top5_table = Table([[top5_p]], colWidths=[520])
            top5_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF2FF")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#818CF8")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]))
            story.append(top5_table)
            story.append(Spacer(1, 10))

    # -----------------------------------------------------------------------
    # 3. 7-Day Targeted Revision Schedule (Day-by-Day Table)
    # -----------------------------------------------------------------------
    if "plan" in active_sections and topics:
        story.append(Paragraph("📅 Day-by-Day Targeted Revision Schedule", section_heading))
        story.append(Paragraph("A realistic daily schedule putting high-priority and repeat patterns first.", subtitle_style))

        high_names = [t.get("name") for t in topics if t.get("priority_level") == "High"]
        med_names = [t.get("name") for t in topics if t.get("priority_level") == "Medium"]
        low_names = [t.get("name") for t in topics if t.get("priority_level") == "Low"]

        def _get_items_slice(lst, start, count):
            chunk = lst[start:start + count]
            return ", ".join(chunk) if chunk else "Topic deep dive & practice problems"

        plan_data = [
            [
                Paragraph("<b>Day</b>", cell_bold),
                Paragraph("<b>Focus Category</b>", cell_bold),
                Paragraph("<b>Target Exam Topics</b>", cell_bold),
                Paragraph("<b>Action Items & Target Outcomes</b>", cell_bold),
            ],
            [
                Paragraph("Day 1", cell_bold),
                Paragraph("<font color='#DC2626'><b>High Priority</b></font>", cell_style),
                Paragraph(clean_pdf_text(_get_items_slice(high_names, 0, 2)), cell_style),
                Paragraph("Study core definitions, governing equations, and circuit/flow diagrams.", cell_style),
            ],
            [
                Paragraph("Day 2", cell_bold),
                Paragraph("<font color='#DC2626'><b>High Priority</b></font>", cell_style),
                Paragraph(clean_pdf_text(_get_items_slice(high_names, 2, 2)), cell_style),
                Paragraph("Master recurring question patterns and write out complete mathematical derivations.", cell_style),
            ],
            [
                Paragraph("Day 3", cell_bold),
                Paragraph("<font color='#DC2626'><b>High Priority</b></font>", cell_style),
                Paragraph(clean_pdf_text(_get_items_slice(high_names, 4, 2)), cell_style),
                Paragraph("Practice numerical problems and test yourself on formula recall.", cell_style),
            ],
            [
                Paragraph("Day 4", cell_bold),
                Paragraph("<font color='#D97706'><b>Medium Priority</b></font>", cell_style),
                Paragraph(clean_pdf_text(_get_items_slice(med_names, 0, 2)), cell_style),
                Paragraph("Focus on differences, comparison tables, and architectural trade-offs.", cell_style),
            ],
            [
                Paragraph("Day 5", cell_bold),
                Paragraph("<font color='#D97706'><b>Medium Priority</b></font>", cell_style),
                Paragraph(clean_pdf_text(_get_items_slice(med_names, 2, 2)), cell_style),
                Paragraph("Solve past exam short questions and verify key steps.", cell_style),
            ],
            [
                Paragraph("Day 6", cell_bold),
                Paragraph("<font color='#059669'><b>Low & Notes</b></font>", cell_style),
                Paragraph(clean_pdf_text(_get_items_slice(low_names, 0, 3)), cell_style),
                Paragraph("Skim secondary topics, review handwritten notes, and verify formula cheat sheet.", cell_style),
            ],
            [
                Paragraph("Day 7", cell_bold),
                Paragraph("<b>Full Mock & Review</b>", cell_style),
                Paragraph("All Topics & Formula Bank", cell_style),
                Paragraph("Timed mock exam, full formula review, mental rehearsal, and adequate rest.", cell_style),
            ],
        ]

        plan_table = Table(plan_data, colWidths=[45, 95, 220, 160], repeatRows=1)
        plan_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2FF")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(plan_table)
        story.append(Spacer(1, 14))

    # -----------------------------------------------------------------------
    # SECTION 1: High & Medium Priority Topic Deep-Dives & Concept Explanations
    # -----------------------------------------------------------------------
    if "topics" in active_sections and topics:
        story.append(PageBreak())
        story.append(Paragraph("Section 1: High-Priority Topic Deep-Dives & Concept Explanations", section_heading))
        story.append(Paragraph(
            "Detailed explanations, governing formulas, and high-scoring exam points for every critical topic.",
            subtitle_style,
        ))

        # Focus deep dive on High and Medium topics (or at least top 6 topics)
        deep_topics = [t for t in topics if t.get("priority_level") in ["High", "Medium"]]
        if len(deep_topics) < 4:
            deep_topics = topics[:6]

        subj_name = subject_dict.get("name") or "Subject"

        for idx, t in enumerate(deep_topics):
            t_name = t.get("name", "Topic")
            p_level = t.get("priority_level", "High")
            p_score = t.get("priority_score", 75)
            badge_color = "#DC2626" if p_level == "High" else "#D97706"

            dive_data = get_topic_deep_dive(
                topic_name=t_name,
                subject_name=subj_name,
                language=language,
                exam_type=subject_dict.get("exam_type", "General"),
            )

            explanation = clean_pdf_text(dive_data.get("detailed_explanation", ""))
            formulas = dive_data.get("key_formulas", [])
            tips = dive_data.get("exam_tips", [])

            # Topic Card Header
            topic_header_html = (
                f"<b>{idx + 1}. {clean_pdf_text(t_name)}</b> &nbsp;|&nbsp; "
                f"<font color='{badge_color}'><b>[{p_level} Priority - Score: {p_score}/100]</b></font> &nbsp;|&nbsp; "
                f"Weightage: <b>{t.get('total_marks', 0)} Marks</b> ({t.get('frequency', 1)} appearances)"
            )
            story.append(Paragraph(topic_header_html, sub_heading))

            # Concept Explanation Card
            expl_table = Table([[Paragraph(f"<b>Concept Overview:</b><br/>{explanation}", body_style)]], colWidths=[520])
            expl_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]))
            story.append(expl_table)
            story.append(Spacer(1, 4))

            # Key Formulas / Theorems Callout Box
            if formulas:
                formula_items = "<br/>".join([f"• <b>{clean_pdf_text(f)}</b>" for f in formulas])
                formula_box_html = f"<b>📐 Key Formulas, Theorems & Governing Equations:</b><br/>{formula_items}"
                form_table = Table([[Paragraph(formula_box_html, formula_style)]], colWidths=[520])
                form_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0FDF4")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#86EFAC")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]))
                story.append(form_table)
                story.append(Spacer(1, 4))

            # Exam Tips & Checklist Box
            if tips:
                tip_items = "<br/>".join([f"✓ {clean_pdf_text(tp)}" for tp in tips])
                tip_box_html = f"<b>💡 Important Points to Remember for Full Marks:</b><br/>{tip_items}"
                tip_table = Table([[Paragraph(tip_box_html, tip_style)]], colWidths=[520])
                tip_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFFBEB")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#FCD34D")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]))
                story.append(tip_table)

            story.append(Spacer(1, 10))

    # -----------------------------------------------------------------------
    # SECTION 2: Repeated Question Patterns with Model Answers / Solution Steps
    # -----------------------------------------------------------------------
    if "repeated" in active_sections and repeated_questions:
        story.append(PageBreak())
        story.append(Paragraph("Section 2: Repeated Question Patterns with Model Answers & Solutions", section_heading))
        story.append(Paragraph(
            "Every question pattern that appeared across multiple examination cycles, paired with an AI step-by-step solution guide.",
            subtitle_style,
        ))

        # UNTRUNCATED: print ALL repeated questions
        for idx, rq in enumerate(repeated_questions):
            q_text = rq.get("canonical_question", "").strip()
            years_list = rq.get("years", [])
            years_str = ", ".join(str(y) for y in years_list)
            score = rq.get("similarity_score", 85)
            r_count = rq.get("repeat_count", len(years_list) or 2)

            # Generate structured step-by-step model answer
            topic_guess = rq.get("unit_or_topic_guess") or "Core Examination Concept"
            model_ans = generate_model_answers(
                question_text=q_text,
                topic_name=topic_guess,
                subject_name=subject_dict.get("name", "Subject"),
                language=language,
            )

            # Question Header
            q_header = (
                f"<b>Pattern #{idx + 1}:</b> {clean_pdf_text(q_text)}<br/>"
                f"<font color='#4338CA'><b>Frequency:</b> Appeared {r_count}x across cycles ({years_str}) &nbsp;|&nbsp; "
                f"<b>Semantic Match:</b> {score}% &nbsp;|&nbsp; <b>Marks:</b> {rq.get('marks', 7)}M</font>"
            )
            story.append(Paragraph(q_header, sub_heading))

            # Solution Steps & Formula Card
            steps_list = model_ans.get("step_by_step_solution", [])
            steps_html = "<br/>".join([clean_pdf_text(s) for s in steps_list])
            key_f = clean_pdf_text(model_ans.get("key_formula", ""))
            tip = clean_pdf_text(model_ans.get("examiner_tip", ""))

            solution_card_content = (
                f"<b>Governing Formula / Principle:</b> {key_f}<br/><br/>"
                f"<b>Step-by-Step Model Answer:</b><br/>{steps_html}<br/><br/>"
                f"<b>Examiner Tip:</b> {tip}"
            )
            sol_table = Table([[Paragraph(solution_card_content, cell_style)]], colWidths=[520])
            sol_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF3C7")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#F59E0B")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]))
            story.append(sol_table)
            story.append(Spacer(1, 10))

    # -----------------------------------------------------------------------
    # SECTION 3: Complete Topic-Wise Question Bank (100% UNTRUNCATED)
    # -----------------------------------------------------------------------
    if "questions" in active_sections and topics:
        story.append(PageBreak())
        story.append(Paragraph("Section 3: Complete Topic-Wise Question Bank (100% Untruncated)", section_heading))
        story.append(Paragraph(
            "Every single past paper question and suggested note question, categorized topic-by-topic without truncation. Use checkboxes to track your preparation.",
            subtitle_style,
        ))

        # Collect past questions topic-by-topic
        for t in topics:
            t_name = t.get("name", "Topic")
            t_qs = t.get("questions", [])
            t_level = t.get("priority_level", "Medium")
            badge_color = "#DC2626" if t_level == "High" else ("#D97706" if t_level == "Medium" else "#059669")

            if not t_qs:
                continue

            story.append(Paragraph(
                f"<b>{clean_pdf_text(t_name)}</b> &nbsp;<font color='{badge_color}'><b>[{t_level}]</b></font> "
                f"({len(t_qs)} Questions, Total {t.get('total_marks', 0)} Marks)",
                sub_heading,
            ))

            q_rows = [
                [
                    Paragraph("<b>Done</b>", cell_bold),
                    Paragraph("<b>Complete Question Text (Untruncated)</b>", cell_bold),
                    Paragraph("<b>Marks</b>", cell_bold),
                    Paragraph("<b>Year</b>", cell_bold),
                ]
            ]

            # UNTRUNCATED: print every question in full
            for q in t_qs:
                q_text = clean_pdf_text(q.get("question_text", ""))
                q_marks = q.get("marks", 7)
                q_year = q.get("year", 2023)

                q_rows.append([
                    Paragraph("☐", cell_bold),
                    Paragraph(q_text, cell_style),
                    Paragraph(f"{q_marks}M", cell_style),
                    Paragraph(str(q_year), cell_style),
                ])

            t_table = Table(q_rows, colWidths=[35, 410, 40, 35], repeatRows=1)
            t_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(t_table)
            story.append(Spacer(1, 8))

        # Suggested Questions from Notes (if available)
        if suggested_questions:
            story.append(Spacer(1, 8))
            story.append(Paragraph("<b>Suggested Practice Questions Extracted from Notes:</b>", sub_heading))
            sq_rows = [
                [
                    Paragraph("<b>Done</b>", cell_bold),
                    Paragraph("<b>Suggested Question</b>", cell_bold),
                    Paragraph("<b>Topic</b>", cell_bold),
                    Paragraph("<b>Marks</b>", cell_bold),
                ]
            ]
            for sq in suggested_questions:
                sq_rows.append([
                    Paragraph("☐", cell_bold),
                    Paragraph(clean_pdf_text(sq.get("question_text", "")), cell_style),
                    Paragraph(clean_pdf_text(sq.get("topic_name", "Notes")), cell_style),
                    Paragraph(f"{sq.get('expected_marks', 5)}M", cell_style),
                ])
            sq_table = Table(sq_rows, colWidths=[35, 345, 100, 40], repeatRows=1)
            sq_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2FF")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E7FF")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(sq_table)

    # -----------------------------------------------------------------------
    # Disclaimer Box
    # -----------------------------------------------------------------------
    story.append(Spacer(1, 12))
    disclaimer_html = (
        "<b>Academic Disclaimer:</b> This Master Study & Solution Guide is algorithmically synthesized "
        "from historical examination papers and mathematical frequency analysis. "
        "It is designed to maximize student preparation efficiency and revision clarity. "
        "It is not an official examination board guarantee. Master all concepts thoroughly."
    )
    disclaimer_p = Paragraph(disclaimer_html, subtitle_style)
    disclaimer_box = Table([[disclaimer_p]], colWidths=[520])
    disclaimer_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#D1D5DB")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(disclaimer_box)

    # Build Document with NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer
