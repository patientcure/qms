# apps/quotations/pdf_service.py
import os
import io
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from datetime import datetime
import tempfile
from urllib.parse import urljoin
import re
from weasyprint import HTML
from .models import TermsAndConditions as Term

class QuotationPDFGenerator:
    def __init__(self, quotation, company_profile=None, terms=None):
        self.quotation = quotation
        self.company = company_profile
        self.terms = terms or []  # Accept terms as parameter
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
        
        # Define custom styles
        self._define_styles()
    
    def _define_styles(self):
        # Title style
        self.title_style = ParagraphStyle(
            'Title',
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        # Heading style
        self.heading_style = ParagraphStyle(
            'Heading',
            parent=self.styles['Heading2'],
            fontSize=12,
            spaceAfter=12,
            spaceBefore=12
        )
        
        # Normal style
        self.normal_style = ParagraphStyle(
            'Normal',
            parent=self.styles['Normal'],
            fontSize=10
        )
        
        # Bold style
        self.bold_style = ParagraphStyle(
            'Bold',
            parent=self.styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold'
        )
        
        # Right aligned style
        self.right_style = ParagraphStyle(
            'Right',
            parent=self.styles['Normal'],
            fontSize=10,
            alignment=TA_RIGHT
        )
        
        # Terms heading style
        self.terms_heading_style = ParagraphStyle(
            'TermsHeading',
            parent=self.styles['Heading3'],
            fontSize=11,
            fontName='Helvetica-Bold',
            spaceAfter=6,
            spaceBefore=6
        )
        
        # Terms content style
        self.terms_content_style = ParagraphStyle(
            'TermsContent',
            parent=self.styles['Normal'],
            fontSize=9,
            leftIndent=10,
            spaceAfter=6
        )
    
    def _build_company_header(self):
        """Build company header section"""
        elements = []
        
        if self.company:
            # Company name
            elements.append(Paragraph(self.company.name, self.title_style))
            
            # Company details
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
        """Build quotation information section"""
        elements = []
        
        # Quotation title and number
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
        """Build customer information section"""
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
        """Build quotation items table"""
        elements = []
        elements.append(Paragraph("Items", self.heading_style))
        
        # Table headers
        headers = ['Item', 'Description', 'Qty', 'Unit Price', 'Tax %', 'Total']
        header_style = self.bold_style
        
        # Prepare table data
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
        
        # Create table
        item_table = Table(
            table_data, 
            colWidths=[35 * mm, 45 * mm, 20 * mm, 25 * mm, 20 * mm, 25 * mm],
            repeatRows=1
        )
        
        # Style table
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
        """Build totals section"""
        elements = []
        
        totals_data = [
            [Paragraph("Subtotal:", self.bold_style), Paragraph(f"Rs  {self.quotation.subtotal:.2f}", self.normal_style)],
            [Paragraph("Tax Total:", self.bold_style), Paragraph(f"Rs  {self.quotation.tax_total:.2f}", self.normal_style)],
            [Paragraph("Grand Total:", self.bold_style), Paragraph(f"Rs  {self.quotation.total:.2f}", self.bold_style)],
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
        """Clean and convert HTML content for ReportLab"""
        if not html_content:
            return ""
        
        # Remove HTML tags and convert to plain text with formatting
        # This is a simple approach - you might want to use a proper HTML parser
        import re
        
        # Replace common HTML tags with appropriate formatting
        content = html_content.replace('<br>', '\n')
        content = content.replace('<br/>', '\n')
        content = content.replace('<br />', '\n')
        content = re.sub(r'<p[^>]*>', '\n', content)
        content = content.replace('</p>', '\n')
        content = re.sub(r'<li[^>]*>', '• ', content)
        content = content.replace('</li>', '\n')
        content = re.sub(r'<ul[^>]*>|</ul>', '', content)
        content = re.sub(r'<ol[^>]*>|</ol>', '', content)
        
        # Remove any remaining HTML tags
        content = re.sub(r'<[^>]+>', '', content)
        
        # Clean up whitespace
        content = re.sub(r'\n\s*\n', '\n\n', content)
        content = content.strip()
        
        return content
    
    def _build_terms(self):
        """Build terms and conditions section"""
        elements = []
        
        # Check if we have terms to display
        terms_to_display = []
        
        # First, try to get terms from the parameter passed to the constructor
        if self.terms:
            try:
                terms_to_display = list(Term.objects.filter(id__in=self.terms))
            except Exception as e:
                print(f"Error fetching terms by IDs: {e}")
        
        # Fallback: try to get terms from quotation.terms field (if it exists)
        if not terms_to_display and hasattr(self.quotation, 'terms') and self.quotation.terms:
            try:
                # Handle different formats of terms field
                if isinstance(self.quotation.terms, str):
                    # Parse comma-separated string
                    term_ids = [int(t.strip()) for t in self.quotation.terms.split(",") if t.strip().isdigit()]
                    terms_to_display = list(Term.objects.filter(id__in=term_ids))
                else:
                    # Assume it's a ManyToMany relationship
                    terms_to_display = list(self.quotation.terms.all())
            except Exception as e:
                print(f"Error fetching terms from quotation: {e}")
        
        # If we have terms to display, add them to the PDF
        if terms_to_display:
            elements.append(Paragraph("Terms & Conditions", self.heading_style))
            
            for term in terms_to_display:
                # Add term title
                elements.append(Paragraph(term.title, self.terms_heading_style))
                
                # Process term content
                content = ""
                if hasattr(term, 'content_html') and term.content_html:
                    content = self._clean_html_content(term.content_html)
                elif hasattr(term, 'content') and term.content:
                    content = str(term.content)
                
                if content:
                    # Split content into paragraphs and add each as a separate element
                    paragraphs = content.split('\n\n')
                    for para in paragraphs:
                        para = para.strip()
                        if para:
                            # Handle bullet points
                            if para.startswith('•'):
                                elements.append(Paragraph(para, self.terms_content_style))
                            else:
                                # Split on single newlines for line breaks within a paragraph
                                lines = para.split('\n')
                                for line in lines:
                                    line = line.strip()
                                    if line:
                                        elements.append(Paragraph(line, self.terms_content_style))
                
                # Add some space after each term
                elements.append(Spacer(1, 5 * mm))
        
        return elements
    
    def _build_footer(self):
        """Build footer section"""
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
    
    def generate(self):
        """Generate the complete PDF"""
        elements = []
        
        # Build all sections
        elements.extend(self._build_company_header())
        elements.extend(self._build_quotation_info())
        elements.extend(self._build_customer_info())
        elements.extend(self._build_items_table())
        elements.extend(self._build_totals())
        elements.extend(self._build_terms())
        elements.extend(self._build_footer())
        
        # Build PDF document
        self.doc.build(elements)
        
        # Get PDF content
        pdf = self.buffer.getvalue()
        self.buffer.close()
        
        return pdf