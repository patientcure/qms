# apps/quotations/pdf_service.py
import io
import re
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.graphics import renderPDF
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
            rightMargin=25 * mm,
            leftMargin=25 * mm,
            topMargin=25 * mm,
            bottomMargin=25 * mm
        )
        # Define color scheme matching HTML template
        self.primary_blue = colors.Color(37/255, 99/255, 235/255)  # #2563eb
        self.light_gray = colors.Color(249/255, 250/255, 251/255)  # #f9fafb
        self.dark_gray = colors.Color(55/255, 65/255, 81/255)  # #374151
        self.medium_gray = colors.Color(75/255, 85/255, 99/255)  # #4b5563
        self.border_gray = colors.Color(209/255, 213/255, 219/255)  # #d1d5db
        
        self._define_styles()
    
    def _define_styles(self):
        # Main title style - large and bold
        self.title_style = ParagraphStyle(
            'Title',
            parent=self.styles['Heading1'],
            fontSize=24,
            fontName='Helvetica-Bold',
            spaceAfter=20,
            alignment=TA_LEFT,
            textColor=colors.Color(17/255, 24/255, 39/255)  # #111827
        )
        
        # Company name style - blue accent
        self.company_name_style = ParagraphStyle(
            'CompanyName',
            parent=self.styles['Heading1'],
            fontSize=20,
            fontName='Helvetica-Bold',
            spaceAfter=8,
            alignment=TA_RIGHT,
            textColor=self.primary_blue
        )
        
        # Section headings
        self.section_heading_style = ParagraphStyle(
            'SectionHeading',
            parent=self.styles['Heading2'],
            fontSize=14,
            fontName='Helvetica-Bold',
            spaceAfter=12,
            spaceBefore=16,
            textColor=colors.Color(17/255, 24/255, 39/255)  # #111827
        )
        
        # Normal text
        self.normal_style = ParagraphStyle(
            'Normal',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=self.dark_gray
        )
        
        # Bold text
        self.bold_style = ParagraphStyle(
            'Bold',
            parent=self.styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
            textColor=self.dark_gray
        )
        
        # Right aligned text
        self.right_style = ParagraphStyle(
            'Right',
            parent=self.styles['Normal'],
            fontSize=10,
            alignment=TA_RIGHT,
            textColor=self.dark_gray
        )
        
        # Small text for company details
        self.small_text_style = ParagraphStyle(
            'SmallText',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=self.medium_gray,
            alignment=TA_RIGHT
        )
        
        # Info label style
        self.info_label_style = ParagraphStyle(
            'InfoLabel',
            parent=self.styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
            textColor=self.dark_gray
        )
        
        # Terms styles
        self.terms_heading_style = ParagraphStyle(
            'TermsHeading',
            parent=self.styles['Heading3'],
            fontSize=11,
            fontName='Helvetica-Bold',
            spaceAfter=6,
            spaceBefore=6,
            textColor=colors.Color(17/255, 24/255, 39/255)
        )
        
        self.terms_content_style = ParagraphStyle(
            'TermsContent',
            parent=self.styles['Normal'],
            fontSize=9,
            spaceAfter=6,
            textColor=self.dark_gray
        )
        
        # Footer style
        self.footer_style = ParagraphStyle(
            'Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            alignment=TA_CENTER,
            textColor=self.medium_gray
        )
    
    def _add_header_border(self, elements):
        """Add a blue border line similar to HTML template"""
        # Create a blue line using a table with background color
        line_data = [[""]]
        line_table = Table(line_data, colWidths=[170 * mm])
        line_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), self.primary_blue),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(line_table)
        elements.append(Spacer(1, 8 * mm))
        return elements
    
    def _build_company_header(self):
        elements = []
        
        header_data = []
        
        left_content = []
        left_content.append(Paragraph("QUOTATION", self.title_style))
        
        quotation_info = f"<b>Quotation No:</b> {self.quotation.quotation_number}<br/>"
        quotation_info += f"<b>Date:</b> {datetime.now().strftime('%d/%m/%Y')}<br/>"
        if self.quotation.follow_up_date:
            quotation_info += f"<b>Valid Until:</b> {self.quotation.follow_up_date.strftime('%d-%m-%Y')}"
        
        left_content.append(Paragraph(quotation_info, self.normal_style))
        
        # Right side - Company info
        right_content = []
        if self.company:
            right_content.append(Paragraph(self.company.name or "Your Company", self.company_name_style))
            
            company_details = ""
            if self.company.address:
                company_details += f"{self.company.address}<br/>"
            if self.company.phone:
                company_details += f"Phone: {self.company.phone}<br/>"
            if self.company.email:
                company_details += f"Email: {self.company.email}<br/>"
            if self.company.gst_number:
                company_details += f"GST: {self.company.gst_number}"
            
            if company_details:
                right_content.append(Paragraph(company_details, self.small_text_style))
        
        # Combine left and right in a table
        left_cell = []
        for item in left_content:
            left_cell.append(item)
        
        right_cell = []
        for item in right_content:
            right_cell.append(item)
        
        header_table = Table([[left_cell, right_cell]], colWidths=[85 * mm, 85 * mm])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
        ]))
        
        elements.append(header_table)
        
        # Add the blue border line
        elements = self._add_header_border(elements)
        
        return elements
    
    def _build_customer_info(self):
        elements = []
        elements.append(Paragraph("Bill To:", self.section_heading_style))
        
        customer = self.quotation.customer
        
        # Create customer info in a styled box (using table with background)
        customer_info = ""
        if customer:
            customer_info += f"<b>Customer Name:</b> {customer.name}<br/>"
            if customer.email:
                customer_info += f"<b>Email:</b> {customer.email}<br/>"
            if customer.phone:
                customer_info += f"<b>Phone:</b> {customer.phone}<br/>"
            if customer.company_name:
                customer_info += f"<b>Company:</b> {customer.company_name}<br/>"
            if customer.gst_number:
                customer_info += f"<b>GST:</b> {customer.gst_number}<br/>"
            if customer.address:
                customer_info += f"<b>Address:</b> {customer.address}"
        else:
            customer_info = "<i>No customer information available</i>"
        
        # Create a background box for customer info
        customer_data = [[Paragraph(customer_info, self.normal_style)]]
        customer_table = Table(customer_data, colWidths=[170 * mm])
        customer_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), self.light_gray),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, self.border_gray),
        ]))
        
        elements.append(customer_table)
        elements.append(Spacer(1, 8 * mm))
        return elements
    
    def _build_items_table(self):
        elements = []
        
        # Table headers
        headers = ['S.No.', 'Product/Service', 'Quantity', 'Rate', 'Amount']
        table_data = [headers]
        
        # Add items
        for idx, item in enumerate(self.quotation.items.select_related('product').all(), 1):
            unit_price = float(item.unit_price)
            quantity = float(item.quantity)
            tax_rate = float(item.tax_rate) if item.tax_rate else 0
            
            # Calculate amount including tax
            amount = quantity * unit_price * (1 + tax_rate / 100)
            
            row = [
                Paragraph(str(idx), self.normal_style),
                Paragraph(item.product.name if item.product else (item.description or "N/A"), self.normal_style),
                Paragraph(str(int(quantity) if quantity.is_integer() else quantity), self.normal_style),
                Paragraph(f"Rs. {unit_price:.2f}", self.normal_style),
                Paragraph(f"Rs. {amount:.2f}", self.normal_style),
            ]
            table_data.append(row)
        
        # Create table with styling similar to HTML template
        item_table = Table(
            table_data, 
            colWidths=[15 * mm, 70 * mm, 25 * mm, 30 * mm, 30 * mm],
            repeatRows=1
        )
        
        item_table.setStyle(TableStyle([
            # Header styling
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(239/255, 246/255, 255/255)),  # #eff6ff
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (1, 0), 'LEFT'),  # S.No. and Product left aligned
            ('ALIGN', (2, 0), (2, 0), 'CENTER'),  # Quantity center aligned
            ('ALIGN', (3, 0), (4, 0), 'RIGHT'),  # Rate and Amount right aligned
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            
            # Data rows styling
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), self.dark_gray),
            ('ALIGN', (0, 1), (1, -1), 'LEFT'),  # S.No. and Product left aligned
            ('ALIGN', (2, 1), (2, -1), 'CENTER'),  # Quantity center aligned
            ('ALIGN', (3, 1), (4, -1), 'RIGHT'),  # Rate and Amount right aligned
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 12),
            
            # Grid
            ('GRID', (0, 0), (-1, -1), 1, self.border_gray)
        ]))
        
        elements.append(item_table)
        elements.append(Spacer(1, 8 * mm))
        return elements
    
    def _build_totals(self):
        elements = []

        # Compute totals dynamically
        subtotal = sum(item.quantity * item.unit_price for item in self.quotation.items.all())
        tax_total = sum(item.quantity * item.unit_price * (item.tax_rate / 100 if item.tax_rate else 0) for item in self.quotation.items.all())
        grand_total = subtotal + tax_total

        # Create summary box similar to HTML template
        totals_data = [
            [Paragraph("Subtotal:", self.normal_style), Paragraph(f"Rs. {subtotal:.2f}", self.normal_style)],
            [Paragraph("Tax Total:", self.normal_style), Paragraph(f"Rs. {tax_total:.2f}", self.normal_style)],
            [Paragraph("Total Amount:", ParagraphStyle(
                'TotalAmount',
                parent=self.normal_style,
                fontSize=14,
                fontName='Helvetica-Bold',
                textColor=self.primary_blue
            )), Paragraph(f"Rs. {grand_total:.2f}", ParagraphStyle(
                'TotalAmountValue',
                parent=self.normal_style,
                fontSize=14,
                fontName='Helvetica-Bold',
                textColor=self.primary_blue,
                alignment=TA_RIGHT
            ))],
        ]

        totals_table = Table(totals_data, colWidths=[40 * mm, 40 * mm])
        totals_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), self.light_gray),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTSIZE', (0, 0), (-1, -2), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LINEABOVE', (0, -1), (-1, -1), 1, self.border_gray),
            ('GRID', (0, 0), (-1, -1), 0.5, self.border_gray),
        ]))

        # Right align the summary
        summary_container = Table([[None, totals_table]], colWidths=[90 * mm, 80 * mm])
        summary_container.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))

        elements.append(summary_container)
        elements.append(Spacer(1, 10 * mm))
        return elements
    
    def _build_terms(self):
        elements = []
        terms_to_display = []

        # Get terms to display
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
                        bullet_items = [ListItem(Paragraph(bp.strip(), self.terms_content_style)) for bp in bullet_points]
                        elements.append(ListFlowable(bullet_items, bulletType='bullet', leftIndent=10 * mm))
                
                elements.append(Spacer(1, 5 * mm))
        else:
            # Default terms if none specified
            elements.append(Paragraph("Terms & Conditions:", self.section_heading_style))
            default_terms = """
            1. <b>Pricing:</b> All prices are in Indian Rupees (Rs.) and exclude applicable taxes unless specified.<br/>
            """
            elements.append(Paragraph(default_terms, self.terms_content_style))

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
    
    def _build_footer(self):
        elements = []
        elements.append(Spacer(1, 15 * mm))
        
        # Thank you message and signature section
        footer_data = [
            [Paragraph("Thank you for your business!", self.normal_style), 
             Paragraph("Digitally Signed <br/>Admin Authorized", self.right_style)]
        ]
        
        footer_table = Table(footer_data, colWidths=[85 * mm, 85 * mm])
        footer_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        elements.append(footer_table)
        
        # Generation info
        elements.append(Spacer(1, 10 * mm))
        footer_text = f"Generated on {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        if self.company:
            footer_text += f" | {self.company.name}"
        elements.append(Paragraph(footer_text, self.footer_style))
        
        return elements
    
    def _add_page_number(self, canvas_obj: canvas.Canvas, doc):
        page_num = canvas_obj.getPageNumber()
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.setFillColor(self.medium_gray)
        canvas_obj.drawRightString(200 * mm, 10 * mm, f"Page {page_num}")
    
    def generate(self):
        elements = []
        elements.extend(self._build_company_header())
        elements.extend(self._build_customer_info())
        elements.extend(self._build_items_table())
        elements.extend(self._build_totals())
        elements.extend(self._build_terms())
        elements.extend(self._build_footer())
        
        self.doc.build(elements, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)
        pdf = self.buffer.getvalue()
        self.buffer.close()
        return pdf