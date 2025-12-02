# apps/quotations/pdf_service.py
import io
import re
import os
import requests
from reportlab.platypus import Image as RLImage, Table as RLTable, Paragraph, Spacer, KeepTogether
from reportlab.lib.units import mm
from reportlab.lib import colors
from decimal import Decimal

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    ListFlowable, ListItem, Frame, PageTemplate, NextPageTemplate
)
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.utils import ImageReader
from .models import TermsAndConditions as Term
from django.contrib.staticfiles import finders


class QuotationPDFGenerator:
    def __init__(self, quotation, items_data, user=None, company_profile=None, terms=None):
        self.quotation = quotation
        self.items_data = items_data
        self.user = user
        self.company = company_profile
        self.terms = terms or []
        self.styles = getSampleStyleSheet()
        self.buffer = io.BytesIO()

        self.doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=50 * mm,
            bottomMargin=50 * mm
        )

        self.primary_blue = colors.Color(37/255, 99/255, 235/255)
        self.light_gray = colors.Color(249/255, 250/255, 251/255)
        self.dark_gray = colors.Color(55/255, 65/255, 81/255)
        self.medium_gray = colors.Color(75/255, 85/255, 99/255)
        self.border_gray = colors.Color(209/255, 213/255, 219/255)
        self.separator_gray = colors.Color(220/255, 38/255, 38/255)
        self.header_blue = colors.Color(0/255, 51/255, 102/255)

        self._define_styles()
        self._setup_templates()

    def _setup_templates(self):
        """Setup page templates with consistent header/footer"""
        frame = Frame(self.doc.leftMargin, self.doc.bottomMargin, self.doc.width, self.doc.height, id='normal')
        first_page_template = PageTemplate(id='firstPage', frames=[frame], onPage=self._draw_header_footer)
        later_page_template = PageTemplate(id='laterPages', frames=[frame], onPage=self._draw_header_footer)
        self.doc.addPageTemplates([first_page_template, later_page_template])

    def _draw_header_footer(self, canvas, doc):
        """Draw header and footer on every page"""
        canvas.saveState()
        self._draw_header(canvas)
        self._draw_footer(canvas)
        self._add_page_number(canvas, doc)
        canvas.restoreState()

    def _draw_header(self, canvas):
        """Draw the exact header from letterhead"""
        page_width, page_height = A4
        try:
            godrej_path = finders.find("quotations/assets/godrej.jpeg")
            if godrej_path:
                godrej_logo = ImageReader(godrej_path)
                logo_x = page_width - 60 * mm
                logo_y = page_height - 25 * mm
                canvas.drawImage(godrej_logo, logo_x, logo_y, width=40 * mm, height=15 * mm, preserveAspectRatio=True, mask='auto')
        except Exception as e:
            print(f"Error loading Godrej logo: {e}")
        canvas.setFont("Helvetica-Bold", 16)
        canvas.setFillColor(self.header_blue)
        canvas.drawString(20 * mm, page_height - 20 * mm, "N.K. Prosales Private Limited")
        canvas.setFont("Helvetica", 10)
        canvas.drawString(20 * mm, page_height - 26 * mm, "39/1, Acharya puri, Gurgaon-122001")
        canvas.drawString(20 * mm, page_height - 30 * mm, "Ph-0124 - 2306638, Email: neelamgt2004@yahoo.co.in")
        canvas.setStrokeColor(self.separator_gray)
        canvas.setLineWidth(1.0)
        canvas.line(20 * mm, page_height - 32 * mm, page_width - 20 * mm, page_height - 32 * mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(self.medium_gray)
        canvas.drawString(20 * mm, page_height - 36 * mm, "Wholesale Dealer of: GODREJ & Boyce Mfg. Co. Ltd., Carysil, Eureka Forbes")

    def _draw_footer(self, canvas):
        """Draw the exact footer from letterhead"""
        page_width, _ = A4
        try:
            eureka_path = finders.find("quotations/assets/eureka.jpeg")
            if eureka_path:
                canvas.drawImage(ImageReader(eureka_path), 60 * mm, 25 * mm, width=30 * mm, height=12 * mm, preserveAspectRatio=True, mask='auto')
        except Exception as e:
            print(f"Error loading Eureka logo: {e}")
        try:
            carysil_path = finders.find("quotations/assets/carysil.jpeg")
            if carysil_path:
                canvas.drawImage(ImageReader(carysil_path), 120 * mm, 25 * mm, width=30 * mm, height=12 * mm, preserveAspectRatio=True, mask='auto')
        except Exception as e:
            print(f"Error loading Carysil logo: {e}")
        canvas.setStrokeColor(self.separator_gray)
        canvas.setLineWidth(1.0)
        canvas.line(20 * mm, 21 * mm, page_width - 20 * mm, 21 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(self.dark_gray)
        canvas.drawCentredString(page_width / 2, 18 * mm, "Godrej: Modular Office Furniture Systems and Storage Products • Physical Electronics & Premises Security Equipment • Optimiser • Heavy Duty Indl. Rack.")
        canvas.drawCentredString(page_width / 2, 14 * mm, "Eureka Forbes: Commercial & Industrial Products • Vacuum Cleaner • Scrubber Drier • Sweeper • High Jet Pressure • Water Cooler.")
        canvas.drawCentredString(page_width / 2, 10 * mm, "Carysil: Sinks • Faucet • Chimney • Hobs etc.")

    def _add_page_number(self, canvas, doc):
        page_num = canvas.getPageNumber()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(self.medium_gray)
        canvas.drawRightString(A4[0] - 20 * mm, A4[1] - 46 * mm, f"Page {page_num}")

    def _to_decimal(self, value, precision='0.01'):
        if value is None: return Decimal('0')
        try:
            return Decimal(str(value)).quantize(Decimal(precision), rounding=ROUND_HALF_UP)
        except (ValueError, TypeError):
            return Decimal('0')

    def _format_currency(self, value):
        return f"Rs.&nbsp;{value:,.2f}"

    def _clean_html_content(self, content):
        if not content: return ""
        return re.sub(r'<[^>]+>', '', content).strip()

    def _define_styles(self):
        """Define paragraph styles, keeping original styles"""
        self.title_style = ParagraphStyle('Title', parent=self.styles['Heading1'], fontSize=16, fontName='Helvetica-Bold', spaceAfter=14, alignment=TA_CENTER, textColor=self.dark_gray)
        self.section_heading_style = ParagraphStyle('SectionHeading', parent=self.styles['Heading2'], fontSize=14, fontName='Helvetica-Bold', spaceAfter=12, spaceBefore=16, textColor=colors.black)
        self.normal_style = ParagraphStyle('Normal', parent=self.styles['Normal'], fontSize=10, textColor=self.dark_gray, leading=14)
        self.right_style = ParagraphStyle('Right', parent=self.styles['Normal'], fontSize=10, alignment=TA_RIGHT, textColor=self.dark_gray)
        self.terms_heading_style = ParagraphStyle('TermsHeading', parent=self.styles['Heading3'], fontSize=11, fontName='Helvetica-Bold', spaceAfter=6, spaceBefore=6, textColor=colors.black)
        self.terms_content_style = ParagraphStyle('TermsContent', parent=self.styles['Normal'], fontSize=9, spaceAfter=6, textColor=self.dark_gray, leading=12)
        self.footer_style = ParagraphStyle('Footer', parent=self.styles['Normal'], fontSize=8, alignment=TA_CENTER, textColor=self.medium_gray)

    def _build_header_and_customer_info(self):
        """Builds header and customer info based on requested changes."""
        elements = [
            Paragraph("QUOTATION", self.title_style),
            Paragraph(f"Date: {datetime.now().strftime('%d-%m-%Y')}", self.right_style),
            Paragraph(f"{self.quotation.quotation_number}", self.right_style),
            Spacer(1, 8 * mm),
            Paragraph("To:", self.normal_style),
            Spacer(1, 2 * mm),
        ]

        customer = self.quotation.customer
        info = [f"<b>Company Name:</b> {customer.company_name}"]
        info.append(f"<b>Customer Name:</b> {customer.name}")
        if customer.email: info.append(f"<b>Email:</b> {customer.email}")
        if customer.phone: info.append(f"<b>Phone:</b> {customer.phone}")
        if customer.primary_address: info.append(f"<b>Address:</b> {customer.primary_address}")
        if customer.gst_number: info.append(f"<b>GST Number:</b> {customer.gst_number}")

        customer_table = Table(
            [[Paragraph("<br/>".join(info), self.normal_style)]],
            colWidths=[170 * mm]
        )
        customer_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), self.light_gray),
            ('GRID', (0, 0), (-1, -1), 0.5, self.border_gray),
            ('PADDING', (0, 0), (-1, -1), 12)
        ]))

        elements.extend([customer_table, Spacer(1, 8 * mm)])
        return elements

    def _build_items_table(self):
        has_any_discount = any(self._to_decimal(item.get('discount', 0)) > 0 for item in self.items_data)

        if has_any_discount:
            headers = ['S.No.', 'Product/Service', 'Qty', 'Rate', 'Disc (%)', 'Net Amount']
            colWidths = [12*mm, 68*mm, 15*mm, 25*mm, 20*mm, 30*mm]
        else:
            headers = ['S.No.', 'Product/Service', 'Qty', 'Rate', 'Net Amount']
            colWidths = [12*mm, 88*mm, 15*mm, 25*mm, 30*mm]

        table_data = [headers]
        subtotal = Decimal('0')
        total_item_discount = Decimal('0')
        max_img_w = 18 * mm
        max_img_h = 18 * mm

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

            # --- build product/service cell with optional image ---
            product_cell = Paragraph(description, self.normal_style)

            image_flowable = None
            image_url = item.get('image_url') or item.get('image_path')  # accept either key
            if image_url:
                try:
                    if str(image_url).lower().startswith(('http://', 'https://')):
                        resp = requests.get(image_url, timeout=5)
                        resp.raise_for_status()
                        img_io = io.BytesIO(resp.content)
                        image_flowable = RLImage(img_io, width=max_img_w, height=max_img_h, kind='proportional')
                    else:
                        # treat as local file path
                        if os.path.exists(image_url):
                            image_flowable = RLImage(image_url, width=max_img_w, height=max_img_h, kind='proportional')
                except Exception:
                    # silently ignore image errors and fall back to text only
                    image_flowable = None

            if image_flowable:
                # Create a small two-column table: [image | description]
                # ensure left column fits image, right column uses rest of the product column width
                product_col_width = colWidths[1] if len(colWidths) > 1 else 68*mm
                inner_colwidths = [max_img_w + 2*mm, product_col_width - (max_img_w + 2*mm)]
                inner_table = RLTable(
                    [[image_flowable, Paragraph(description, self.normal_style)]],
                    colWidths=inner_colwidths,
                    style=[
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('LEFTPADDING', (0, 0), (-1, -1), 0),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                        ('TOPPADDING', (0, 0), (-1, -1), 0),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                    ]
                )
                product_cell = inner_table  # cell becomes the mini-table
            # --- end image cell build ---

            row = [
                Paragraph(str(idx), self.normal_style),
                product_cell,
                Paragraph(str(quantity), self.normal_style),
                Paragraph(self._format_currency(unit_price), self.right_style),
            ]
            if has_any_discount:
                discount_text = f"{item_discount_percent:.2f}%" if item_discount_percent > 0 else "--"
                row.append(Paragraph(discount_text, self.right_style))
            row.append(Paragraph(self._format_currency(net_amount), self.right_style))
            table_data.append(row)

        item_table = Table(table_data, colWidths=colWidths, repeatRows=1)
        item_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(239/255, 246/255, 255/255)),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 1, self.border_gray),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))

        return [item_table, Spacer(1, 8*mm)], {"subtotal": subtotal, "total_item_discount": total_item_discount}

    def _build_totals(self, totals):
        subtotal_after_item_disc = self._to_decimal(totals.get("subtotal", 0)) - self._to_decimal(totals.get("total_item_discount", 0))
        overall_discount_value = self._to_decimal(getattr(self.quotation, 'discount', 0))
        discount_label, overall_discount_amount = 'Special Discount:', Decimal('0.00')
        if overall_discount_value > 0:
            if getattr(self.quotation, 'discount_type', 'percentage') == 'amount':
                overall_discount_amount = overall_discount_value
            else:
                overall_discount_amount = subtotal_after_item_disc * (overall_discount_value / 100)
                discount_label = f'Special Discount ({overall_discount_value}%):'
        subtotal_after_all_discounts = subtotal_after_item_disc - overall_discount_amount
        additional_charge_amount = self._to_decimal(getattr(self.quotation, 'additional_charge_amount', 0))
        additional_charge_name = getattr(self.quotation, 'additional_charge_name', 'Additional Charges') or 'Additional Charges'
        subtotal_before_tax = subtotal_after_all_discounts + additional_charge_amount
        
        tax_rate = self._to_decimal(getattr(self.quotation, 'tax_rate', 0))
        tax_amount = subtotal_before_tax * (tax_rate / 100)
        tax_label = f'Tax ({tax_rate}%):' if tax_rate > 0 else 'Tax:'

        grand_total = subtotal_before_tax + tax_amount

        totals_data = [
            ['Subtotal:', self._format_currency(subtotal_after_item_disc)],
        ]       
        if overall_discount_amount > 0:
            totals_data.append([discount_label, f"- {self._format_currency(overall_discount_amount)}"])

        if additional_charge_amount > 0:
            totals_data.append([f'{additional_charge_name}:', self._format_currency(additional_charge_amount)])
        
        totals_data.extend([
            [tax_label, self._format_currency(tax_amount)],
            ['Total Amount:', self._format_currency(grand_total)],
        ])
        totals_table = Table(totals_data, colWidths=[40*mm, 40*mm])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, -1), (-1, -1), self.primary_blue),
            ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.black),
            ('TOPPADDING', (0, -1), (-1, -1), 8),
        ]))
        return [Table([[totals_table]], colWidths=[170 * mm], style=[('ALIGN', (0, 0), (0, 0), 'RIGHT')]), Spacer(1, 10*mm)]

    def _build_terms(self):
        """Build terms and conditions section"""
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
            elements.append(Paragraph("Terms & Conditions:", self.section_heading_style))          
            for term in terms_to_display:
                elements.append(Paragraph(term.title, self.terms_heading_style))
                content = getattr(term, 'content_html', '') or str(getattr(term, 'content', ''))
                if content:
                    # Extract bullet points from stars and normal text
                    bullet_points = re.findall(r'\*(.*?)\*', content)
                    normal_text = re.sub(r'\*(.*?)\*', '', content).strip()
                    
                    # Add normal text first if exists
                    if normal_text:
                        clean_normal_text = self._clean_html_content(normal_text)
                        if clean_normal_text:
                            elements.append(Paragraph(clean_normal_text, self.terms_content_style))
                    
                    # Add bullet points if exists
                    if bullet_points:
                        bullet_items = [
                            ListItem(Paragraph(bp.strip(), self.terms_content_style)) 
                            for bp in bullet_points
                        ]
                        elements.append(ListFlowable(
                            bullet_items, 
                            bulletType='bullet', 
                            leftIndent=10 * mm
                        ))
                
                elements.append(Spacer(1, 5 * mm))
        else:
            # Default terms if none specified
            elements.append(Paragraph("Terms & Conditions:", self.section_heading_style))
            default_terms = """
            1. <b>Pricing:</b> All prices are in Indian Rupees (Rs.) and exclude applicable taxes unless specified.<br/>
            2. <b>Payment:</b> Payment terms as agreed upon between parties.<br/>
            3. <b>Delivery:</b> Delivery timeline will be communicated separately.<br/>
            """
            elements.append(Paragraph(default_terms, self.terms_content_style))

        return elements

    def _build_valid_until(self):
        valid_until = getattr(self.quotation, 'follow_up_date', None)
        if valid_until:
            table = Table(
                [[Paragraph(f"<b>Valid Until:</b> {valid_until.strftime('%d-%m-%Y')}", self.normal_style)]],
                colWidths=[170 * mm]
            )
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.Color(232/255, 245/255, 233/255)),  # light green
                ('BOX', (0, 0), (-1, -1), 1, colors.green),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            return [table, Spacer(1, 5 * mm)]
        return []

    def _build_additional_notes(self):
        elements = []
        additional_notes = getattr(self.quotation, 'additionalNotes', '')
        if additional_notes:
            clean_notes = self._clean_html_content(additional_notes)
            if clean_notes:
                notes_table = Table(
                    [[Paragraph(f"Additional Notes: {clean_notes}", self.normal_style)]],
                    colWidths=[170 * mm]
                )
                notes_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.Color(1, 1, 0.7)),
                    ('BOX', (0, 0), (-1, -1), 1, colors.yellow),
                    ('LEFTPADDING', (0, 0), (-1, -1), 12),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ]))
                elements.append(notes_table)
                elements.append(Spacer(1, 8 * mm))
        return elements
    
    def _build_footer(self):
        creator_name = "Admin"
        creator_phone = ""
        user = getattr(self, 'user', None)
        if user and user.is_authenticated:
            creator_name = user.get_full_name() or user.username or "Admin"
            creator_phone = getattr(user, 'phone_number', "")
        footer_text = f"Thank you for your business!<br/><br/>Created By<br/>{creator_name}"
        if creator_phone:
            footer_text += f"<br/>{creator_phone}"
        footer_table = Table([[
            Paragraph(footer_text, self.normal_style)
        ]], colWidths=[170 * mm])

        return [Spacer(1, 15 * mm), footer_table]

    def generate(self):
        """Generate the complete PDF"""
        elements = [NextPageTemplate('firstPage')]
        
        elements.extend(self._build_header_and_customer_info())
        
        item_elements, calculated_totals = self._build_items_table()
        elements.extend(item_elements)
        elements.extend(self._build_totals(calculated_totals))
        elements.extend(self._build_terms())
        elements.extend(self._build_additional_notes())
        elements.extend(self._build_valid_until())
        elements.extend(self._build_footer())
        
        self.doc.build(elements, onFirstPage=self._draw_header_footer, onLaterPages=self._draw_header_footer)
        
        pdf = self.buffer.getvalue()
        self.buffer.close()
        return pdf