from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.briefs import router as briefs_router
from app.api.routes.github import router as github_router
from app.config import FRONTEND_DIR


app = FastAPI(title="BriefScrapr")


@app.middleware("http")
async def frontend_cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith(("/assets/", "/api/github/")):
        response.headers["Cache-Control"] = "no-store"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(briefs_router, prefix="/api")
app.include_router(github_router, prefix="/api")


app.mount("/assets", StaticFiles(directory=f"{FRONTEND_DIR}/assets"), name="assets")


@app.get("/")
def frontend():
    return FileResponse(f"{FRONTEND_DIR}/index.html")
