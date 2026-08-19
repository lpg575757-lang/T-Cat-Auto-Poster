import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
from oauth import TokenBundle
from tiktok_api import AuthorizedUser, CreatorInfo, UploadTicket
from video import VideoFacts, validate_video


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        deps = server.Dependencies(
            exchange_code=lambda config, code, verifier: TokenBundle("access-secret", "refresh-secret", 1, 2, ("user.info.basic", "video.publish"), "oid"),
            get_user_info=lambda token: AuthorizedUser("abcdefghijk", "Target Cat"),
            get_creator_info=lambda token: CreatorInfo("", "cat", "Target Cat", ("SELF_ONLY",), False, True, True, 300),
            initialize_post=self._initialize,
            upload_video=lambda ticket, path: self.calls.append(("upload", ticket.publish_id, str(path))),
            get_post_status=lambda token, publish_id: type("Status", (), {"status": "PROCESSING_UPLOAD"})(),
            probe_video=lambda path: VideoFacts("mov,mp4", "h264", 61.0, 2194583),
            validate_video=validate_video,
        )
        self.app = server.App({"client_key": "key", "client_secret": "secret", "redirect_uri": server.REDIRECT_URI}, deps)

    def _initialize(self, token, request):
        self.calls.append(("initialize", request))
        return UploadTicket("pub1", "https://upload.invalid/u")

    def test_login_redirect_cookie_and_no_store(self):
        response = self.app.handle("GET", "/login")
        self.assertEqual(response.status, 302)
        query = parse_qs(urlparse(response.headers["Location"]).query)
        self.assertEqual(query["scope"], ["user.info.basic,video.publish"])
        self.assertIn("HttpOnly", response.headers["Set-Cookie"])
        self.assertIn("SameSite=Lax", response.headers["Set-Cookie"])
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_callback_error_is_safe(self):
        response = self.app.handle("GET", "/callback/", query={"state": "wrong", "code": "sensitive"}, cookies={"tc_session": "missing"})
        self.assertEqual(response.status, 400)
        self.assertNotIn("sensitive", response.body)

    def test_callback_renders_safe_authorized_user(self):
        login = self.app.handle("GET", "/login")
        sid = login.headers["Set-Cookie"].split("=", 1)[1].split(";", 1)[0]
        state = self.app.sessions[sid]["oauth"]["state"]
        response = self.app.handle("GET", "/callback/", query={"state": state, "code": "code-sensitive"}, cookies={"tc_session": sid})
        self.assertEqual(response.status, 303)
        self.assertEqual(response.headers["Location"], "/authorized")
        serialized = response.body + repr(response.headers)
        self.assertNotIn("code-sensitive", serialized)
        self.assertNotIn(state, serialized)
        authorized = self.app.handle("GET", "/authorized", cookies={"tc_session": sid})
        self.assertEqual(authorized.status, 200)
        self.assertIn("Target Cat", authorized.body)
        self.assertIn("abcd…hijk", authorized.body)
        self.assertNotIn("access-secret", authorized.body)
        self.assertNotIn("code-sensitive", authorized.body)

    def test_callback_query_never_reaches_ui_or_redirect(self):
        login = self.app.handle("GET", "/login")
        sid = login.headers["Set-Cookie"].split("=", 1)[1].split(";", 1)[0]
        state = self.app.sessions[sid]["oauth"]["state"]
        code = "one-time-code-must-not-appear"
        response = self.app.handle("GET", "/callback/", query={"state": state, "code": code}, cookies={"tc_session": sid})
        self.assertEqual(response.headers.get("Location"), "/authorized")
        self.assertNotIn("?", response.headers["Location"])
        self.assertNotIn(code, response.body + repr(response.headers))
        self.assertNotIn(state, response.body + repr(response.headers))

    def test_review_does_not_initialize_and_enforces_self_only(self):
        sid = self._authorized_session()
        csrf = self.app.sessions[sid]["csrf"]
        response = self.app.handle("POST", "/review", form={"csrf": csrf, "path": "C:/approved/demo.mp4", "caption": "T Cat demo"}, cookies={"tc_session": sid})
        self.assertEqual(response.status, 200)
        self.assertIn("demo.mp4", response.body)
        self.assertIn("T Cat demo", response.body)
        self.assertIn("SELF_ONLY", response.body)
        self.assertIn("Maximum duration: 300 seconds", response.body)
        self.assertIn("Comments: enabled", response.body)
        self.assertEqual(self.calls, [])

    def test_review_stops_when_creator_limit_is_below_61_seconds(self):
        self.app.deps.get_creator_info = lambda token: CreatorInfo("", "cat", "Target Cat", ("SELF_ONLY",), False, True, True, 60)
        sid = self._authorized_session()
        csrf = self.app.sessions[sid]["csrf"]
        response = self.app.handle("POST", "/review", form={"csrf": csrf, "path": "C:/approved/demo.mp4", "caption": "T Cat demo"}, cookies={"tc_session": sid})
        self.assertEqual(response.status, 400)
        self.assertIn("creator_duration_exceeded", response.body)
        self.assertEqual(self.calls, [])

    def test_publish_requires_post_and_csrf_then_initializes(self):
        sid = self._authorized_session()
        self.assertEqual(self.app.handle("GET", "/publish", cookies={"tc_session": sid}).status, 405)
        bad = self.app.handle("POST", "/publish", form={"csrf": "wrong"}, cookies={"tc_session": sid})
        self.assertEqual(bad.status, 403)
        self.assertEqual(self.calls, [])
        csrf = self.app.sessions[sid]["csrf"]
        self.app.sessions[sid]["review"] = {"path": "C:/approved/demo.mp4", "caption": "T Cat demo"}
        response = self.app.handle("POST", "/publish", form={"csrf": csrf}, cookies={"tc_session": sid})
        self.assertEqual(response.status, 200)
        self.assertEqual(self.calls[0][0], "initialize")
        self.assertEqual(self.calls[0][1]["post_info"]["privacy_level"], "SELF_ONLY")

    def _authorized_session(self):
        login = self.app.handle("GET", "/login")
        sid = login.headers["Set-Cookie"].split("=", 1)[1].split(";", 1)[0]
        state = self.app.sessions[sid]["oauth"]["state"]
        self.app.handle("GET", "/callback/", query={"state": state, "code": "code"}, cookies={"tc_session": sid})
        return sid


if __name__ == "__main__":
    unittest.main()
