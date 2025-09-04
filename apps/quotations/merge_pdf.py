import os
import io
import requests
from datetime import datetime
import logging

from django.core.files.base import ContentFile
from storages.backends.gcloud import GoogleCloudStorage

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

import PyPDF2

logger = logging.getLogger(__name__)


def merge_pdfs_from_urls(pdf_urls, save_folder='merged_pdfs'):
    try:
        merger = PyPDF2.PdfMerger()
        successful_urls = []

        for url in pdf_urls:
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()  # raises HTTPError for bad status
                pdf_file = io.BytesIO(response.content)
                # Attempt to read PDF to make sure it's valid
                PyPDF2.PdfReader(pdf_file)
                pdf_file.seek(0)
                merger.append(pdf_file)
                successful_urls.append(url)
            except Exception as e:
                logger.warning(f"Skipping PDF {url} due to error: {e}")

        if not successful_urls:
            raise Exception("No valid PDFs to merge.")

        # Write merged PDF to in-memory bytes
        merged_pdf_bytes = io.BytesIO()
        merger.write(merged_pdf_bytes)
        merger.close()
        merged_pdf_bytes.seek(0)

        # Generate a filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_name = f'merged_{timestamp}.pdf'
        file_path = os.path.join(save_folder, file_name)

        # Save to Firebase (Google Cloud Storage)
        gcs_storage = GoogleCloudStorage()
        saved_path = gcs_storage.save(file_path, ContentFile(merged_pdf_bytes.read()))
        pdf_url = gcs_storage.url(saved_path)

        logger.info(f"Merged PDF uploaded successfully: {pdf_url}")
        return pdf_url

    except Exception as e:
        logger.error(f"Error merging PDFs: {e}", exc_info=True)
        raise


class MergePDFsAPIView(APIView):
    def post(self, request):
        pdf_urls = request.data.get("pdf_urls")
        if not pdf_urls or not isinstance(pdf_urls, list):
            return Response(
                {"error": "pdf_urls must be a list of valid PDF URLs."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            merged_pdf_url = merge_pdfs_from_urls(pdf_urls)
            return Response({
                "message": "PDFs merged successfully",
                "final_url": merged_pdf_url,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Failed to merge PDFs: {e}", exc_info=True)
            return Response(
                {"error": "Failed to merge PDFs", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
