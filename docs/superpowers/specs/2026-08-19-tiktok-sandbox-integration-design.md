# T Cat Auto Poster TikTok Sandbox Integration Design

## Goal

Configure the existing `T Cat Sandbox` with the minimum TikTok products and
scopes needed for a Desktop OAuth and Direct Post demonstration, then build a
local-only test application that proves authorization and the user-confirmed
Sandbox posting flow without submitting a Production review.

## Current boundaries

The public static site and GitHub Pages routes remain unchanged. New local
integration code lives under `oauth-test/`. The existing Chrome profile and
existing logged-in browser are never modified. Portal automation uses a
dedicated temporary Chrome profile exposed only through a task-specific CDP
port. Production mode, Import to Production, Submit for review, Client Secret
reveal in logs, and any P13-TQ Git operation are forbidden.

The requested icon `T_Cat_Auto_Poster_icon_1024.png` and a 61-second MP4 were
not found during discovery. Their absence does not block OAuth code and Portal
configuration that does not require them, but icon upload or posting must stop
until exact candidate files are available and validated.

## Official platform requirements

The registered Desktop redirect URI is
`http://127.0.0.1:3455/callback/`. It is absolute, static, uses an allowed
loopback host, includes a port, and has no query or fragment.

Desktop Login Kit uses `https://www.tiktok.com/v2/auth/authorize/`, requires a
fresh PKCE verifier for every request, and uses TikTok's documented
SHA-256-hex challenge. The callback must validate a cryptographically random
`state` value before accepting the authorization code. Token exchange uses
`https://open.tiktokapis.com/v2/oauth/token/` and requires the Client key,
Client secret, authorization code, redirect URI, and PKCE verifier.

The minimum requested scopes are `user.info.basic` and `video.publish`.
`user.info.basic` identifies the authorized user through `/v2/user/info/`.
`video.publish` permits creator-info queries and Direct Post. Sandbox does not
provide public Content Posting API video publication. An unaudited client is
restricted to the minimum privacy allowed by TikTok, normally `SELF_ONLY`.

Before every Direct Post attempt the application calls
`/v2/post/publish/creator_info/query/` and renders the returned creator,
privacy options, interaction settings, and maximum duration. It never invents
or expands privacy options.

## Portal configuration

Use the existing `T Cat Auto Poster` app, Sandbox mode, and `T Cat Sandbox`.
Read current values before editing. Keep or set:

- app name `T Cat Auto Poster`;
- category `Photo & Video`;
- description `T Cat Auto Poster helps creators organize their own videos and
  prepare them for publishing with user authorization.`;
- Login Kit configured for Desktop with the exact redirect URI;
- Content Posting API with Direct Post only;
- scopes `user.info.basic` and `video.publish` only.

Do not add Share Kit, Display API, Webhooks, Data Portability API, or unrelated
scopes. Apply changes only after reviewing the complete pending configuration.
Never switch to or mutate Production.

Sandbox Target User setup may redirect to TikTok login and Developer Terms.
At login, account choice, password, QR, 2FA, CAPTCHA, terms acceptance, or
OAuth consent, stop and request exactly one user action. Do not inspect,
capture, type, or store credentials.

## CDP browser isolation

Launch a new Chrome process with a fresh task-specific temporary profile and a
loopback-only remote-debugging endpoint. Do not pass or reuse the user's normal
profile directory. Record only the Chrome process identifier, CDP endpoint,
and temporary profile path needed to reconnect during this task. The profile
is not committed and is deleted only after the integration work is complete
and no authentication state is needed.

Browser automation may read and modify only the approved Sandbox configuration.
Before actions that transmit files or save Portal settings, re-check that the
visible mode is Sandbox and the sandbox name is `T Cat Sandbox`. If the page
shows Production or Submit for review, stop.

## Local architecture

Use Python 3 standard libraries so no runtime dependency is added. The local
application binds only to `127.0.0.1:3455` and contains these focused units:

- `oauth-test/server.py`: HTTP routes, secure session cookie, UI rendering,
  callback orchestration, and no-store response headers;
- `oauth-test/oauth.py`: state and PKCE generation, authorization URL
  construction, callback validation, token exchange, and token refresh;
- `oauth-test/tiktok_api.py`: authenticated user info, creator info, upload
  initialization, binary upload, and status polling;
- `oauth-test/video.py`: MP4/H.264/duration/size validation through an existing
  local `ffprobe` when available, failing closed when proof is unavailable;
- `oauth-test/templates/`: local pages for login, authorization result,
  publishing review, explicit Publish confirmation, and safe status;
- `oauth-test/tests/`: deterministic unit and local integration tests;
- `oauth-test/.env.example`: key names only;
- `oauth-test/README.md`: setup, safe secret entry, run, test, and demo steps.

The existing root `.gitignore` must continue excluding `.env` and token/secret
files. Runtime state uses a local ignored directory such as
`oauth-test/.runtime/`. Tokens are held in memory or encrypted operating-system
storage if available; they are never returned to browser markup, printed, or
written to committed files.

## Secret entry and redaction

The application needs `TIKTOK_CLIENT_KEY` and `TIKTOK_CLIENT_SECRET`. The
Client key may appear in the outbound authorization URL. The secret must be
entered by the user through a non-echoing local setup prompt or directly into
an ignored `.env`; Codex never asks the user to paste it into chat. Test and
runtime log filters redact fields containing `token`, `secret`, `code`,
`authorization`, and cookie values. User-facing errors contain only safe error
codes and retry guidance.

## OAuth flow

1. The local home page starts a new one-time session.
2. The server creates random `state` and PKCE verifier values and stores them
   server-side with a short expiry and single-use flag.
3. The browser redirects to TikTok with Client key, exact redirect URI,
   `user.info.basic,video.publish`, state, and PKCE challenge.
4. The user performs TikTok login and consent manually when requested.
5. The callback rejects missing code, missing state, mismatched state, expired
   session, reused callback, and OAuth error responses.
6. The server exchanges the code without logging request fields or response
   credentials.
7. The server calls `/v2/user/info/` and renders only the authorized display
   name and a shortened non-secret account identifier.

## Publishing flow

The user selects one local MP4. Before accepting it, the application verifies
ownership confirmation, MP4 container, H.264 video codec, exact or allowed
duration for the test scenario, size, and creator maximum duration. It queries
creator info immediately before rendering the review page.

The review page shows filename, caption, authorized account, TikTok-provided
privacy options, and interaction options. In Sandbox/unaudited mode it
preselects and enforces `SELF_ONLY` when available. A distinct Publish button
is the only action that can initialize upload. The application then uploads
the file to the TikTok-provided URL and polls status using the publish ID. It
renders safe states such as initialized, uploading, processing, succeeded, or
failed without exposing tokens or full API payloads.

No automatic posting, background scheduler, public-visibility escalation, or
posting to an account other than the authorized Target User is permitted.

## Testing

Tests are written before implementation. They cover PKCE format and challenge,
state mismatch/expiry/replay, missing callback code, OAuth error callback,
token exchange failure and redaction, user-info success/failure, creator-info
required fields, allowed privacy options, explicit publish confirmation,
unsupported file/container/codec/duration/size, upload failure, status polling,
and network failure.

Run the existing root `tests/validate-site.ps1` unchanged to prove the public
site remains intact. Before any Git commit, run all OAuth tests, the static
site suite, secret-pattern scans, `git diff --check`, and exact-file diff review.
An `.env`, token, secret, authorization code, runtime state, browser profile,
video, or screenshot must never be staged.

## Completion and proof boundaries

Portal configuration is complete only after the Sandbox page shows the exact
products, redirect URI, scopes, and successfully applied changes. OAuth is
complete only after callback state validation, token exchange, and
`user.info.basic` succeed against the configured Sandbox Target User. Posting
is complete only after creator info is rendered, the user presses Publish, and
TikTok returns a publish ID and observable status. A Sandbox restriction or
private-only outcome is not a failure if it matches TikTok's documented
behavior.

Build/test proof is not live OAuth or posting proof. Missing Client Secret,
Target User authorization, eligible MP4, or TikTok approval must be reported as
the exact remaining boundary. Production Review submission is never part of
this work.
