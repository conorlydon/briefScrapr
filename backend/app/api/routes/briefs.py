from io import BytesIO

from fastapi import APIRouter, UploadFile, File

from services.pdf_parser import extract_text_from_pdf
from services.llm import analyse_brief


router = APIRouter()


@router.post("/briefs/analyse")
async def analyse_brief_endpoint(file: UploadFile = File(...)):
    contents = await file.read()

    pdf_file = BytesIO(contents)

    text = extract_text_from_pdf(pdf_file)

    analysis = analyse_brief(text)

    return {
        "filename": file.filename,
        "analysis": analysis.model_dump(),
    }