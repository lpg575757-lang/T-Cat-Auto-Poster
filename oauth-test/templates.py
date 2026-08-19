"""Small dependency-free HTML renderer for local-only pages."""

from html import escape


def page(title: str, content: str) -> str:
    return ("<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{escape(title)}</title><body><main><h1>{escape(title)}</h1>{content}</main></body></html>")


def authorized(display_name: str, short_id: str, csrf: str) -> str:
    return page("Authorized Target User", f"<p>{escape(display_name)} ({escape(short_id)})</p>"
                "<form method='post' action='/review'>"
                f"<input type='hidden' name='csrf' value='{escape(csrf)}'>"
                "<label>Approved MP4 path <input name='path' required></label>"
                "<label>Caption <input name='caption' required></label><button>Review</button></form>")


def review(filename: str, caption: str, account: str, csrf: str, creator) -> str:
    comments = "disabled" if creator.comment_disabled else "enabled"
    duet = "disabled" if creator.duet_disabled else "enabled"
    stitch = "disabled" if creator.stitch_disabled else "enabled"
    return page("Review SELF_ONLY Post", f"<p>File: {escape(filename)}</p><p>Caption: {escape(caption)}</p>"
                f"<p>Account: {escape(account)}</p><p>Privacy: SELF_ONLY</p>"
                f"<p>Maximum duration: {creator.max_video_post_duration_sec} seconds</p>"
                f"<p>Comments: {comments}; Duet: {duet}; Stitch: {stitch}</p>"
                "<form method='post' action='/publish'>"
                f"<input type='hidden' name='csrf' value='{escape(csrf)}'>"
                "<button>Publish</button></form>")


def safe_error(code: str) -> str:
    return page("Request failed", f"<p>Error: {escape(code)}</p>")
