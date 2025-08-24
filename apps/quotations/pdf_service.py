# apps/quotations/pdf_service.py
import io
import re
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.pdfgen import canvas
from .models import TermsAndConditions as Term


class QuotationPDFGenerator:
    def __init__(self, quotation, company_profile=None, terms=None):
        self.quotation = quotation
        self.company = company_profile
        self.terms = terms or []
        self.styles = getSampleStyleSheet()
        self.buffer = io.BytesIO()
        self.doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm
        )
        self._define_styles()
    
    def _define_styles(self):
        self.title_style = ParagraphStyle(
            'Title',
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        self.heading_style = ParagraphStyle(
            'Heading',
            parent=self.styles['Heading2'],
            fontSize=12,
            spaceAfter=12,
            spaceBefore=12
        )
        
        self.normal_style = ParagraphStyle(
            'Normal',
            parent=self.styles['Normal'],
            fontSize=10
        )
        
        self.bold_style = ParagraphStyle(
            'Bold',
            parent=self.styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold'
        )
        
        self.right_style = ParagraphStyle(
            'Right',
            parent=self.styles['Normal'],
            fontSize=10,
            alignment=TA_RIGHT
        )
        
        self.terms_heading_style = ParagraphStyle(
            'TermsHeading',
            parent=self.styles['Heading3'],
            fontSize=11,
            fontName='Helvetica-Bold',
            spaceAfter=6,
            spaceBefore=6
        )
        
        self.terms_content_style = ParagraphStyle(
            'TermsContent',
            parent=self.styles['Normal'],
            fontSize=9,
            leftIndent=10,
            spaceAfter=6
        )
    
    def _build_company_header(self):
        elements = []
        
        if self.company:
            elements.append(Paragraph(self.company.name, self.title_style))
            
            company_details = []
            if self.company.address:
                company_details.append(self.company.address)
            if self.company.email:
                company_details.append(f"Email: {self.company.email}")
            if self.company.phone:
                company_details.append(f"Phone: {self.company.phone}")
            if self.company.gst_number:
                company_details.append(f"GST: {self.company.gst_number}")
                
            for detail in company_details:
                elements.append(Paragraph(detail, self.normal_style))
        
        elements.append(Spacer(1, 15 * mm))
        return elements
    
    def _build_quotation_info(self):
        elements = []
        elements.append(Paragraph("QUOTATION", self.heading_style))
        
        info_data = [
            [Paragraph("Quotation #:", self.bold_style), Paragraph(self.quotation.quotation_number, self.normal_style)],
            [Paragraph("Date:", self.bold_style), Paragraph(datetime.now().strftime("%Y-%m-%d"), self.normal_style)],
        ]
        
        if self.quotation.follow_up_date:
            info_data.append([
                Paragraph("Valid Until:", self.bold_style), 
                Paragraph(self.quotation.follow_up_date.strftime("%Y-%m-%d"), self.normal_style)
            ])
        
        info_table = Table(info_data, colWidths=[40 * mm, 80 * mm])
        info_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        elements.append(info_table)
        elements.append(Spacer(1, 10 * mm))
        return elements
    
    def _build_customer_info(self):
        elements = []
        elements.append(Paragraph("Customer Details", self.heading_style))
        
        customer = self.quotation.customer
        customer_data = [
            [Paragraph("Name:", self.bold_style), Paragraph(customer.name, self.normal_style)],
            [Paragraph("Email:", self.bold_style), Paragraph(customer.email, self.normal_style)],
        ]
        
        if customer.phone:
            customer_data.append([Paragraph("Phone:", self.bold_style), Paragraph(customer.phone, self.normal_style)])
        if customer.company_name:
            customer_data.append([Paragraph("Company:", self.bold_style), Paragraph(customer.company_name, self.normal_style)])
        if customer.gst_number:
            customer_data.append([Paragraph("GST:", self.bold_style), Paragraph(customer.gst_number, self.normal_style)])
        if customer.address:
            customer_data.append([Paragraph("Address:", self.bold_style), Paragraph(customer.address, self.normal_style)])
        
        customer_table = Table(customer_data, colWidths=[30 * mm, 90 * mm])
        customer_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        elements.append(customer_table)
        elements.append(Spacer(1, 10 * mm))
        return elements
    
    def _build_items_table(self):
        elements = []
        elements.append(Paragraph("Items", self.heading_style))
        
        headers = ['Item', 'Description', 'Qty', 'Unit Price', 'Tax %', 'Total']
        table_data = [headers]
        
        for item in self.quotation.items.select_related('product').all():
            row = [
                Paragraph(item.product.name if item.product else "N/A", self.normal_style),
                Paragraph(item.description or "", self.normal_style),
                Paragraph(str(item.quantity), self.normal_style),
                Paragraph(f"Rs  {item.unit_price:.2f}", self.normal_style),
                Paragraph(f"{item.tax_rate}%", self.normal_style),
                Paragraph(f"Rs  {(item.quantity * item.unit_price * (1 + item.tax_rate / 100)):.2f}", self.normal_style),
            ]
            table_data.append(row)
        
        item_table = Table(
            table_data, 
            colWidths=[35 * mm, 45 * mm, 20 * mm, 25 * mm, 20 * mm, 25 * mm],
            repeatRows=1
        )
        
        item_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (2, 1), (5, -1), 'RIGHT'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(item_table)
        elements.append(Spacer(1, 10 * mm))
        return elements
    
    def _build_totals(self):
        elements = []

        # compute totals dynamically
        subtotal = sum(item.quantity * item.unit_price for item in self.quotation.items.all())
        tax_total = sum(item.quantity * item.unit_price * (item.tax_rate / 100) for item in self.quotation.items.all())
        grand_total = subtotal + tax_total

        totals_data = [
            [Paragraph("Subtotal:", self.bold_style), Paragraph(f"Rs  {subtotal:.2f}", self.normal_style)],
            [Paragraph("Tax Total:", self.bold_style), Paragraph(f"Rs  {tax_total:.2f}", self.normal_style)],
            [Paragraph("Grand Total:", self.bold_style), Paragraph(f"Rs  {grand_total:.2f}", self.bold_style)],
        ]

        totals_table = Table(totals_data, colWidths=[40 * mm, 40 * mm])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))

        elements.append(totals_table)
        elements.append(Spacer(1, 15 * mm))
        return elements
    
    def _clean_html_content(self, html_content):
        if not html_content:
            return ""
        content = html_content.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
        content = re.sub(r'<p[^>]*>', '\n', content)
        content = content.replace('</p>', '\n')
        content = re.sub(r'<li[^>]*>', '• ', content)
        content = content.replace('</li>', '\n')
        content = re.sub(r'<ul[^>]*>|</ul>', '', content)
        content = re.sub(r'<ol[^>]*>|</ol>', '', content)
        content = re.sub(r'<[^>]+>', '', content)
        content = re.sub(r'\n\s*\n', '\n\n', content)
        return content.strip()
    
    def _build_terms(self):
        elements = []
        terms_to_display = []

        if self.terms:
            terms_to_display = list(Term.objects.filter(id__in=self.terms))

        if not terms_to_display and hasattr(self.quotation, 'terms') and self.quotation.terms:
            try:
                if isinstance(self.quotation.terms, str):
                    term_ids = [int(t.strip()) for t in self.quotation.terms.split(",") if t.strip().isdigit()]
                    terms_to_display = list(Term.objects.filter(id__in=term_ids))
                else:
                    terms_to_display = list(self.quotation.terms.all())
            except Exception:
                pass

        if terms_to_display:
            elements.append(Paragraph("Terms & Conditions", self.heading_style))
            for term in terms_to_display:
                elements.append(Paragraph(term.title, self.terms_heading_style))
                content = getattr(term, 'content_html', '') or str(getattr(term, 'content', ''))
                if content:
                    bullet_points = re.findall(r'\*(.*?)\*', content)
                    normal_text = re.sub(r'\*(.*?)\*', '', content).strip()
                    if normal_text:
                        elements.append(Paragraph(normal_text, self.terms_content_style))
                    if bullet_points:
                        bullet_items = [ListItem(Paragraph(bp.strip(), self.terms_content_style)) for bp in bullet_points]
                        elements.append(ListFlowable(bullet_items, bulletType='bullet', leftIndent=10 * mm))
                elements.append(Spacer(1, 5 * mm))

        return elements
    
    def _build_footer(self):
        elements = []
        elements.append(Spacer(1, 20 * mm))
        footer_text = f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        if self.company:
            footer_text += f" | {self.company.name}"
        elements.append(Paragraph(footer_text, ParagraphStyle(
            'Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            alignment=TA_CENTER,
            textColor=colors.grey
        )))
        return elements
    
    def _add_page_number(self, canvas_obj: canvas.Canvas, doc):
        page_num = canvas_obj.getPageNumber()
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.setFillColor(colors.grey)
        canvas_obj.drawRightString(200 * mm, 10 * mm, f"Page {page_num}")
    
    def generate(self):
        elements = []
        elements.extend(self._build_company_header())
        elements.extend(self._build_quotation_info())
        elements.extend(self._build_customer_info())
        elements.extend(self._build_items_table())
        elements.extend(self._build_totals())
        elements.extend(self._build_terms())
        elements.extend(self._build_footer())
        
        self.doc.build(elements, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)
        pdf = self.buffer.getvalue()
        self.buffer.close()
        return pdf
