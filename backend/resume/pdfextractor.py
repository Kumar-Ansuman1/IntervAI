"""Compatibility imports for the relocated resume parser service."""

from backend.app.services.resume.pdfextractor import (
    extract_resume_details,
    extract_text_from_pdf,
)

__all__ = ["extract_resume_details", "extract_text_from_pdf"]
