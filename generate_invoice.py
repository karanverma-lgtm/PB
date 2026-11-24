import os
import sys
import hashlib

# Fix for Python 3.8 hashlib.md5 'usedforsecurity' compatibility in reportlab
_orig_md5 = hashlib.md5
def _patched_md5(*args, **kwargs):
    kwargs.pop("usedforsecurity", None)
    return _orig_md5(*args, **kwargs)
hashlib.md5 = _patched_md5

from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import fitz  # PyMuPDF to convert PDF to image for visual preview

def generate_invoice(pdf_path="Invoice_StockmightyBot.pdf"):
    # 612 x 792 pt letter
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=30,
        rightMargin=30,
        topMargin=26,
        bottomMargin=26
    )

    styles = getSampleStyleSheet()

    brand_style = ParagraphStyle(
        'BrandTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0F172A')
    )
    
    invoice_title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        alignment=2,
        textColor=colors.HexColor('#2563EB')
    )

    sub_right_style = ParagraphStyle(
        'SubRight',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        alignment=2,
        textColor=colors.HexColor('#64748B')
    )

    h3_style = ParagraphStyle(
        'H3Style',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#334155')
    )

    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11.5,
        textColor=colors.HexColor('#1E293B')
    )

    body_bold = ParagraphStyle(
        'BodyBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor('#0F172A')
    )

    th_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    )

    td_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.8,
        leading=10.5,
        textColor=colors.HexColor('#1E293B')
    )

    td_right = ParagraphStyle(
        'TableCellRight',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        alignment=2,
        textColor=colors.HexColor('#1E293B')
    )

    td_right_bold = ParagraphStyle(
        'TableCellRightBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        alignment=2,
        textColor=colors.HexColor('#0F172A')
    )

    story = []

    # 1. Header Table: Left Brand / Right INVOICE details
    header_data = [
        [
            Paragraph("<b>StockMighty</b> Automation", brand_style),
            Paragraph("INVOICE", invoice_title_style)
        ],
        [
            Paragraph("<font color='#64748B'>E-Commerce Price Intelligence & Real-Time Alert Systems</font>", body_style),
            Paragraph("<b>Invoice #:</b> INV-2026-1101 &nbsp;|&nbsp; <b>Date:</b> Nov 20, 2026<br/><b>Due Date:</b> Nov 27, 2026 &nbsp;|&nbsp; <b>Status:</b> <font color='#2563EB'><b>PAYMENT DUE</b></font>", sub_right_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[3.2 * inch, 4.45 * inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))

    # Divider line
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=8, spaceBefore=0))

    # 2. Billed By / Billed To Section
    billing_data = [
        [
            Paragraph("<b>PROVIDER / DEVELOPER:</b>", h3_style),
            Paragraph("<b>CLIENT / BILL TO:</b>", h3_style)
        ],
        [
            Paragraph(
                "<b>Karan Verma</b><br/>"
                "Full-Stack Python & Cloud Automation Engineering<br/>"
                "Telegram: @karanverma_dev &nbsp;|&nbsp; Location: India",
                body_style
            ),
            Paragraph(
                "<b>Daisha Electronic</b><br/>"
                "Project: <b>Price Drop & Stock Alert Bot (@Stockmightybot)</b><br/>"
                "Platform: Telegram Cloud Bot &nbsp;|&nbsp; Environment: Production (Railway)",
                body_style
            )
        ]
    ]
    billing_table = Table(billing_data, colWidths=[3.82 * inch, 3.83 * inch])
    billing_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(billing_table)
    story.append(Spacer(1, 10))

    # 3. Line Items Table
    headers = [
        Paragraph("Service / Scope Description", th_style),
        Paragraph("Category", th_style),
        Paragraph("Qty", th_style),
        Paragraph("Rate (INR)", th_style),
        Paragraph("Amount (INR)", th_style)
    ]

    items = [
        [
            Paragraph(
                "<b>Multi-Platform Price Drop & Stock Tracking Bot — Development & Deployment</b><br/>"
                "<font color='#64748B'>• Scraper engine supporting 6 major platforms: Amazon, Flipkart, JioMart, Reliance Digital, Croma & Samsung.<br/>"
                "• Dual-layer anti-bot architecture: curl_cffi browser TLS impersonation + Camoufox stealth browser.<br/>"
                "• Localized delivery PIN code price & availability detection.<br/>"
                "• Persistent SQLite database with WAL mode on persistent Railway volume.</font>",
                td_style
            ),
            Paragraph("Setup & Dev", td_style),
            Paragraph("1 Project", td_style),
            Paragraph("Rs. 15,000", td_right),
            Paragraph("Rs. 15,000", td_right_bold)
        ],
        [
            Paragraph(
                "<b>Cloud Server Hosting & 24/7 Monitoring Infrastructure (Month 1)</b><br/>"
                "<font color='#64748B'>• Containerized Linux environment hosted on Railway cloud infrastructure.<br/>"
                "• Automated background scheduler polling tracked items every 4 hours.<br/>"
                "• High-availability uptime guarantee (99.9%) and daily database state persistence.</font>",
                td_style
            ),
            Paragraph("Cloud Hosting", td_style),
            Paragraph("1 Month", td_style),
            Paragraph("Rs. 1,500", td_right),
            Paragraph("Rs. 1,500", td_right_bold)
        ],
        [
            Paragraph(
                "<b>E-Commerce Scraper Maintenance & Bot Defense Updates (Month 1 Retainer)</b><br/>"
                "<font color='#64748B'>• Ongoing DOM/HTML layout updates across supported platforms.<br/>"
                "• Anti-bot protection & WAF bypass maintenance.<br/>"
                "• Priority 24-hour turnaround for scraper repairs & Telegram bot enhancements.</font>",
                td_style
            ),
            Paragraph("Maintenance SLA", td_style),
            Paragraph("1 Month", td_style),
            Paragraph("Rs. 3,499", td_right),
            Paragraph("Rs. 3,499", td_right_bold)
        ]
    ]

    table_data = [headers] + items

    items_table = Table(table_data, colWidths=[3.65 * inch, 1.1 * inch, 0.65 * inch, 1.05 * inch, 1.2 * inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 10))

    # 4. Summary & Project Scope Block
    summary_data = [
        [Paragraph("Subtotal:", body_bold), Paragraph("Rs. 19,999.00", td_right)],
        [Paragraph("Initial Package Discount:", body_style), Paragraph("<font color='#16A34A'><b>- Rs. 2,999.00</b></font>", td_right)],
        [Paragraph("Taxes (0% - Direct Freelance):", body_style), Paragraph("Rs. 0.00", td_right)],
        [Paragraph("<b>TOTAL AMOUNT DUE:</b>", ParagraphStyle('TotP', fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#2563EB'))),
         Paragraph("<b>Rs. 17,000.00</b>", ParagraphStyle('TotV', fontName='Helvetica-Bold', fontSize=11, alignment=2, textColor=colors.HexColor('#2563EB')))],
        [Paragraph("<font color='#64748B'>Subsequent Monthly Retainer:</font>", body_style), Paragraph("<font color='#64748B'><b>Rs. 4,999.00 / mo</b></font>", td_right)]
    ]
    summary_table = Table(summary_data, colWidths=[2.1 * inch, 1.65 * inch])
    summary_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEABOVE', (0, 3), (-1, 3), 1, colors.HexColor('#2563EB')),
        ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#EFF6FF')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
    ]))

    notes_info = [
        [Paragraph("<b>PROJECT NOTES & DELIVERABLES</b>", h3_style)],
        [Paragraph(
            "• <b>Live Deployment:</b> Automated 24/7 background container running on Railway.<br/>"
            "• <b>Delivery PIN Integration:</b> Real-time localized stock & price evaluation.<br/>"
            "• <b>Dual Anti-Bot Engine:</b> TLS fingerprint spoofing + Camoufox stealth browser.<br/>"
            "• <b>Supported Platforms:</b> Amazon, Flipkart, JioMart, Reliance Digital, Croma & Samsung.<br/>"
            "<i>Invoice issued to Daisha Electronic. Thank you for your business!</i>",
            body_style
        )]
    ]
    notes_table = Table(notes_info, colWidths=[3.75 * inch])
    notes_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
    ]))

    bottom_block = Table([[notes_table, summary_table]], colWidths=[3.85 * inch, 3.8 * inch])
    bottom_block.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(bottom_block)
    story.append(Spacer(1, 10))

    # 5. Terms & Signature Footer
    terms_text = (
        "<b>Terms of Service & Retainer Agreement:</b><br/>"
        "1. Monthly maintenance covers 24/7 continuous cloud execution, Railway container hosting, and automated database backups.<br/>"
        "2. E-commerce platforms frequently update their code; scraper updates and anti-bot patches are resolved within 24–48 hours of detection.<br/>"
        "3. Recurring monthly maintenance invoice (Rs. 4,999/mo) begins on the 20th of each following calendar month.<br/>"
        "<b>Thank you for your business!</b>"
    )
    story.append(Paragraph(terms_text, ParagraphStyle('Terms', fontName='Helvetica', fontSize=7.2, leading=9.5, textColor=colors.HexColor('#64748B'))))

    doc.build(story)
    print(f"✅ Invoice PDF successfully generated at: {pdf_path}")

    # Render first page as PNG for visual check
    doc_fitz = fitz.open(pdf_path)
    print(f"📄 Page count: {len(doc_fitz)}")
    page = doc_fitz[0]
    pix = page.get_pixmap(dpi=150)
    img_path = pdf_path.replace(".pdf", "_preview.png")
    pix.save(img_path)
    print(f"✅ Preview image generated at: {img_path}")


def generate_monthly_recurring_invoice(pdf_path="Invoice_Monthly_Retainer.pdf", month_name="December 2026", amount=4999.0):
    """Generate a clean, professional monthly recurring invoice."""
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=30,
        rightMargin=30,
        topMargin=26,
        bottomMargin=26
    )

    styles = getSampleStyleSheet()

    brand_style = ParagraphStyle(
        'BrandTitle', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=20, leading=24, textColor=colors.HexColor('#0F172A')
    )
    invoice_title_style = ParagraphStyle(
        'InvoiceTitle', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=22, leading=26, alignment=2, textColor=colors.HexColor('#2563EB')
    )
    sub_right_style = ParagraphStyle(
        'SubRight', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8.5, leading=12, alignment=2, textColor=colors.HexColor('#64748B')
    )
    h3_style = ParagraphStyle(
        'H3Style', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.HexColor('#334155')
    )
    body_style = ParagraphStyle(
        'Body', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8, leading=11.5, textColor=colors.HexColor('#1E293B')
    )
    body_bold = ParagraphStyle(
        'BodyBold', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=8.5, leading=11.5, textColor=colors.HexColor('#0F172A')
    )
    th_style = ParagraphStyle(
        'TableHeader', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=colors.white
    )
    td_style = ParagraphStyle(
        'TableCell', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor('#1E293B')
    )
    td_right = ParagraphStyle(
        'TableCellRight', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8, leading=11, alignment=2, textColor=colors.HexColor('#1E293B')
    )
    td_right_bold = ParagraphStyle(
        'TableCellRightBold', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=2, textColor=colors.HexColor('#0F172A')
    )

    story = []

    # 1. Header Table
    header_data = [
        [
            Paragraph("<b>StockMighty</b> Automation", brand_style),
            Paragraph("MONTHLY INVOICE", invoice_title_style)
        ],
        [
            Paragraph("<font color='#64748B'>E-Commerce Price Intelligence & Real-Time Alert Systems</font>", body_style),
            Paragraph(f"<b>Invoice #:</b> INV-M-2026-12 &nbsp;|&nbsp; <b>Billing Period:</b> {month_name}<br/><b>Due Date:</b> Dec 05, 2026 &nbsp;|&nbsp; <b>Status:</b> <font color='#2563EB'><b>PAYMENT DUE</b></font>", sub_right_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[3.2 * inch, 4.45 * inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))

    # Divider line
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=8, spaceBefore=0))

    # 2. Billed By / Billed To Section
    billing_data = [
        [
            Paragraph("<b>PROVIDER / DEVELOPER:</b>", h3_style),
            Paragraph("<b>CLIENT / BILL TO:</b>", h3_style)
        ],
        [
            Paragraph(
                "<b>Karan Verma</b><br/>"
                "Full-Stack Python & Cloud Automation Engineering<br/>"
                "Telegram: @karanverma_dev &nbsp;|&nbsp; Location: India",
                body_style
            ),
            Paragraph(
                "<b>Daisha Electronic</b><br/>"
                "Project: <b>Price Drop & Stock Alert Bot (@Stockmightybot)</b><br/>"
                "Platform: Telegram Cloud Bot &nbsp;|&nbsp; Environment: Production (Railway)",
                body_style
            )
        ]
    ]
    billing_table = Table(billing_data, colWidths=[3.82 * inch, 3.83 * inch])
    billing_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(billing_table)
    story.append(Spacer(1, 10))

    # 3. Line Items Table
    headers = [
        Paragraph("Service / Subscription Details", th_style),
        Paragraph("Period", th_style),
        Paragraph("Qty", th_style),
        Paragraph("Rate (INR)", th_style),
        Paragraph("Amount (INR)", th_style)
    ]

    items = [
        [
            Paragraph(
                f"<b>Monthly Dedicated Cloud Server Hosting & Storage ({month_name})</b><br/>"
                "<font color='#64748B'>• 24/7 continuous Railway container execution with persistent SQLite WAL volume.<br/>"
                "• Automated background scheduler monitoring tracked products every 4 hours.<br/>"
                "• 99.9% uptime SLA & automated failure recovery.</font>",
                td_style
            ),
            Paragraph(month_name, td_style),
            Paragraph("1 Month", td_style),
            Paragraph("Rs. 1,500.00", td_right),
            Paragraph("Rs. 1,500.00", td_right_bold)
        ],
        [
            Paragraph(
                f"<b>Scraper Health, Anti-Bot Bypasses & Platform SLA Retainer ({month_name})</b><br/>"
                "<font color='#64748B'>• Continuous monitoring & updates for 6 e-commerce scrapers (Amazon, Flipkart, JioMart, Reliance Digital, Croma, Samsung).<br/>"
                "• Anti-bot engine maintenance (Cloudflare, WAF, TLS JA4 fingerprint updates).<br/>"
                "• Guaranteed 24-hour turnaround on scraper patch updates.</font>",
                td_style
            ),
            Paragraph(month_name, td_style),
            Paragraph("1 Month", td_style),
            Paragraph("Rs. 3,499.00", td_right),
            Paragraph("Rs. 3,499.00", td_right_bold)
        ]
    ]

    table_data = [headers] + items
    items_table = Table(table_data, colWidths=[3.65 * inch, 1.1 * inch, 0.65 * inch, 1.05 * inch, 1.2 * inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 12))

    # 4. Summary & Payment Block
    summary_data = [
        [Paragraph("Subtotal:", body_bold), Paragraph(f"Rs. {amount:,.2f}", td_right)],
        [Paragraph("Taxes (0% - Direct Freelance):", body_style), Paragraph("Rs. 0.00", td_right)],
        [Paragraph("<b>TOTAL AMOUNT DUE:</b>", ParagraphStyle('TotP', fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor('#2563EB'))),
         Paragraph(f"<b>Rs. {amount:,.2f}</b>", ParagraphStyle('TotV', fontName='Helvetica-Bold', fontSize=11, alignment=2, textColor=colors.HexColor('#2563EB')))],
        [Paragraph("<font color='#64748B'>Renewal Cycle:</font>", body_style), Paragraph("<font color='#64748B'>Monthly (Net 7)</font>", td_right)]
    ]
    summary_table = Table(summary_data, colWidths=[2.1 * inch, 1.65 * inch])
    summary_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEABOVE', (0, 2), (-1, 2), 1, colors.HexColor('#2563EB')),
        ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#EFF6FF')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
    ]))

    notes_info = [
        [Paragraph("<b>MONTHLY SERVICE & SLA SUMMARY</b>", h3_style)],
        [Paragraph(
            "• <b>Infrastructure:</b> 24/7 dedicated container runtime with persistent SQLite volume.<br/>"
            "• <b>Active Monitoring:</b> Automated 4-hour background checking of all tracked items.<br/>"
            "• <b>Maintenance SLA:</b> Proactive updates for DOM layout changes & WAF bypasses.<br/>"
            "• <b>Coverage:</b> Amazon, Flipkart, JioMart, Reliance Digital, Croma & Samsung.<br/>"
            "<i>Monthly recurring retainer for Daisha Electronic.</i>",
            body_style
        )]
    ]
    notes_table = Table(notes_info, colWidths=[3.75 * inch])
    notes_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
    ]))

    bottom_block = Table([[notes_table, summary_table]], colWidths=[3.85 * inch, 3.8 * inch])
    bottom_block.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(bottom_block)
    story.append(Spacer(1, 12))

    # 5. Terms Footer
    terms_text = (
        "<b>Terms of Service:</b><br/>"
        "1. This monthly retainer covers cloud container hosting and continuous scraper maintenance for @Stockmightybot.<br/>"
        "2. Service ensures 24/7 uptime and 24-hour turnaround on e-commerce anti-bot and layout updates.<br/>"
        "<b>Thank you for your business!</b>"
    )
    story.append(Paragraph(terms_text, ParagraphStyle('Terms', fontName='Helvetica', fontSize=7.2, leading=9.5, textColor=colors.HexColor('#64748B'))))

    doc.build(story)
    print(f"✅ Monthly Recurring Invoice PDF successfully generated at: {pdf_path}")
    doc_fitz = fitz.open(pdf_path)
    print(f"📄 Page count: {len(doc_fitz)}")


if __name__ == "__main__":
    generate_invoice("Invoice_Setup_and_Monthly.pdf")
    generate_monthly_recurring_invoice("Invoice_Monthly_Retainer.pdf")
