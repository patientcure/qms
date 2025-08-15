from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from qms import settings


SCOPES = ['https://www.googleapis.com/auth/drive.file']

def _drive_service():
    creds = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_DRIVE_CREDENTIALS_FILE, scopes=SCOPES
    )
    return build('drive', 'v3', credentials=creds)

def upload_pdf_to_drive(local_path: str, file_name: str):
    service = _drive_service()
    file_metadata = {
        'name': file_name,
        'parents': [settings.GOOGLE_DRIVE_PARENT_FOLDER_ID],  # single shared folder
    }
    media = MediaFileUpload(local_path, mimetype='application/pdf')
    file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
    return file['id'], file['webViewLink']
