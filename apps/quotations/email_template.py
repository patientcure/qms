# apps/quotations/email_templates.py

def mytemplate(quotation):
    customer = quotation.customer

    subject = f"Quotation #{quotation.quotation_number} - {customer.company_name or customer.name}"

    plain_text = (
        f"Dear {customer.name},\n\n"
        f"Please find attached the quotation #{quotation.quotation_number}.\n\n"
        f"Company: {customer.company_name or 'N/A'}\n"
        f"Total Amount: {quotation.currency} {quotation.total:,.2f}\n"
        f"Discount: {quotation.discount or 0} ({quotation.discount_type})\n"
        f"Subtotal: {quotation.currency} {quotation.subtotal:,.2f}\n"
        f"Tax Rate: {quotation.tax_rate}%\n\n"
        f"We appreciate your business and look forward to serving you.\n\n"
        f"Best Regards,\n"
        f"{quotation.created_by.get_full_name() if quotation.created_by else 'Our Team'}"
    )

    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color:#2c3e50;">Quotation #{quotation.quotation_number}</h2>
        <p>Dear {customer.name},</p>
        <p>
          Please find attached your quotation details. Below is a quick summary:
        </p>
        <table style="border-collapse: collapse; width: 100%; margin: 20px 0;">
          <tr>
            <td style="border: 1px solid #ccc; padding: 8px;"><b>Company</b></td>
            <td style="border: 1px solid #ccc; padding: 8px;">{customer.company_name or 'N/A'}</td>
          </tr>
          <tr>
            <td style="border: 1px solid #ccc; padding: 8px;"><b>Subtotal</b></td>
            <td style="border: 1px solid #ccc; padding: 8px;">{quotation.currency} {quotation.subtotal:,.2f}</td>
          </tr>
          <tr>
            <td style="border: 1px solid #ccc; padding: 8px;"><b>Discount</b></td>
            <td style="border: 1px solid #ccc; padding: 8px;">{quotation.discount or 0} ({quotation.discount_type})</td>
          </tr>
          <tr>
            <td style="border: 1px solid #ccc; padding: 8px;"><b>Tax Rate</b></td>
            <td style="border: 1px solid #ccc; padding: 8px;">{quotation.tax_rate}%</td>
          </tr>
          <tr>
            <td style="border: 1px solid #ccc; padding: 8px;"><b>Total</b></td>
            <td style="border: 1px solid #ccc; padding: 8px;"><b>{quotation.currency} {quotation.total:,.2f}</b></td>
          </tr>
        </table>
        <p>
          We appreciate your business and look forward to serving you.
        </p>
        <p>
          Best Regards,<br/>
          {quotation.created_by.get_full_name() if quotation.created_by else 'Our Team'}
        </p>
      </body>
    </html>
    """

    return subject, plain_text, html_content
