"""Minimal, redacting TikTok Content Posting API client."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping


API_ROOT = "https://open.tiktokapis.com"


class ApiError(Exception):
    """A deliberately limited error safe for UI and logs."""


@dataclass(frozen=True)
class AuthorizedUser:
    open_id: str
    display_name: str


@dataclass(frozen=True)
class CreatorInfo:
    creator_avatar_url: str
    creator_username: str
    creator_nickname: str
    privacy_level_options: tuple[str, ...]
    comment_disabled: bool
    duet_disabled: bool
    stitch_disabled: bool
    max_video_post_duration_sec: int


@dataclass(frozen=True)
class UploadTicket:
    publish_id: str
    upload_url: str


@dataclass(frozen=True)
class PostStatus:
    status: str


Transport = Callable[[str, str, Mapping[str, str], bytes | None, float], tuple[int, bytes]]


def _default_transport(method, url, headers, body, timeout):
    request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def _call(method, path, access_token, payload, transport, *, absolute=False):
    url = path if absolute else API_ROOT + path
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
    try:
        status, raw = (transport or _default_transport)(method, url, headers, body, 20.0)
    except Exception as error:
        raise ApiError("network_error") from error
    try:
        response = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        response = {}
    error_data = response.get("error", {}) if isinstance(response, dict) else {}
    error_code = str(error_data.get("code", "unknown_error"))
    if status < 200 or status >= 300 or error_code not in ("ok", ""):
        log_id = str(error_data.get("log_id", ""))[:8]
        suffix = f" log_id={log_id}" if log_id else ""
        raise ApiError(f"api_failed status={status} code={error_code}{suffix}")
    return response.get("data", {})


def get_user_info(access_token: str, transport: Transport | None = None) -> AuthorizedUser:
    data = _call("GET", "/v2/user/info/?fields=open_id,display_name", access_token, None, transport)
    try:
        user = data["user"]
        return AuthorizedUser(str(user["open_id"]), str(user["display_name"]))
    except (KeyError, TypeError) as error:
        raise ApiError("invalid_user_info") from error


def get_creator_info(access_token: str, transport: Transport | None = None) -> CreatorInfo:
    data = _call("POST", "/v2/post/publish/creator_info/query/", access_token, {}, transport)
    try:
        options = tuple(str(value) for value in data["privacy_level_options"])
        if "SELF_ONLY" not in options:
            raise ApiError("self_only_unavailable")
        return CreatorInfo(
            str(data["creator_avatar_url"]), str(data["creator_username"]),
            str(data["creator_nickname"]), options, bool(data["comment_disabled"]),
            bool(data["duet_disabled"]), bool(data["stitch_disabled"]),
            int(data["max_video_post_duration_sec"]),
        )
    except ApiError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise ApiError("invalid_creator_info") from error


def initialize_post(access_token: str, request: Mapping[str, object], transport: Transport | None = None) -> UploadTicket:
    post_info = request.get("post_info", {})
    if not isinstance(post_info, Mapping) or post_info.get("privacy_level") != "SELF_ONLY":
        raise ApiError("self_only_required")
    data = _call("POST", "/v2/post/publish/video/init/", access_token, request, transport)
    try:
        return UploadTicket(str(data["publish_id"]), str(data["upload_url"]))
    except (KeyError, TypeError) as error:
        raise ApiError("invalid_upload_ticket") from error


def upload_video(ticket: UploadTicket, path: str | Path, transport: Transport | None = None) -> None:
    media = Path(path).read_bytes()
    headers = {"Content-Type": "video/mp4", "Content-Length": str(len(media)),
               "Content-Range": f"bytes 0-{len(media) - 1}/{len(media)}"}
    try:
        status, _ = (transport or _default_transport)("PUT", ticket.upload_url, headers, media, 60.0)
    except Exception as error:
        raise ApiError("upload_network_error") from error
    if status < 200 or status >= 300:
        raise ApiError(f"upload_failed status={status}")


def get_post_status(access_token: str, publish_id: str, transport: Transport | None = None) -> PostStatus:
    data = _call("POST", "/v2/post/publish/status/fetch/", access_token,
                 {"publish_id": publish_id}, transport)
    try:
        return PostStatus(str(data["status"]))
    except (KeyError, TypeError) as error:
        raise ApiError("invalid_post_status") from error
