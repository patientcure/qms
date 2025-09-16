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
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Frame, PageTemplate
from .models import TermsAndConditions as Term
from django.contrib.staticfiles import finders


class QuotationPDFGenerator:
    def __init__(self, quotation, items_data, company_profile=None, terms=None):
        self.quotation = quotation
        self.items_data = items_data
        self.company = company_profile
        self.terms = terms or []
        self.styles = getSampleStyleSheet()
        self.buffer = io.BytesIO()

        # Margins adjusted for letterhead - increased to ensure content doesn't overlap
        self.doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=20 * mm, 
            leftMargin=20 * mm,
            topMargin=50 * mm,  # Increased for header
            bottomMargin=50 * mm  # Increased for footer
        )
        
        # Color definitions
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
        # Create frame for content area
        frame = Frame(
            self.doc.leftMargin, 
            self.doc.bottomMargin,
            self.doc.width, 
            self.doc.height,
            id='normal',
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0
        )
        
        # Create page template with header/footer for first page
        first_page_template = PageTemplate(
            id='firstPage', 
            frames=[frame],
            onPage=self._draw_header_footer
        )
        
        # Create page template with header/footer for later pages
        later_page_template = PageTemplate(
            id='laterPages', 
            frames=[frame],
            onPage=self._draw_header_footer
        )
        
        # Add both templates
        self.doc.addPageTemplates([first_page_template, later_page_template])

    def _draw_header_footer(self, canvas, doc):
        """Draw header and footer on every page"""
        canvas.saveState()
        
        # Draw header
        self._draw_header(canvas)
        
        # Draw footer
        self._draw_footer(canvas)
        
        # Add page number
        self._add_page_number(canvas, doc)
        
        canvas.restoreState()

    def _draw_header(self, canvas):
        """Draw the exact header from letterhead"""
        # Get page dimensions
        page_width, page_height = A4
        
        try:
            # Draw Godrej logo (top right)
            godrej_path = finders.find("quotations/assets/godrej.jpeg")
            if godrej_path:
                godrej_logo = ImageReader(godrej_path)
                # Position: top-right corner with margin
                logo_x = page_width - 60 * mm
                logo_y = page_height - 25 * mm
                canvas.drawImage(
                    godrej_logo, 
                    logo_x, logo_y,
                    width=40 * mm, 
                    height=15 * mm, 
                    preserveAspectRatio=True, 
                    mask='auto'
                )
        except Exception as e:
            print(f"Error loading Godrej logo: {e}")

        # Company name (top left, bold)
        canvas.setFont("Helvetica-Bold", 16)
        canvas.setFillColor(self.header_blue)
        canvas.drawString(20 * mm, page_height - 20 * mm, "N.K. Prosales Private Limited")

        # Company address line 1
        canvas.setFont("Helvetica", 10)
        canvas.drawString(20 * mm, page_height - 26 * mm, "39/1, Acharya puri, Gurgaon-122001")
        
        # Company contact line 2
        canvas.drawString(20 * mm, page_height - 30 * mm, "Ph-0124 - 2306638, Email: neelamgt2004@yahoo.co.in")

        # Header separator line
        canvas.setStrokeColor(self.separator_gray)
        canvas.setLineWidth(1.0)
        canvas.line(20 * mm, page_height - 32 * mm, page_width - 20 * mm, page_height - 32 * mm)

        # Products line (smaller font)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(self.medium_gray)
        canvas.drawString(20 * mm, page_height - 36 * mm,
            "Wholesale Dealer of: GODREJ & Boyce Mfg. Co. Ltd., Carysil, Eureka Forbes")


    def _draw_footer(self, canvas):
        """Draw the exact footer from letterhead"""
        page_width, page_height = A4
        
        # Footer separator line
        try:
            # Eureka Forbes logo (left side)
            eureka_path = finders.find("quotations/assets/eureka.jpeg")
            if eureka_path:
                eureka_logo = ImageReader(eureka_path)
                canvas.drawImage(
                    eureka_logo, 
                    60 * mm, 25 * mm, 
                    width=30 * mm, 
                    height=12 * mm,
                    preserveAspectRatio=True, 
                    mask='auto'
                )
        except Exception as e:
            print(f"Error loading Eureka logo: {e}")

        try:
            # Carysil logo (right side)
            carysil_path = finders.find("quotations/assets/carysil.jpeg")
            if carysil_path:
                carysil_logo = ImageReader(carysil_path)
                canvas.drawImage(
                    carysil_logo, 
                    120 * mm, 25 * mm, 
                    width=30 * mm, 
                    height=12 * mm,
                    preserveAspectRatio=True, 
                    mask='auto'
                )
        except Exception as e:
            print(f"Error loading Carysil logo: {e}")

        #Footer Seperator Line
        canvas.setStrokeColor(self.separator_gray)
        canvas.setLineWidth(1.0)
        canvas.line(20 * mm, 21 * mm, page_width - 20 * mm, 21 * mm)


        # Product descriptions (footer text)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(self.dark_gray)
        
        # Line 1: Godrej products
        canvas.drawCentredString(
            page_width / 2, 18 * mm,
            "Godrej: Modular Office Furniture Systems and Storage Products • Physical Electronics & Premises Security Equipment • Optimiser • Heavy Duty Indl. Rack."
        )
        
        # Line 2: Eureka Forbes products
        canvas.drawCentredString(
            page_width / 2, 14 * mm,
            "Eureka Forbes: Commercial & Industrial Products • Vacuum Cleaner • Scrubber Drier • Sweeper • High Jet Pressure • Water Cooler."
        )
        
        # Line 3: Carysil products
        canvas.drawCentredString(
            page_width / 2, 10 * mm,
            "Carysil: Sinks • Faucet • Chimney • Hobs etc."
        )

    def _add_page_number(self, canvas, doc):
        """Add page number"""
        page_num = canvas.getPageNumber()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(self.medium_gray)
        # Position page number in top right, below header
        canvas.drawRightString(A4[0] - 20 * mm, A4[1] - 46 * mm, f"Page {page_num}")

    def _to_decimal(self, value, precision='0.01'):
        if value is None: 
            return Decimal('0')
        try:
            return Decimal(str(value)).quantize(Decimal(precision), rounding=ROUND_HALF_UP)
        except (ValueError, TypeError):
            return Decimal('0')

    def _format_currency(self, value):
        return f"Rs. {value:,.2f}"

    def _clean_html_content(self, content):
        """Clean HTML content for terms"""
        if not content:
            return ""
        # Basic HTML cleaning - you may need to expand this
        content = re.sub(r'<[^>]+>', '', content)
        return content.strip()

    def _define_styles(self):
        """Define paragraph styles"""
        self.title_style = ParagraphStyle(
            'Title', 
            parent=self.styles['Heading1'], 
            fontSize=24,
            fontName='Helvetica-Bold', 
            spaceAfter=20, 
            alignment=TA_LEFT, 
            textColor=self.primary_blue
        )
        
        self.company_name_style = ParagraphStyle(
            'CompanyName', 
            parent=self.styles['Heading1'], 
            fontSize=20,
            fontName='Helvetica-Bold', 
            spaceAfter=8, 
            alignment=TA_RIGHT, 
            textColor=self.primary_blue
        )
        
        self.section_heading_style = ParagraphStyle(
            'SectionHeading', 
            parent=self.styles['Heading2'], 
            fontSize=14,
            fontName='Helvetica-Bold', 
            spaceAfter=12, 
            spaceBefore=16, 
            textColor=colors.black
        )
        
        self.normal_style = ParagraphStyle(
            'Normal', 
            parent=self.styles['Normal'], 
            fontSize=10,
            textColor=self.dark_gray, 
            leading=14
        )
        
        self.right_style = ParagraphStyle(
            'Right', 
            parent=self.styles['Normal'], 
            fontSize=10,
            alignment=TA_RIGHT, 
            textColor=self.dark_gray
        )
        
        self.small_text_style = ParagraphStyle(
            'SmallText', 
            parent=self.styles['Normal'], 
            fontSize=9,
            textColor=self.medium_gray, 
            alignment=TA_RIGHT, 
            leading=12
        )
        
        self.terms_heading_style = ParagraphStyle(
            'TermsHeading', 
            parent=self.styles['Heading3'], 
            fontSize=11,
            fontName='Helvetica-Bold', 
            spaceAfter=6, 
            spaceBefore=6, 
            textColor=colors.black
        )
        
        self.terms_content_style = ParagraphStyle(
            'TermsContent', 
            parent=self.styles['Normal'], 
            fontSize=9,
            spaceAfter=6, 
            textColor=self.dark_gray, 
            leading=12
        )
        
        self.footer_style = ParagraphStyle(
            'Footer', 
            parent=self.styles['Normal'], 
            fontSize=8,
            alignment=TA_CENTER, 
            textColor=self.medium_gray
        )

    def _build_company_header(self):
        """Build the quotation header section"""
        # Left side - Quotation title and info
        left_content = [Paragraph("QUOTATION", self.title_style)]
        
        quotation_info = f"<b>Quotation No:</b> {self.quotation.quotation_number}<br/>"
        quotation_info += f"<b>Date:</b> {datetime.now().strftime('%d/%m/%Y')}<br/>"
        
        if self.quotation.follow_up_date:
            quotation_info += f"<b>Valid Until:</b> {self.quotation.follow_up_date.strftime('%d-%m-%Y')}"
            
        left_content.append(Paragraph(quotation_info, self.normal_style))
        
        # Right side - Company GST info (if available)
        right_content = []
        if self.company and hasattr(self.company, 'gst_number') and self.company.gst_number:
            company_details = f"<b>GST:</b> {self.company.gst_number}"
            right_content.append(Paragraph(company_details, self.small_text_style))
        
        # Create header table
        header_table = Table(
            [[left_content, right_content]], 
            colWidths=[120 * mm, 50 * mm], 
            style=[('VALIGN', (0, 0), (-1, -1), 'TOP')]
        )
        
        return [header_table, Spacer(1, 8 * mm)]

    def _build_customer_info(self):
        """Build customer information section"""
        customer = self.quotation.customer
        customer_info = f"<b>Customer Name:</b> {customer.name}<br/>"
        
        if hasattr(customer, 'email') and customer.email: 
            customer_info += f"<b>Email:</b> {customer.email}<br/>"
        if hasattr(customer, 'phone') and customer.phone: 
            customer_info += f"<b>Phone:</b> {customer.phone}<br/>"
        if hasattr(customer, 'company_name') and customer.company_name: 
            customer_info += f"<b>Company:</b> {customer.company_name}<br/>"
        if hasattr(customer, 'gst_number') and customer.gst_number: 
            customer_info += f"<b>GST:</b> {customer.gst_number}<br/>"
        if hasattr(customer, 'primary_address') and customer.primary_address: 
            customer_info += f"<b>Address:</b> {customer.primary_address}"
        
        customer_table = Table(
            [[Paragraph(customer_info, self.normal_style)]], 
            colWidths=[170 * mm]
        )
        customer_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), self.light_gray), 
            ('GRID', (0, 0), (-1, -1), 0.5, self.border_gray), 
            ('PADDING', (0, 0), (-1, -1), 12)
        ]))
        
        return [
            Paragraph("Bill To:", self.section_heading_style), 
            customer_table, 
            Spacer(1, 8 * mm)
        ]

    def _build_items_table(self):
        """Build items table with calculations"""
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
                Paragraph(str(idx), self.normal_style), 
                Paragraph(description, self.normal_style),
                Paragraph(str(quantity), self.normal_style), 
                Paragraph(self._format_currency(unit_price), self.right_style),
                Paragraph(f"{item_discount_percent:.2f}%", self.right_style), 
                Paragraph(self._format_currency(net_amount), self.right_style),
            ]
            table_data.append(row)

        # Create table
        item_table = Table(
            table_data, 
            colWidths=[12*mm, 68*mm, 15*mm, 25*mm, 20*mm, 30*mm], 
            repeatRows=1
        )
        
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
        
        calculated_totals = {
            "subtotal": subtotal, 
            "total_item_discount": total_item_discount
        }
        
        return [item_table, Spacer(1, 8*mm)], calculated_totals

    def _build_totals(self, totals):
        """Build totals section with tax applied after discount"""
        subtotal = self._to_decimal(totals.get("subtotal", 0))
        total_item_discount = self._to_decimal(totals.get("total_item_discount", 0))
        
        # Step 1: Apply item discounts
        subtotal_after_item_disc = subtotal - total_item_discount

        # Step 2: Apply overall discount (on subtotal after item discounts)
        overall_discount_value = self._to_decimal(getattr(self.quotation, 'discount', 0))
        discount_label = 'Discount:'
        overall_discount_amount = Decimal('0.00')
        if overall_discount_value > 0:
            if getattr(self.quotation, 'discount_type', 'percentage') == 'amount':
                overall_discount_amount = overall_discount_value
            else:
                overall_discount_amount = subtotal_after_item_disc * (overall_discount_value / 100)
                discount_label = f'Discount ({overall_discount_value}%):'
        
        subtotal_after_all_discounts = subtotal_after_item_disc - overall_discount_amount

        # Step 3: Apply tax on net amount (after all discounts)
        tax_rate = self._to_decimal(getattr(self.quotation, 'tax_rate', 0))
        tax_amount = Decimal('0.00')
        tax_label = 'Tax:'
        if tax_rate > 0:
            tax_amount = subtotal_after_all_discounts * (tax_rate / 100)
            tax_label = f'Tax ({tax_rate}%):'
        
        # Step 4: Final grand total
        grand_total = subtotal_after_all_discounts + tax_amount

        totals_data = [
            ['Subtotal:', self._format_currency(subtotal_after_item_disc)],
            [discount_label, f"- {self._format_currency(overall_discount_amount)}"],
            [tax_label, self._format_currency(tax_amount)],
            ['Total Amount:', self._format_currency(grand_total)],
        ]
        
        totals_table = Table(totals_data, colWidths=[40*mm, 40*mm])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'), 
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, -1), (-1, -1), self.primary_blue), 
            ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.black),
            ('TOPPADDING', (0, -1), (-1, -1), 8),
        ]))

        summary_container = Table(
            [[totals_table]], 
            colWidths=[170 * mm], 
            style=[('ALIGN', (0, 0), (0, 0), 'RIGHT')]
        )
        
        return [summary_container, Spacer(1, 10*mm)]

        
    def _build_terms(self):
        """Build terms and conditions section"""
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

    def _build_footer(self):
        """Build document footer"""
        footer_table = Table([
            [
                Paragraph("Thank you for your business!", self.normal_style), 
                Paragraph("Digitally Signed <br/>Admin Authorized", self.right_style)
            ]
        ], colWidths=[85 * mm, 85 * mm])
        
        return [Spacer(1, 15 * mm), footer_table]

    def generate(self):
        """Generate the complete PDF"""
        elements = []
        
        # Add a NextPageTemplate directive to ensure our template is used
        from reportlab.platypus import NextPageTemplate
        elements.append(NextPageTemplate('firstPage'))
        
        # Build all sections
        elements.extend(self._build_company_header())
        elements.extend(self._build_customer_info())
        
        item_elements, calculated_totals = self._build_items_table()
        elements.extend(item_elements)
        elements.extend(self._build_totals(calculated_totals))
        elements.extend(self._build_terms())
        elements.extend(self._build_footer())
        
        # Build the document with explicit template usage
        self.doc.build(elements, onFirstPage=self._draw_header_footer, onLaterPages=self._draw_header_footer)
        
        # Get PDF content
        pdf = self.buffer.getvalue()
        self.buffer.close()
        
        return pdf