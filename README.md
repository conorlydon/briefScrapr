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
docker compose exec ollama ollama pull qwen2.5:0.5b
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

## Editing, verification, and export

Analysis processes the entire extracted text in overlapping sections and shows live progress.
Open **Compare with extracted brief text** to check each part of the source against the plan.
Edit the title, summary, and category lists (one item per line), then click **Download Markdown**.
The combined result has no five-item limit. The small model can still omit or misclassify facts;
compare its output with the source before treating the plan as complete.
Drafts are saved in this browser so they survive the GitHub sign-in redirect.

## GitHub OAuth setup

1. Register an OAuth App at https://github.com/settings/developers (OAuth Apps → New OAuth App).
2. Set Homepage URL to `http://localhost:8000`.
3. Set Authorization callback URL to `http://localhost:8000/api/github/callback`.
4. Copy `.env.example` to `.env` and fill in `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` locally.
   Do not commit `.env` or paste the secret into chat.
5. Run `docker compose up -d --build backend` and refresh the page.
6. Sign in with GitHub, choose a repository, preview requirements as issues, edit the titles and bodies,
   select the ones you want, and click **Create selected issues**. No issues are created during analysis or preview.

The default `public_repo` scope supports public repositories. Set `GITHUB_SCOPE=repo` and sign in again
if private repositories are required; that scope grants broader repository access.
Only writable, non-archived repositories with issues enabled are listed. If deploying elsewhere,
set `APP_URL` to the site's HTTPS origin and register the matching callback URL.

OAuth uses state validation and PKCE. Access tokens stay in server memory; the browser receives an
HttpOnly session cookie and a CSRF token. Sessions expire after eight hours and are cleared when
the backend restarts. This is a single-worker local MVP; persistent multi-worker sessions are not implemented.
Successful issue creations are remembered during the session to prevent duplicates on partial retries.
If a network timeout makes creation uncertain, check the repository before retrying.
Disconnect removes the local session; revoke the app's access in GitHub Settings to revoke authorization.

GitHub reference: https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps

## Checks

```powershell
docker compose exec -T backend python -m unittest discover -s tests -v
node frontend/tests/plan.test.mjs
```

The GitHub tests use mocked responses and do not create real issues. A live OAuth test requires
your app registration, credentials, and browser authorization.
