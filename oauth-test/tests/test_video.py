import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import video


def runner_with(payload, returncode=0):
    def run(command):
        return returncode, json.dumps(payload), "ffprobe details must stay internal"
    return run


class VideoTests(unittest.TestCase):
    def test_probe_rejects_missing_file_and_malformed_output(self):
        with self.assertRaisesRegex(video.VideoError, "file_missing"):
            video.probe_video("missing.mp4", runner_with({}))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "x.mp4"
            path.write_bytes(b"x")
            with self.assertRaisesRegex(video.VideoError, "probe_invalid"):
                video.probe_video(path, lambda command: (0, "not-json", "secret"))

    def test_validation_fail_closed_cases(self):
        base = dict(container="mov,mp4,m4a,3gp,3g2,mj2", codec="h264", duration=61.0, size=100)
        cases = [
            ({**base, "container": "matroska,webm"}, "container_not_mp4"),
            ({**base, "codec": "hevc"}, "codec_not_h264"),
            ({**base, "duration": 60.8}, "duration_not_61_seconds"),
            ({**base, "duration": 61.0}, "creator_duration_exceeded", 60),
            ({**base, "size": 0}, "file_empty"),
            ({**base, "size": video.MAX_FILE_BYTES + 1}, "file_too_large"),
        ]
        for item in cases:
            facts, expected, *limit = item
            result = video.validate_video(video.VideoFacts(**facts), limit[0] if limit else 300)
            self.assertFalse(result.ok)
            self.assertEqual(result.code, expected)

    def test_successful_61_second_h264_mp4(self):
        payload = {"format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "61.000000", "size": "1234"},
                   "streams": [{"codec_type": "video", "codec_name": "h264"}]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "valid.mp4"
            path.write_bytes(b"x")
            facts = video.probe_video(path, runner_with(payload))
        self.assertTrue(video.validate_video(facts, 300).ok)


if __name__ == "__main__":
    unittest.main()
