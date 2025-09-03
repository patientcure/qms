# apps/quotations/pdf_service.py
import io
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.pdfgen import canvas
from .models import TermsAndConditions as Term

class QuotationPDFGenerator:
    def __init__(self, quotation, items_data, company_profile=None, terms=None):
        self.quotation = quotation
        self.items_data = items_data
        self.company = company_profile
        self.terms = terms or []
        self.styles = getSampleStyleSheet()
        self.buffer = io.BytesIO()
        self.doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=20 * mm, leftMargin=20 * mm,
            topMargin=25 * mm, bottomMargin=25 * mm
        )
        self.primary_blue = colors.Color(37/255, 99/255, 235/255)
        self.light_gray = colors.Color(249/255, 250/255, 251/255)
        self.dark_gray = colors.Color(55/255, 65/255, 81/255)
        self.medium_gray = colors.Color(75/255, 85/255, 99/255)
        self.border_gray = colors.Color(209/255, 213/255, 219/255)
        self._define_styles()

    def _to_decimal(self, value, precision='0.01'):
        if value is None: return Decimal('0')
        try:
            return Decimal(str(value)).quantize(Decimal(precision), rounding=ROUND_HALF_UP)
        except (ValueError, TypeError):
            return Decimal('0')

    def _format_currency(self, value):
        return f"Rs. {value:,.2f}"

    def _define_styles(self):
        self.title_style = ParagraphStyle('Title', parent=self.styles['Heading1'], fontSize=24, fontName='Helvetica-Bold', spaceAfter=20, alignment=TA_LEFT, textColor=colors.Color(17/255, 24/255, 39/255))
        self.company_name_style = ParagraphStyle('CompanyName', parent=self.styles['Heading1'], fontSize=20, fontName='Helvetica-Bold', spaceAfter=8, alignment=TA_RIGHT, textColor=self.primary_blue)
        self.section_heading_style = ParagraphStyle('SectionHeading', parent=self.styles['Heading2'], fontSize=14, fontName='Helvetica-Bold', spaceAfter=12, spaceBefore=16, textColor=colors.Color(17/255, 24/255, 39/255))
        self.normal_style = ParagraphStyle('Normal', parent=self.styles['Normal'], fontSize=10, textColor=self.dark_gray, leading=14)
        self.right_style = ParagraphStyle('Right', parent=self.styles['Normal'], fontSize=10, alignment=TA_RIGHT, textColor=self.dark_gray)
        self.small_text_style = ParagraphStyle('SmallText', parent=self.styles['Normal'], fontSize=9, textColor=self.medium_gray, alignment=TA_RIGHT, leading=12)
        self.terms_heading_style = ParagraphStyle('TermsHeading', parent=self.styles['Heading3'], fontSize=11, fontName='Helvetica-Bold', spaceAfter=6, spaceBefore=6, textColor=colors.Color(17/255, 24/255, 39/255))
        self.terms_content_style = ParagraphStyle('TermsContent', parent=self.styles['Normal'], fontSize=9, spaceAfter=6, textColor=self.dark_gray, leading=12)
        self.footer_style = ParagraphStyle('Footer', parent=self.styles['Normal'], fontSize=8, alignment=TA_CENTER, textColor=self.medium_gray)

    def _build_company_header(self):
        left_content = [Paragraph("QUOTATION", self.title_style)]
        quotation_info = f"<b>Quotation No:</b> {self.quotation.quotation_number}<br/><b>Date:</b> {datetime.now().strftime('%d/%m/%Y')}<br/>"
        if self.quotation.follow_up_date:
            quotation_info += f"<b>Valid Until:</b> {self.quotation.follow_up_date.strftime('%d-%m-%Y')}"
        left_content.append(Paragraph(quotation_info, self.normal_style))
        
        right_content = []
        if self.company:
            right_content.append(Paragraph(self.company.name or "Your Company", self.company_name_style))
            company_details = f"{self.company.address or ''}<br/>Phone: {self.company.phone or ''}<br/>Email: {self.company.email or ''}<br/>GST: {self.company.gst_number or ''}"
            right_content.append(Paragraph(company_details, self.small_text_style))
        
        header_table = Table([[left_content, right_content]], colWidths=[85 * mm, 85 * mm], style=[('VALIGN', (0, 0), (-1, -1), 'TOP')])
        return [header_table, Spacer(1, 8 * mm)]

    def _build_customer_info(self):
        customer = self.quotation.customer
        customer_info = f"<b>Customer Name:</b> {customer.name}<br/>"
        if customer.email: customer_info += f"<b>Email:</b> {customer.email}<br/>"
        if customer.phone: customer_info += f"<b>Phone:</b> {customer.phone}<br/>"
        if customer.company_name: customer_info += f"<b>Company:</b> {customer.company_name}<br/>"
        if customer.gst_number: customer_info += f"<b>GST:</b> {customer.gst_number}<br/>"
        if customer.primary_address: customer_info += f"<b>Address:</b> {customer.primary_address}"
        
        customer_table = Table([[Paragraph(customer_info, self.normal_style)]], colWidths=[170 * mm])
        customer_table.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), self.light_gray), ('GRID', (0,0), (-1,-1), 0.5, self.border_gray), ('PADDING', (0,0), (-1,-1), 12)]))
        return [Paragraph("Bill To:", self.section_heading_style), customer_table, Spacer(1, 8 * mm)]

    def _build_items_table(self):
        headers = ['S.No.', 'Product/Service', 'Qty', 'Rate', 'Disc (%)', 'Net Amount']
        table_data = [headers]
        subtotal = Decimal('0')
        total_item_discount = Decimal('0')

        for idx, item in enumerate(self.items_data, 1):
            quantity = self._to_decimal(item.get('quantity', 1))
            unit_price = self._to_decimal(item.get('unit_price', 0))
            item_discount_percent = self._to_decimal(item.get('discount', 0))
            gross_amount = quantity * unit_price
            discount_amount = gross_amount * (item_discount_percent / 100)
            net_amount = gross_amount - discount_amount
            subtotal += gross_amount
            total_item_discount += discount_amount
            
            description = item.get('description') or item.get('name', 'N/A')
            row = [
                Paragraph(str(idx), self.normal_style), Paragraph(description, self.normal_style),
                Paragraph(str(quantity), self.normal_style), Paragraph(self._format_currency(unit_price), self.right_style),
                Paragraph(f"{item_discount_percent:.2f}%", self.right_style), Paragraph(self._format_currency(net_amount), self.right_style),
            ]
            table_data.append(row)

        item_table = Table(table_data, colWidths=[12*mm, 68*mm, 15*mm, 25*mm, 20*mm, 30*mm], repeatRows=1)
        item_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(239/255, 246/255, 255/255)), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('ALIGN', (1, 0), (1, -1), 'LEFT'), ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 1, self.border_gray), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        calculated_totals = {"subtotal": subtotal, "total_item_discount": total_item_discount}
        return [item_table, Spacer(1, 8*mm)], calculated_totals

    def _build_totals(self, totals):
        # --- MODIFIED: This entire method is updated to subtract discount last ---
        subtotal = self._to_decimal(totals.get("subtotal", 0))
        total_item_discount = self._to_decimal(totals.get("total_item_discount", 0))
        
        subtotal_after_item_disc = subtotal - total_item_discount

        # 1. Calculate tax amount based on the subtotal after item discounts
        tax_rate = self._to_decimal(self.quotation.tax_rate)
        tax_amount = Decimal('0.00')
        tax_label = 'Tax:'
        if tax_rate > 0:
            tax_amount = subtotal_after_item_disc * (tax_rate / 100)
            tax_label = f'Tax ({tax_rate}%):'
        
        # 2. Calculate the total before applying the final discount
        total_before_overall_discount = subtotal_after_item_disc + tax_amount
        
        # 3. Calculate overall discount amount (base is pre-tax subtotal)
        overall_discount_value = self._to_decimal(getattr(self.quotation, 'discount', 0))
        discount_label = 'Discount:'
        overall_discount_amount = Decimal('0.00')
        if overall_discount_value > 0:
            if getattr(self.quotation, 'discount_type', 'percentage') == 'amount':
                overall_discount_amount = overall_discount_value
            else:
                overall_discount_amount = subtotal_after_item_disc * (overall_discount_value / 100)
                discount_label = f'Discount ({overall_discount_value}%):'
        
        # 4. Calculate final grand total by subtracting the discount last
        grand_total = total_before_overall_discount - overall_discount_amount

        totals_data = [
            ['Subtotal:', self._format_currency(subtotal)],
            ['Item Discounts:', f"- {self._format_currency(total_item_discount)}"],
            [tax_label, self._format_currency(tax_amount)],
            [discount_label, f"- {self._format_currency(overall_discount_amount)}"],
            ['Total Amount:', self._format_currency(grand_total)],
        ]
        
        totals_table = Table(totals_data, colWidths=[40*mm, 40*mm])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'), ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, -1), (-1, -1), self.primary_blue), ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.black),
            ('TOPPADDING', (0, -1), (-1, -1), 8),
        ]))

        summary_container = Table([[totals_table]], colWidths=[170 * mm], style=[('ALIGN', (0, 0), (0, 0), 'RIGHT')])
        return [summary_container, Spacer(1, 10*mm)]
        
    def _build_terms(self):
        elements = []
        if not self.terms: return elements
        try:
            terms_to_display = list(Term.objects.filter(id__in=self.terms))
        except (ValueError, TypeError): return []
        if not terms_to_display: return elements

        elements.append(Paragraph("Terms & Conditions:", self.section_heading_style))
        for term in terms_to_display:
            elements.append(Paragraph(term.title, self.terms_heading_style))
            content = (term.content_html or "").replace('<p>', '').replace('</p>', '<br/>').replace('&nbsp;', ' ')
            elements.append(Paragraph(content, self.terms_content_style))
        return elements

    def _build_footer(self):
        footer_table = Table([[Paragraph("Thank you for your business!", self.normal_style), Paragraph("Digitally Signed <br/>Admin Authorized", self.right_style)]], colWidths=[85 * mm, 85 * mm])
        footer_text = f"Generated on {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        if self.company: footer_text += f" | {self.company.name}"
        return [Spacer(1, 15 * mm), footer_table, Spacer(1, 10 * mm), Paragraph(footer_text, self.footer_style)]

    def _add_page_number(self, canvas_obj, doc):
        page_num = canvas_obj.getPageNumber()
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.setFillColor(self.medium_gray)
        canvas_obj.drawRightString(200 * mm, 10 * mm, f"Page {page_num}")

    def generate(self):
        elements = []
        elements.extend(self._build_company_header())
        elements.extend(self._build_customer_info())
        item_elements, calculated_totals = self._build_items_table()
        elements.extend(item_elements)
        elements.extend(self._build_totals(calculated_totals))
        elements.extend(self._build_terms())
        elements.extend(self._build_footer())
        self.doc.build(elements, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)
        pdf = self.buffer.getvalue()
        self.buffer.close()
        return pdf