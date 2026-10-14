# BriefScrapr

BriefScrapr is a local web app that reads a text-based PDF project brief and extracts a structured project specification with a local Ollama model.

## What You Have To Do

1. Install Docker Desktop.
2. Start Docker Desktop.
3. Open PowerShell in this folder.
4. Run:

```powershell
docker compose up --build
```

5. In a second PowerShell window, pull the default model into Ollama:

```powershell
docker compose exec ollama ollama pull gpt-oss:20b
```

6. Open:

```text
http://localhost:8000
```

7. Upload a text-based PDF brief and click **Analyse brief**.

## Using A Different Ollama Model

Set `OLLAMA_MODEL` before starting the app:

```powershell
$env:OLLAMA_MODEL="llama3.1:8b"
docker compose up --build
```

Then pull that model:

```powershell
docker compose exec ollama ollama pull llama3.1:8b
```

## Local Python Run

If you already have Ollama running locally:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open `http://localhost:8000`.

## API

Health check:

```text
GET /health
```

Analyse a PDF:

```text
POST /api/briefs/analyse
```

The request must be `multipart/form-data` with a `file` field containing a PDF.
