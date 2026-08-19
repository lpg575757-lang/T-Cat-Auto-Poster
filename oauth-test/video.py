"""Read-only MP4 validation for the approved Sandbox demonstration asset."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


MAX_FILE_BYTES = 4 * 1024 * 1024 * 1024


class VideoError(Exception):
    pass


@dataclass(frozen=True)
class VideoFacts:
    container: str
    codec: str
    duration: float
    size: int


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    code: str


Runner = Callable[[Sequence[str]], tuple[int, str, str]]


def _default_runner(command: Sequence[str]) -> tuple[int, str, str]:
    result = subprocess.run(command, capture_output=True, text=True, timeout=20, shell=False)
    return result.returncode, result.stdout, result.stderr


def probe_video(path: str | Path, runner: Runner | None = None) -> VideoFacts:
    media = Path(path)
    if not media.is_file():
        raise VideoError("file_missing")
    command = ["ffprobe", "-v", "error", "-show_entries",
               "format=format_name,duration,size:stream=codec_type,codec_name",
               "-of", "json", str(media)]
    try:
        returncode, stdout, _ = (runner or _default_runner)(command)
        if returncode != 0:
            raise VideoError("probe_failed")
        payload = json.loads(stdout)
        format_data = payload["format"]
        video_stream = next(stream for stream in payload["streams"] if stream.get("codec_type") == "video")
        return VideoFacts(
            container=str(format_data["format_name"]),
            codec=str(video_stream["codec_name"]),
            duration=float(format_data["duration"]),
            size=int(format_data["size"]),
        )
    except VideoError:
        raise
    except (json.JSONDecodeError, KeyError, StopIteration, TypeError, ValueError) as error:
        raise VideoError("probe_invalid") from error


def validate_video(facts: VideoFacts, creator_limit: int, require_duration: float = 61.0) -> ValidationResult:
    containers = {part.strip().lower() for part in facts.container.split(",")}
    if "mp4" not in containers:
        return ValidationResult(False, "container_not_mp4")
    if facts.codec.lower() != "h264":
        return ValidationResult(False, "codec_not_h264")
    if facts.size <= 0:
        return ValidationResult(False, "file_empty")
    if facts.size > MAX_FILE_BYTES:
        return ValidationResult(False, "file_too_large")
    if abs(facts.duration - require_duration) > 0.05:
        return ValidationResult(False, "duration_not_61_seconds")
    if facts.duration > creator_limit:
        return ValidationResult(False, "creator_duration_exceeded")
    return ValidationResult(True, "ok")
