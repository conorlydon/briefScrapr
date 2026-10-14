"""Local MVP OAuth sessions: tokens stay on the server and expire after eight hours."""
import base64
import hashlib
import secrets
import threading
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.config import APP_URL, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET, GITHUB_SCOPE

router = APIRouter(prefix="/github")
pending = {}
sessions = {}
lock = threading.RLock()
CALLBACK = APP_URL + "/api/github/callback"
COOKIE = "briefscrapr_session"


def cleanup():
    now = time.time()
    for collection in (pending, sessions):
        for key in list(collection):
            if collection[key]["expires"] <= now:
                del collection[key]


def session_for(request: Request):
    with lock:
        cleanup()
        session = sessions.get(request.cookies.get(COOKIE))
        if not session:
            raise HTTPException(401, "Sign in with GitHub first.")
        return session


def check_csrf(request: Request, session):
    if not secrets.compare_digest(request.headers.get("X-CSRF-Token", ""), session["csrf"]):
        raise HTTPException(403, "Invalid session request. Refresh and try again.")


def github_request(token, method, path, **kwargs):
    try:
        response = httpx.request(method, "https://api.github.com" + path,
                                headers={"Authorization": f"Bearer {token}",
                                         "Accept": "application/vnd.github+json"},
                                timeout=25, **kwargs)
    except httpx.RequestError as exc:
        raise HTTPException(502, "Could not reach GitHub. Please try again.") from exc
    if response.status_code >= 400:
        messages = {401: "GitHub sign-in expired. Sign in again.",
                    403: "GitHub denied access or its rate limit was reached.",
                    404: "Repository not found or access denied.",
                    410: "Issues are disabled for this repository.",
                    422: "GitHub rejected this issue. Check its title and repository settings."}
        raise HTTPException(502, messages.get(response.status_code, "GitHub could not complete the request."))
    return response.json()


@router.get("/session")
def get_session(request: Request):
    try:
        session = session_for(request)
    except HTTPException:
        return {"configured": bool(GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET), "authenticated": False}
    return {"configured": True, "authenticated": True, "login": session["login"],
            "csrf_token": session["csrf"]}


@router.get("/login")
def login():
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(503, "Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET in .env first.")
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    with lock:
        cleanup()
        if len(pending) >= 1000:
            raise HTTPException(429, "Too many sign-in attempts. Try again later.")
        pending[state] = {"verifier": verifier, "expires": time.time() + 600}
    response = RedirectResponse("https://github.com/login/oauth/authorize?" + urlencode({
        "client_id": GITHUB_CLIENT_ID, "redirect_uri": CALLBACK, "scope": GITHUB_SCOPE,
        "state": state, "code_challenge": challenge, "code_challenge_method": "S256"}))
    response.set_cookie("briefscrapr_oauth_state", state, max_age=600, httponly=True,
                        secure=APP_URL.startswith("https://"), samesite="lax", path="/api/github")
    return response


@router.get("/callback")
def callback(request: Request, code: str = "", state: str = "", error: str = ""):
    with lock:
        cleanup()
        cookie_state = request.cookies.get("briefscrapr_oauth_state", "")
        if not state or not secrets.compare_digest(state, cookie_state):
            raise HTTPException(400, "GitHub sign-in state mismatch. Start sign-in again.")
        attempt = pending.pop(state, None)
    if not attempt or not code or error:
        return RedirectResponse("/?github=failed", status_code=303)
    try:
        response = httpx.post("https://github.com/login/oauth/access_token",
                              headers={"Accept": "application/json"}, timeout=25,
                              data={"client_id": GITHUB_CLIENT_ID, "client_secret": GITHUB_CLIENT_SECRET,
                                    "code": code, "redirect_uri": CALLBACK,
                                    "code_verifier": attempt["verifier"]})
        response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            return RedirectResponse("/?github=failed", status_code=303)
        user = github_request(token, "GET", "/user")
    except (httpx.HTTPError, HTTPException, ValueError):
        return RedirectResponse("/?github=failed", status_code=303)
    session_id = secrets.token_urlsafe(32)
    with lock:
        old_id = request.cookies.get(COOKIE)
        sessions.pop(old_id, None)
        sessions[session_id] = {"token": token, "login": user["login"], "csrf": secrets.token_urlsafe(32),
                                "expires": time.time() + 28800, "issues": {}}
    response = RedirectResponse("/?github=connected", status_code=303)
    response.set_cookie(COOKIE, session_id, max_age=28800, httponly=True,
                        secure=APP_URL.startswith("https://"), samesite="lax")
    response.delete_cookie("briefscrapr_oauth_state", path="/api/github")
    return response


@router.post("/logout")
def logout(request: Request, response: Response):
    session = session_for(request)
    check_csrf(request, session)
    with lock:
        sessions.pop(request.cookies.get(COOKIE), None)
    response.delete_cookie(COOKIE)
    return {"ok": True}


@router.get("/repositories")
def repositories(request: Request, page: int = 1):
    if page < 1:
        raise HTTPException(400, "Invalid page.")
    session = session_for(request)
    repos = github_request(session["token"], "GET", "/user/repos",
                           params={"per_page": 100, "page": page, "sort": "updated"})
    return {"repositories": [{"full_name": repo["full_name"], "private": repo["private"]}
                             for repo in repos if repo.get("has_issues") and not repo.get("archived")
                             and (GITHUB_SCOPE == "repo" or not repo.get("private"))
                             and repo.get("permissions", {}).get("push")], "has_more": len(repos) == 100}


class Issue(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    body: str = Field(default="", max_length=10000)


class IssueBatch(BaseModel):
    repository: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+$")
    issues: list[Issue] = Field(min_length=1, max_length=50)


@router.post("/issues")
def create_issues(batch: IssueBatch, request: Request):
    session = session_for(request)
    check_csrf(request, session)
    if batch.repository.split("/")[1] in (".", ".."):
        raise HTTPException(400, "Invalid repository name.")
    created, errors = [], []
    # Keep successful creations so a partial retry cannot duplicate them in this session.
    with lock:
        issue_lock = session.setdefault("issue_lock", threading.Lock())
    with issue_lock:
        repo = github_request(session["token"], "GET", f"/repos/{batch.repository}")
        if not repo.get("has_issues") or repo.get("archived") or not repo.get("permissions", {}).get("push"):
            raise HTTPException(403, "Choose a repository with write access and issues enabled.")
        for issue in batch.issues:
            title = issue.title.strip()
            if not title:
                errors.append({"title": issue.title, "message": "Issue title cannot be blank."})
                continue
            key = hashlib.sha256((batch.repository + "\0" + title + "\0" + issue.body).encode()).hexdigest()
            if key in session["issues"]:
                created.append(session["issues"][key])
                continue
            try:
                result = github_request(session["token"], "POST", f"/repos/{batch.repository}/issues",
                                        json={"title": title, "body": issue.body})
            except HTTPException as exc:
                errors.append({"title": title, "message": exc.detail})
                break
            entry = {"title": title, "url": result["html_url"], "number": result["number"]}
            session["issues"][key] = entry
            created.append(entry)
    return {"created": created, "errors": errors}
