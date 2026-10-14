from io import BytesIO
import json
import logging

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import ValidationError
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from services.pdf_parser import extract_text_from_pdf
from services.llm import analyse_brief, analyse_brief_events


router = APIRouter()


async def read_brief(file: UploadFile) -> str:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    contents = await file.read()

    if not contents:
        raise HTTPException(status_code=400, detail="The uploaded PDF is empty.")

    pdf_file = BytesIO(contents)

    try:
        text = extract_text_from_pdf(pdf_file)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not read text from this PDF.") from exc

    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail="No selectable text was found in this PDF. Try a text-based PDF rather than a scanned image.",
        )

    return text


@router.post("/briefs/analyse")
async def analyse_brief_endpoint(file: UploadFile = File(...)):
    text = await read_brief(file)
    try:
        analysis = await run_in_threadpool(analyse_brief, text)
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail="The model returned incomplete or invalid analysis. Please try again.",
        ) from exc

    return {
        "filename": file.filename,
        "analysis": analysis.model_dump(),
    }


def stream_analysis(text: str, filename: str):
    try:
        for event in analyse_brief_events(text):
            if event["type"] == "complete":
                event["filename"] = filename
                event["source_text"] = text
            yield json.dumps(event) + "\n"
    except ValidationError:
        yield json.dumps({"type": "error", "message":
                          "The model returned incomplete or invalid analysis. Please try again."}) + "\n"
    except Exception:
        logging.getLogger("uvicorn.error").exception("Brief analysis failed")
        yield json.dumps({"type": "error", "message":
                          "Analysis failed. Check that Ollama is running and try again."}) + "\n"


@router.post("/briefs/analyse/stream")
async def analyse_brief_stream(file: UploadFile = File(...)):
    text = await read_brief(file)
    return StreamingResponse(
        stream_analysis(text, file.filename),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
