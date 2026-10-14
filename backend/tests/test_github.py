import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from app.main import app
from app.api.routes import github


class GitHubTests(unittest.TestCase):
    def setUp(self):
        github.sessions.clear()
        github.pending.clear()
        self.client = TestClient(app)

    def authenticate(self):
        github.sessions["session"] = {"token": "server-only-token", "login": "tester", "csrf": "csrf",
                                      "expires": time.time() + 600, "issues": {}}
        self.client.cookies.set(github.COOKIE, "session")

    def test_session_never_returns_access_token(self):
        self.authenticate()
        response = self.client.get("/api/github/session")
        self.assertEqual(response.json()["login"], "tester")
        self.assertNotIn("server-only-token", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_login_uses_pkce_and_browser_bound_state(self):
        with patch.object(github, "GITHUB_CLIENT_ID", "client"), patch.object(github, "GITHUB_CLIENT_SECRET", "secret"):
            response = self.client.get("/api/github/login", follow_redirects=False)
        query = parse_qs(urlparse(response.headers["location"]).query)
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertIn(query["state"][0], github.pending)
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        with patch.object(github.httpx, "post") as exchange:
            response = self.client.get("/api/github/callback?state=wrong&code=code")
            self.assertEqual(response.status_code, 400)
            exchange.assert_not_called()

    def test_callback_exchanges_token_server_side(self):
        github.pending["state"] = {"verifier": "verifier", "expires": time.time() + 600}
        self.client.cookies.set("briefscrapr_oauth_state", "state")
        with patch.object(github.httpx, "post") as exchange, patch.object(github, "github_request", return_value={"login": "tester"}):
            exchange.return_value.json.return_value = {"access_token": "private-token"}
            response = self.client.get("/api/github/callback?state=state&code=code", follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertNotIn("private-token", response.text + str(response.headers))
        self.assertEqual(exchange.call_args.kwargs["data"]["code_verifier"], "verifier")
        self.assertNotIn("state", github.pending)
        self.assertTrue(self.client.get("/api/github/session").json()["authenticated"])

    def test_issue_creation_requires_auth_and_csrf(self):
        data = {"repository": "owner/repo", "issues": [{"title": "Build API"}]}
        self.assertEqual(self.client.post("/api/github/issues", json=data).status_code, 401)
        self.authenticate()
        with patch.object(github, "github_request") as remote:
            self.assertEqual(self.client.post("/api/github/issues", json=data).status_code, 403)
            remote.assert_not_called()

    def test_partial_retry_does_not_recreate_successful_issues(self):
        self.authenticate()
        repo = {"has_issues": True, "permissions": {"push": True}}
        data = {"repository": "owner/repo", "issues": [{"title": "Build API"}, {"title": "Write tests"}]}
        headers = {"X-CSRF-Token": "csrf"}
        with patch.object(github, "github_request", side_effect=[repo, {"html_url": "https://github.com/owner/repo/issues/1", "number": 1}, github.HTTPException(502, "Rate limited")]):
            result = self.client.post("/api/github/issues", json=data, headers=headers).json()
        self.assertEqual(len(result["created"]), 1)
        self.assertEqual(len(result["errors"]), 1)
        with patch.object(github, "github_request", side_effect=[repo, {"html_url": "https://github.com/owner/repo/issues/2", "number": 2}]) as remote:
            result = self.client.post("/api/github/issues", json=data, headers=headers).json()
        self.assertEqual(len(result["created"]), 2)
        self.assertEqual(remote.call_count, 2)  # repository check plus only the remaining issue

    def test_repositories_filter_and_paginate(self):
        self.authenticate()
        repos = [{"full_name": "owner/good", "has_issues": True, "private": False, "permissions": {"push": True}},
                 {"full_name": "owner/archived", "has_issues": True, "archived": True, "private": False, "permissions": {"push": True}}]
        with patch.object(github, "github_request", return_value=repos):
            result = self.client.get("/api/github/repositories?page=2").json()
        self.assertEqual(result["repositories"], [{"full_name": "owner/good", "private": False}])
        self.assertFalse(result["has_more"])


if __name__ == "__main__":
    unittest.main()
