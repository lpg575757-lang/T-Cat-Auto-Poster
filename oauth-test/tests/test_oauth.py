import hashlib
import json
import string
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import oauth


class OAuthTests(unittest.TestCase):
    def test_pkce_verifier_and_tiktok_hex_challenge(self):
        verifier, challenge = oauth.generate_pkce()
        self.assertGreaterEqual(len(verifier), 43)
        self.assertLessEqual(len(verifier), 128)
        self.assertTrue(set(verifier) <= set(string.ascii_letters + string.digits + "-._~"))
        self.assertEqual(challenge, hashlib.sha256(verifier.encode("ascii")).hexdigest())

    def test_authorization_url_has_exact_parameters(self):
        url = oauth.build_authorization_url(
            "client-key", "http://127.0.0.1:3455/callback/",
            ("user.info.basic", "video.publish"), "state-value", "challenge-value"
        )
        parsed = urlparse(url)
        self.assertEqual(parsed.scheme + "://" + parsed.netloc + parsed.path,
                         "https://www.tiktok.com/v2/auth/authorize/")
        self.assertEqual(parse_qs(parsed.query), {
            "client_key": ["client-key"],
            "response_type": ["code"],
            "scope": ["user.info.basic,video.publish"],
            "redirect_uri": ["http://127.0.0.1:3455/callback/"],
            "state": ["state-value"],
            "code_challenge": ["challenge-value"],
            "code_challenge_method": ["S256"],
        })

    def test_callback_rejects_mismatch_expiry_replay_missing_code_and_oauth_error(self):
        cases = [
            ({"state": "wrong", "code": "c"}, {"state": "right", "expires_at": 20, "used": False}, 10, "state_mismatch"),
            ({"state": "s", "code": "c"}, {"state": "s", "expires_at": 9, "used": False}, 10, "session_expired"),
            ({"state": "s", "code": "c"}, {"state": "s", "expires_at": 20, "used": True}, 10, "callback_replayed"),
            ({"state": "s"}, {"state": "s", "expires_at": 20, "used": False}, 10, "missing_code"),
            ({"state": "s", "error": "access_denied", "error_description": "do not echo"}, {"state": "s", "expires_at": 20, "used": False}, 10, "oauth_error"),
        ]
        for query, session, now, code in cases:
            with self.subTest(code=code), self.assertRaisesRegex(oauth.OAuthError, code):
                oauth.validate_callback(query, session, now)

    def test_callback_is_single_use(self):
        session = {"state": "s", "expires_at": 20, "used": False}
        self.assertEqual(oauth.validate_callback({"state": "s", "code": "safe-code"}, session, 10), "safe-code")
        self.assertTrue(session["used"])
        with self.assertRaisesRegex(oauth.OAuthError, "callback_replayed"):
            oauth.validate_callback({"state": "s", "code": "safe-code"}, session, 10)

    def test_token_exchange_and_safe_metadata(self):
        captured = {}
        def transport(url, data, headers, timeout):
            captured.update(url=url, data=data, headers=headers, timeout=timeout)
            return 200, json.dumps({
                "access_token": "access-sensitive", "refresh_token": "refresh-sensitive",
                "expires_in": 7200, "refresh_expires_in": 86400,
                "scope": "user.info.basic,video.publish", "open_id": "open-id"
            }).encode()
        bundle = oauth.exchange_code({
            "client_key": "key", "client_secret": "secret-sensitive",
            "redirect_uri": "http://127.0.0.1:3455/callback/"
        }, "code-sensitive", "verifier-sensitive", transport)
        self.assertEqual(bundle.access_token, "access-sensitive")
        safe = repr(bundle)
        self.assertNotIn("sensitive", safe)
        self.assertIn("expires_in=7200", safe)
        body = parse_qs(captured["data"].decode())
        self.assertEqual(body["grant_type"], ["authorization_code"])
        self.assertEqual(body["code_verifier"], ["verifier-sensitive"])

    def test_token_exchange_failure_is_redacted(self):
        def transport(url, data, headers, timeout):
            return 400, b'{"error":"invalid_grant","error_description":"code-sensitive secret-sensitive"}'
        with self.assertRaises(oauth.OAuthError) as caught:
            oauth.exchange_code({
                "client_key": "key", "client_secret": "secret-sensitive",
                "redirect_uri": "http://127.0.0.1:3455/callback/"
            }, "code-sensitive", "verifier-sensitive", transport)
        message = str(caught.exception)
        self.assertIn("token_exchange_failed", message)
        self.assertNotIn("sensitive", message)


if __name__ == "__main__":
    unittest.main()
