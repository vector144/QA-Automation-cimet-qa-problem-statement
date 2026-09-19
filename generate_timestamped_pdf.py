"""
generate_timestamped_pdf.py
Generates an official PDF version of the sales call transcript enriched with
sequential audio timestamps for every speaker turn.
"""

from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas
from database.seed import parse_raw_transcript

_ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPT_TXT = _ROOT / "transcript_content.txt"
OUTPUT_PDF = _ROOT / "call-transcript-with-timestamps.pdf"

# Realistic unredacted test data mapping
REDACTION_MAP = {
    "[CUSTOMER_NAME]": "Margaret",
    "[CUSTOMER_FULL_NAME]": "Margaret Jenkins",
    "[AGENT_NAME]": "Marcus Vance",
    "[PROVIDER_A]": "Dodo NBN",
    "[SERVICE_ADDRESS]": "14/28 Riverview Road, Parramatta NSW 2150",
    "[DELIVERY_ADDRESS]": "Unit 14, 28 Riverview Road, Parramatta NSW 2150",
    "[STREET_NAME]": "Riverview Road",
    "[RESIDENTIAL_COMPLEX]": "Riverview Gardens complex",
    "[PHONE]": "0412 345 678",
    "[EMAIL]": "margaret.jenkins48@gmail.com",
    "[DOB]": "14/08/1958",
    "[ACCOUNT_NUMBER]": "982347102",
    "[OTP_CODE]": "482910",
    "[REFERENCE_NUMBER]": "REF-7892341",
    "[UNCLEAR_NAME]": "Parramatta",
}


def unredact_text(text: str) -> str:
    for tag, replacement in REDACTION_MAP.items():
        text = text.replace(tag, replacement)
    # Clean up artifacts like 'De-identified - contains placeholder tags...'
    text = text.replace("De-identified - contains placeholder tags in place of personal information", "")
    return text.strip()


class NumberedCanvas(canvas.Canvas):
    """Adds running headers and footers with total page count."""
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
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 750, "CIMET QA AUTOMATION — UNREDACTED SALES CALL TRANSCRIPT (WITH TIMESTAMPS)")
            self.drawRightString(558, 750, "CONFIDENTIAL AUDIT")
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.5)
            self.line(54, 744, 558, 744)

        # Footer
        self.setFont("Helvetica", 8)
        self.drawString(54, 36, "CIMET QA Compliance Verification Engine • Outbound Sales Call")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 36, page_str)
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(54, 48, 558, 48)
        self.restoreState()


def format_time(ms: int) -> str:
    secs = int(ms // 1000)
    mins = secs // 60
    rem_secs = secs % 60
    return f"{mins:02d}:{rem_secs:02d}"


import json
import sqlite3
from typing import Optional

def generate_lead_pdf(lead_id: str = "lead-cimet-real-01", output_path: Optional[Path] = None) -> Path:
    """
    Generates a timestamped PDF transcript for the given lead_id using data from SQLite.
    """
    db_path = _ROOT / "backend" / "cimet.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
    lead_row = cur.fetchone()

    cur.execute("SELECT * FROM transcripts WHERE lead_id = ?", (lead_id,))
    trans_row = cur.fetchone()
    conn.close()

    if not lead_row:
        raise ValueError(f"Lead '{lead_id}' not found")

    crm_fields = json.loads(lead_row["crm_fields"]) if lead_row["crm_fields"] else {}
    turns = json.loads(trans_row["turns"]) if (trans_row and trans_row["turns"]) else []

    target_pdf = output_path or (_ROOT / f"transcript-{lead_id}.pdf")

    doc = SimpleDocTemplate(
        str(target_pdf),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#475569"),
    )
    badge_style = ParagraphStyle(
        "Badge",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#dc2626") if lead_row["gate_status"] == "FAILED" else colors.HexColor("#059669"),
    )
    h2_style = ParagraphStyle(
        "Heading2",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=10,
        spaceAfter=4,
    )
    speaker_agent_style = ParagraphStyle(
        "SpeakerAgent",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1e40af"),
    )
    speaker_cust_style = ParagraphStyle(
        "SpeakerCust",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#047857"),
    )
    dialogue_style = ParagraphStyle(
        "Dialogue",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1e293b"),
    )
    legend_key_style = ParagraphStyle(
        "LegendKey",
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9,
        textColor=colors.HexColor("#0f172a"),
    )
    legend_val_style = ParagraphStyle(
        "LegendVal",
        fontName="Helvetica",
        fontSize=7.5,
        leading=9,
        textColor=colors.HexColor("#334155"),
    )

    story = []

    # Title & Metadata Header
    cust_name = crm_fields.get("customer_full_name") or crm_fields.get("customer_name") or "Customer"
    retailer = lead_row["retailer_name"] or lead_row["retailer_id"]
    agent_name = lead_row["agent_name"] or lead_row["agent_id"] or "Agent"
    call_date = lead_row["call_date"]
    gate_status = lead_row["gate_status"]

    story.append(Paragraph(f"Sales Call Transcript: {cust_name} ({retailer})", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>LEAD ID:</b> {lead_id} • <b>GATE STATUS:</b> {gate_status} • <b>AGENT:</b> {agent_name}", badge_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"Official compliance transcript with verified speech timestamps — Call Date: {call_date}", subtitle_style))
    story.append(Spacer(1, 8))

    # Meta Info Table
    last_end = turns[-1]["end_ms"] if turns else 0
    meta_data = [
        [
            Paragraph(f"<b>Retailer:</b> {retailer}", legend_val_style),
            Paragraph(f"<b>Customer:</b> {cust_name}", legend_val_style),
            Paragraph(f"<b>Total Turns:</b> {len(turns)}", legend_val_style),
        ],
        [
            Paragraph(f"<b>Duration:</b> {format_time(last_end)} ({int(last_end/1000)}s)", legend_val_style),
            Paragraph(f"<b>Agent:</b> {agent_name}", legend_val_style),
            Paragraph("<b>PCI-DSS Status:</b> Redacted / Muted", legend_val_style),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[170, 160, 174])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # CRM Source-of-Truth Table
    story.append(Paragraph("CRM Ground Truth Record (Expected Values)", h2_style))
    crm_items = list(crm_fields.items())
    crm_rows = [
        [Paragraph("CRM Field", legend_key_style), Paragraph("Ground Truth Value", legend_key_style),
         Paragraph("CRM Field", legend_key_style), Paragraph("Ground Truth Value", legend_key_style)]
    ]
    for i in range(0, len(crm_items), 2):
        k1, v1 = crm_items[i]
        k2, v2 = crm_items[i+1] if i+1 < len(crm_items) else ("", "")
        crm_rows.append([
            Paragraph(str(k1), legend_key_style), Paragraph(str(v1), legend_val_style),
            Paragraph(str(k2), legend_key_style), Paragraph(str(v2), legend_val_style),
        ])
    crm_table = Table(crm_rows, colWidths=[120, 132, 120, 132])
    crm_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#f1f5f9")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(crm_table)
    story.append(Spacer(1, 10))

    # Dialogue Section
    story.append(Paragraph("Timestamped Dialogue Transcript", h2_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceBefore=2, spaceAfter=6))

    for t in turns:
        start_t = format_time(t.get("start_ms", 0))
        end_t = format_time(t.get("end_ms", 0))
        idx = t.get("turn_index", 0)
        speaker = t.get("speaker", "Speaker")
        raw_text = t.get("text", "")
        text = unredact_text(raw_text)

        is_agent = (speaker.lower() == "agent")
        speaker_label_style = speaker_agent_style if is_agent else speaker_cust_style
        speaker_title = f"[{start_t} - {end_t}] Turn #{idx} — {speaker} ({agent_name if is_agent else cust_name})"

        row_data = [
            [Paragraph(speaker_title, speaker_label_style)],
            [Paragraph(text, dialogue_style)],
        ]
        t_block = Table(row_data, colWidths=[504])
        bg_color = colors.HexColor("#f8fafc") if is_agent else colors.HexColor("#f0fdf4")
        border_color = colors.HexColor("#cbd5e1") if is_agent else colors.HexColor("#86efac")

        t_block.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg_color),
            ("BOX", (0, 0), (-1, -1), 0.5, border_color),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ]))

        story.append(t_block)
        story.append(Spacer(1, 3))

    doc.build(story, canvasmaker=NumberedCanvas)
    return target_pdf


def build_pdf():
    return generate_lead_pdf("lead-cimet-real-01", OUTPUT_PDF)


if __name__ == "__main__":
    build_pdf()

