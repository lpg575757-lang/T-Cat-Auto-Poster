import subprocess
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def is_ignored(relative_path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", "--no-index", relative_path],
        cwd=REPOSITORY_ROOT,
        check=False,
    )
    return result.returncode == 0


class RepositorySafetyTests(unittest.TestCase):
    def test_runtime_and_secret_paths_are_ignored(self) -> None:
        paths = (
            "oauth-test/.env",
            "oauth-test/.runtime/session.json",
            "oauth-test/.browser-profile/Default/Preferences",
            "oauth-test/media/test.mp4",
            "oauth-test/screenshots/portal.png",
            "oauth-test/oauth-test.log",
            "oauth-test/__pycache__/oauth.cpython-311.pyc",
            "oauth-test/tests/__pycache__/test_oauth.cpython-311.pyc",
        )

        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(is_ignored(path), f"must be ignored: {path}")

    def test_env_example_remains_trackable(self) -> None:
        self.assertFalse(is_ignored("oauth-test/.env.example"))


if __name__ == "__main__":
    unittest.main()
