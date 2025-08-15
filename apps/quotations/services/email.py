from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
import base64
from qms import settings


def send_quotation_email(quotation, to_email: str, subject: str, html_body: str, pdf_path: str) -> str:
    sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
    with open(pdf_path, 'rb') as f:
        data = f.read()
    encoded = base64.b64encode(data).decode()

    message = Mail(
        from_email=settings.DEFAULT_FROM_EMAIL,
        to_emails=to_email,
        subject=subject,
        html_content=html_body,
    )
    attachment = Attachment(
        FileContent(encoded),
        FileName(f"{quotation.quotation_number}.pdf"),
        FileType('application/pdf'),
        Disposition('attachment'),
    )
    message.attachment = attachment
    response = sg.send(message)
    # Try to fetch SendGrid Message-ID from headers (may vary)
    provider_message_id = response.headers.get('X-Message-Id') or response.headers.get('X-Message-ID') or ''
    return provider_message_id

