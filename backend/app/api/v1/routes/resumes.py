from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.app.services.resume import pdfextractor


router = APIRouter()


@router.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=415,
            detail="Unsupported file format. Please upload a valid PDF document.",
        )

    try:
        pdf_bytes = await file.read()

        if len(pdf_bytes) == 0:
            raise HTTPException(
                status_code=400,
                detail="The uploaded file stream is empty.",
            )

        parsed_resume_data = pdfextractor.extract_resume_details(pdf_bytes)

        return parsed_resume_data

    except HTTPException as error:
        raise HTTPException(
            status_code=500,
            detail=f"Internal Processing Error: {str(error)}",
        )
