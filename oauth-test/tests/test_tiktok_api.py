import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tiktok_api as api


class FakeTransport:
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload
        self.calls = []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append((method, url, headers, body, timeout))
        encoded = self.payload if isinstance(self.payload, bytes) else json.dumps(self.payload).encode()
        return self.status, encoded


class TikTokApiTests(unittest.TestCase):
    def test_user_info_and_token_only_in_header(self):
        transport = FakeTransport(200, {"data": {"user": {"open_id": "oid", "display_name": "Target"}}, "error": {"code": "ok"}})
        user = api.get_user_info("token-sensitive", transport)
        self.assertEqual((user.open_id, user.display_name), ("oid", "Target"))
        call = transport.calls[0]
        self.assertEqual(call[2]["Authorization"], "Bearer token-sensitive")
        self.assertNotIn("token-sensitive", call[1])

    def test_creator_info_preserves_options_and_requires_self_only(self):
        payload = {"data": {"creator_avatar_url": "https://example.invalid/a", "creator_username": "cat",
            "creator_nickname": "T Cat", "privacy_level_options": ["SELF_ONLY", "MUTUAL_FOLLOW_FRIENDS"],
            "comment_disabled": False, "duet_disabled": True, "stitch_disabled": True,
            "max_video_post_duration_sec": 300}, "error": {"code": "ok"}}
        creator = api.get_creator_info("tok", FakeTransport(200, payload))
        self.assertEqual(creator.privacy_level_options, ("SELF_ONLY", "MUTUAL_FOLLOW_FRIENDS"))
        payload["data"]["privacy_level_options"] = ["PUBLIC_TO_EVERYONE"]
        with self.assertRaisesRegex(api.ApiError, "self_only_unavailable"):
            api.get_creator_info("tok", FakeTransport(200, payload))

    def test_api_error_redacts_token_payload_and_long_log_id(self):
        transport = FakeTransport(401, {"error": {"code": "access_token_invalid", "message": "token-sensitive", "log_id": "1234567890abcdef"}})
        with self.assertRaises(api.ApiError) as caught:
            api.get_user_info("token-sensitive", transport)
        message = str(caught.exception)
        self.assertIn("status=401", message)
        self.assertIn("access_token_invalid", message)
        self.assertIn("12345678", message)
        self.assertNotIn("sensitive", message)
        self.assertNotIn("90abcdef", message)

    def test_initialize_upload_and_status(self):
        init = FakeTransport(200, {"data": {"publish_id": "pub1", "upload_url": "https://upload.example/u"}, "error": {"code": "ok"}})
        ticket = api.initialize_post("tok", {"post_info": {"privacy_level": "SELF_ONLY"}, "source_info": {}}, init)
        self.assertEqual(ticket.publish_id, "pub1")
        self.assertEqual(json.loads(init.calls[0][3]), {"post_info": {"privacy_level": "SELF_ONLY"}, "source_info": {}})
        with tempfile.TemporaryDirectory() as folder:
            media = Path(folder) / "test.mp4"
            media.write_bytes(b"video-bytes")
            upload = FakeTransport(200, b"")
            api.upload_video(ticket, media, upload)
            self.assertEqual(upload.calls[0][0], "PUT")
            self.assertEqual(upload.calls[0][3], b"video-bytes")
        status = FakeTransport(200, {"data": {"status": "PROCESSING_UPLOAD"}, "error": {"code": "ok"}})
        self.assertEqual(api.get_post_status("tok", "pub1", status).status, "PROCESSING_UPLOAD")

    def test_upload_and_network_failures_are_safe(self):
        ticket = api.UploadTicket("pub", "https://upload.example/u")
        with tempfile.TemporaryDirectory() as folder:
            media = Path(folder) / "test.mp4"
            media.write_bytes(b"x")
            with self.assertRaisesRegex(api.ApiError, "upload_failed"):
                api.upload_video(ticket, media, FakeTransport(500, b"secret-response"))
        def broken(*args):
            raise OSError("token-sensitive")
        with self.assertRaisesRegex(api.ApiError, "network_error") as caught:
            api.get_user_info("token-sensitive", broken)
        self.assertNotIn("sensitive", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
