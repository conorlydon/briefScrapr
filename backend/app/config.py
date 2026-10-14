import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
FRONTEND_DIR = os.getenv("FRONTEND_DIR", str(PROJECT_ROOT / "frontend"))
APP_URL = os.getenv("APP_URL", "http://localhost:8000").rstrip("/")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GITHUB_SCOPE = os.getenv("GITHUB_SCOPE", "public_repo")
