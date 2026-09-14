from fastapi import FastAPI

from app.api.routes.briefs import router as briefs_router


app = FastAPI(title="BriefScrapr")


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(briefs_router)