"""Local-only TikTok Sandbox OAuth and explicit publish server."""

from __future__ import annotations

import os
import secrets
import time
from dataclasses import dataclass
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Mapping
from urllib.parse import parse_qs, urlparse

import oauth
import templates
import tiktok_api
import video


HOST = "127.0.0.1"
PORT = 3455
REDIRECT_URI = "http://127.0.0.1:3455/callback/"
SCOPES = ("user.info.basic", "video.publish")


@dataclass
class Response:
    status: int
    body: str = ""
    headers: dict[str, str] | None = None

    def __post_init__(self):
        self.headers = dict(self.headers or {})
        self.headers.setdefault("Cache-Control", "no-store")
        self.headers.setdefault("Pragma", "no-cache")
        self.headers.setdefault("Content-Type", "text/html; charset=utf-8")


@dataclass
class Dependencies:
    exchange_code: Callable
    get_user_info: Callable
    get_creator_info: Callable
    initialize_post: Callable
    upload_video: Callable
    get_post_status: Callable
    probe_video: Callable
    validate_video: Callable


def default_dependencies() -> Dependencies:
    return Dependencies(
        lambda config, code, verifier: oauth.exchange_code(config, code, verifier),
        tiktok_api.get_user_info, tiktok_api.get_creator_info,
        tiktok_api.initialize_post, tiktok_api.upload_video, tiktok_api.get_post_status,
        video.probe_video, video.validate_video,
    )


class App:
    def __init__(self, config: Mapping[str, str], deps: Dependencies | None = None):
        self.config = dict(config)
        self.deps = deps or default_dependencies()
        self.sessions: dict[str, dict] = {}

    def handle(self, method: str, path: str, *, query=None, form=None, cookies=None) -> Response:
        query, form, cookies = query or {}, form or {}, cookies or {}
        try:
            if method == "GET" and path == "/":
                return Response(200, templates.page("TikTok Sandbox Test", "<a href='/login'>Authorize Target User</a>"))
            if method == "GET" and path == "/login":
                return self._login()
            if method == "GET" and path == "/callback/":
                return self._callback(query, cookies)
            if method == "GET" and path == "/authorized":
                return self._authorized_page(cookies)
            if method == "POST" and path == "/review":
                return self._review(form, cookies)
            if path == "/publish" and method != "POST":
                return Response(405, templates.safe_error("method_not_allowed"), {"Allow": "POST"})
            if method == "POST" and path == "/publish":
                return self._publish(form, cookies)
            if method == "GET" and path == "/status":
                return self._status(cookies)
            return Response(404, templates.safe_error("not_found"))
        except (oauth.OAuthError, tiktok_api.ApiError, video.VideoError) as error:
            return Response(400, templates.safe_error(str(error)))
        except Exception:
            return Response(500, templates.safe_error("internal_error"))

    def _session(self, cookies):
        sid = str(cookies.get("tc_session", ""))
        session = self.sessions.get(sid)
        if not session or time.time() > session["expires_at"]:
            raise oauth.OAuthError("session_missing")
        return session

    def _login(self):
        sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        verifier, challenge = oauth.generate_pkce()
        state = oauth.new_state()
        now = time.time()
        self.sessions[sid] = {"expires_at": now + 900, "csrf": csrf,
                              "oauth": {"state": state, "verifier": verifier, "expires_at": now + 600, "used": False}}
        location = oauth.build_authorization_url(self.config["client_key"], self.config["redirect_uri"], SCOPES, state, challenge)
        return Response(302, "", {"Location": location,
                        "Set-Cookie": f"tc_session={sid}; Path=/; HttpOnly; SameSite=Lax; Max-Age=900"})

    def _callback(self, query, cookies):
        session = self._session(cookies)
        code = oauth.validate_callback(query, session["oauth"], time.time())
        bundle = self.deps.exchange_code(self.config, code, session["oauth"]["verifier"])
        user = self.deps.get_user_info(bundle.access_token)
        session["token"] = bundle
        session["user"] = user
        return Response(303, "", {"Location": "/authorized"})

    def _authorized_page(self, cookies):
        session = self._authorized(cookies)
        user = session["user"]
        short_id = user.open_id[:4] + "…" + user.open_id[-4:] if len(user.open_id) > 8 else "…"
        return Response(200, templates.authorized(user.display_name, short_id, session["csrf"]))

    def _authorized(self, cookies):
        session = self._session(cookies)
        if "token" not in session or "user" not in session:
            raise oauth.OAuthError("authorization_required")
        return session

    def _check_csrf(self, session, form):
        supplied = str(form.get("csrf", ""))
        if not supplied or not secrets.compare_digest(session["csrf"], supplied):
            raise PermissionError("csrf_invalid")

    def _review(self, form, cookies):
        session = self._authorized(cookies)
        try:
            self._check_csrf(session, form)
        except PermissionError:
            return Response(403, templates.safe_error("csrf_invalid"))
        path, caption = str(form.get("path", "")), str(form.get("caption", ""))
        if not path or not caption:
            return Response(400, templates.safe_error("review_fields_required"))
        creator = self.deps.get_creator_info(session["token"].access_token)
        if "SELF_ONLY" not in creator.privacy_level_options:
            raise tiktok_api.ApiError("self_only_unavailable")
        facts = self.deps.probe_video(path)
        validation = self.deps.validate_video(facts, creator.max_video_post_duration_sec)
        if not validation.ok:
            return Response(400, templates.safe_error(validation.code))
        session["review"] = {"path": path, "caption": caption}
        return Response(200, templates.review(Path(path).name, caption, session["user"].display_name, session["csrf"], creator))

    def _publish(self, form, cookies):
        session = self._authorized(cookies)
        try:
            self._check_csrf(session, form)
        except PermissionError:
            return Response(403, templates.safe_error("csrf_invalid"))
        review = session.get("review")
        if not review:
            return Response(400, templates.safe_error("review_required"))
        media = Path(review["path"])
        size = media.stat().st_size if media.is_file() else 1
        request = {"post_info": {"title": review["caption"], "privacy_level": "SELF_ONLY",
                                  "disable_comment": False, "disable_duet": True, "disable_stitch": True},
                   "source_info": {"source": "FILE_UPLOAD", "video_size": size,
                                   "chunk_size": size, "total_chunk_count": 1}}
        ticket = self.deps.initialize_post(session["token"].access_token, request)
        self.deps.upload_video(ticket, media)
        session["publish_id"] = ticket.publish_id
        return Response(200, templates.page("Upload initialized", "<p>Status: initialized</p><a href='/status'>Check status</a>"))

    def _status(self, cookies):
        session = self._authorized(cookies)
        if "publish_id" not in session:
            return Response(400, templates.safe_error("publish_not_initialized"))
        status = self.deps.get_post_status(session["token"].access_token, session["publish_id"])
        return Response(200, templates.page("Publish status", f"<p>{status.status}</p>"))


def load_env(path: Path) -> dict[str, str]:
    values = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def run() -> None:
    values = load_env(Path(__file__).with_name(".env"))
    key, secret = values.get("TIKTOK_CLIENT_KEY", ""), values.get("TIKTOK_CLIENT_SECRET", "")
    if not key or not secret:
        raise SystemExit("Configure oauth-test/.env before starting the local server.")
    app = App({"client_key": key, "client_secret": secret, "redirect_uri": REDIRECT_URI})

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self): self._dispatch("GET")
        def do_POST(self): self._dispatch("POST")
        def log_message(self, format, *args): return
        def _dispatch(self, method):
            parsed = urlparse(self.path)
            query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            length = int(self.headers.get("Content-Length", "0"))
            form = {k: v[0] for k, v in parse_qs(self.rfile.read(length).decode()).items()} if length else {}
            jar = SimpleCookie(self.headers.get("Cookie", ""))
            cookies = {k: morsel.value for k, morsel in jar.items()}
            response = app.handle(method, parsed.path, query=query, form=form, cookies=cookies)
            self.send_response(response.status)
            for name, value in response.headers.items(): self.send_header(name, value)
            self.end_headers()
            self.wfile.write(response.body.encode("utf-8"))

    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    run()
