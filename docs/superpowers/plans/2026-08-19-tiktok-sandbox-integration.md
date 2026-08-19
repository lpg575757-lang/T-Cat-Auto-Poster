# TikTok Sandbox Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configure T Cat Sandbox and deliver a tested local Desktop OAuth and user-confirmed SELF_ONLY Direct Post demonstration without changing Production.

**Architecture:** A Python 3.11 standard-library service bound to `127.0.0.1:3455` owns OAuth sessions, secrets, TikTok API calls, upload state, and local review pages. A Node 24 standard-WebSocket CDP helper controls only a fresh temporary Chrome profile for approved Sandbox Portal configuration. Every network boundary is injectable so tests run without real credentials.

**Tech Stack:** Python 3.11 standard library, Node.js 24 built-in WebSocket, Chrome DevTools Protocol, ffprobe 8.1, PowerShell 5.1, Git

**Spec:** `docs/superpowers/specs/2026-08-19-tiktok-sandbox-integration-design.md`

## Global Constraints

- Bind the local service only to `127.0.0.1:3455` with callback `/callback/`.
- Never modify or reuse the existing Chrome profile; use a new task-specific temporary profile.
- Never expose Client Secret, access token, refresh token, password, authorization code, cookies, or full OAuth/API payloads in UI, logs, Git, or reports.
- Never switch to or modify Production and never select Submit for review.
- Request only `user.info.basic` and `video.publish`; add no unrelated products.
- Query creator info before every post review and permit only TikTok-returned privacy values, enforcing `SELF_ONLY` for Sandbox/unaudited tests.
- Never initialize a post until the user presses the explicit Publish button.
- Stop for exactly one user action at TikTok login, password, QR, 2FA, CAPTCHA, terms acceptance, Target User approval, or OAuth final consent.
- Do not search for or select an icon or video without an exact user-provided file.
- Keep `.env`, runtime state, browser profiles, videos, screenshots, secrets, and tokens untracked.

---

### Task 1: Lock down repository and configuration boundaries

**Files:**
- Modify: `.gitignore`
- Create: `oauth-test/.env.example`
- Create: `oauth-test/README.md`
- Test: `oauth-test/tests/test_repository_safety.py`

**Interfaces:**
- Consumes: repository root and environment keys `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`.
- Produces: ignored `.env`, `.runtime/`, browser-profile, media, screenshot, and log paths; documented non-echoing secret setup.

- [ ] Write a failing repository-safety test proving `.env`, `.runtime`, browser profiles, media, screenshots, and logs are ignored while `.env.example` is trackable.
- [ ] Run `python -m unittest discover -s oauth-test/tests -p "test_repository_safety.py" -v` and require failure because patterns/files are absent.
- [ ] Add the exact ignore rules and `.env.example` containing only `TIKTOK_CLIENT_KEY=` and `TIKTOK_CLIENT_SECRET=`.
- [ ] Document safe local setup without showing secret values and rerun the test to green.

### Task 2: Implement OAuth PKCE and state core

**Files:**
- Create: `oauth-test/oauth.py`
- Test: `oauth-test/tests/test_oauth.py`

**Interfaces:**
- Produces: `generate_pkce() -> tuple[str, str]`, `new_state() -> str`, `build_authorization_url(client_key, redirect_uri, scopes, state, challenge) -> str`, `validate_callback(query, session, now) -> str`, and `exchange_code(config, code, verifier, transport) -> TokenBundle`.
- `TokenBundle` stores credentials in memory and exposes only safe scope/expiry metadata.

- [ ] Write failing tests for verifier alphabet/length, SHA-256-hex challenge, exact authorization parameters, state mismatch, expiry, replay, missing code, OAuth error callback, and redacted token-exchange failure.
- [ ] Run the focused tests and confirm each fails for the missing behavior.
- [ ] Implement cryptographic state/PKCE generation, single-use callback validation, form-encoded token exchange, typed safe errors, and redaction.
- [ ] Rerun the focused tests to green.

### Task 3: Implement safe TikTok API boundaries

**Files:**
- Create: `oauth-test/tiktok_api.py`
- Test: `oauth-test/tests/test_tiktok_api.py`

**Interfaces:**
- Produces: `get_user_info(access_token, transport) -> AuthorizedUser`, `get_creator_info(access_token, transport) -> CreatorInfo`, `initialize_post(access_token, request, transport) -> UploadTicket`, `upload_video(ticket, path, transport)`, and `get_post_status(access_token, publish_id, transport) -> PostStatus`.
- All transports receive credentials in headers but error objects expose only HTTP status, TikTok safe error code, and redacted log identifier.

- [ ] Write failing tests for user info, required creator fields, privacy-option preservation, missing `SELF_ONLY`, token redaction, initialization, upload failure, status polling, and network failure.
- [ ] Run the focused tests and confirm failure.
- [ ] Implement the minimal API clients with bounded timeouts and safe parsing.
- [ ] Rerun the focused tests to green.

### Task 4: Implement video validation

**Files:**
- Create: `oauth-test/video.py`
- Test: `oauth-test/tests/test_video.py`

**Interfaces:**
- Produces: `probe_video(path, runner) -> VideoFacts` and `validate_video(facts, creator_limit, require_duration=61.0) -> ValidationResult`.

- [ ] Write failing tests for missing file, non-MP4, non-H.264, wrong duration, excessive creator duration, zero/oversized file, malformed ffprobe JSON, and successful 61-second MP4.
- [ ] Run the focused tests and confirm failure.
- [ ] Implement read-only ffprobe invocation and fail-closed validation.
- [ ] Rerun the focused tests to green.

### Task 5: Implement local OAuth and explicit-publish UI

**Files:**
- Create: `oauth-test/server.py`
- Create: `oauth-test/templates.py`
- Test: `oauth-test/tests/test_server.py`

**Interfaces:**
- Routes: `GET /`, `GET /login`, `GET /callback/`, `GET /publish`, `POST /review`, `POST /publish`, and `GET /status`.
- Session cookies are random, HttpOnly, SameSite=Lax, local-only, short-lived, and never contain credentials.

- [ ] Write failing HTTP tests for login redirect, no-store headers, callback errors, safe authorized-user display, creator-info-gated review, filename/caption/account/privacy rendering, `SELF_ONLY`, POST-only explicit publish, CSRF token, and redacted failures.
- [ ] Run the focused tests and confirm failure.
- [ ] Implement the minimal local server and accessible HTML pages without external assets.
- [ ] Rerun the focused tests to green.

### Task 6: Build and test isolated CDP Chrome control

**Files:**
- Create: `oauth-test/cdp.mjs`
- Create: `oauth-test/tests/cdp.test.mjs`
- Create: `oauth-test/start-sandbox-browser.ps1`

**Interfaces:**
- `cdp.mjs` connects only to a loopback endpoint supplied as `CDP_ENDPOINT`, lists tabs, reads DOM/accessible text, navigates, and performs selector-based clicks/fills after mode guards.
- `start-sandbox-browser.ps1` creates a fresh temporary profile, launches Chrome with a task-specific debugging port, and prints only safe connection metadata.

- [ ] Write a failing Node test against a fake CDP WebSocket server for command correlation, page inspection, selector errors, and the Sandbox/Production guard.
- [ ] Run `node --test oauth-test/tests/cdp.test.mjs` and confirm failure.
- [ ] Implement the standard-WebSocket CDP client and isolated launcher without accessing the normal Chrome profile.
- [ ] Rerun the Node tests to green.

### Task 7: Inspect and configure T Cat Sandbox

**Files:**
- Modify no repository source unless current Portal behavior requires a tested CDP selector adaptation.

**Interfaces:**
- Consumes: dedicated CDP Chrome and the logged-in TikTok Developer Portal session created by the user in that browser.
- Produces: applied Sandbox details, Desktop redirect URI, Login Kit, Content Posting API, and exact scopes.

- [ ] Launch the dedicated CDP Chrome and navigate to TikTok for Developers.
- [ ] If login is shown, stop and ask only: `今は専用ChromeでTikTok Developerへログインしてください。`
- [ ] Read the app name, mode, sandbox name, app details, products, scopes, and Target User state without revealing Client Secret.
- [ ] Verify mode is Sandbox and sandbox name is `T Cat Sandbox` before each mutation.
- [ ] Keep or set exact app details, configure Login Kit Desktop redirect, add only Content Posting API, and enable only `user.info.basic` and `video.publish`.
- [ ] Review pending changes, apply them, and read every validation error.
- [ ] Enter Target User settings; at login/terms/approval stop for exactly one user action.

### Task 8: Run live OAuth and Sandbox posting proof

**Files:**
- Create locally but never stage: `oauth-test/.env`
- Use user-supplied exact media file only.

**Interfaces:**
- Consumes: Client key, non-echoed Client Secret, configured Target User, and exact eligible 61-second MP4.
- Produces: safe evidence of callback, PKCE/state, user info, creator info, explicit Publish, publish ID existence, and status without credential values.

- [ ] Start the local service with secrets loaded from ignored `.env` and verify no secret values appear in process output.
- [ ] Start OAuth in dedicated Chrome; at login/consent stop for exactly one action.
- [ ] Verify callback, state, token exchange, and user info with only safe metadata.
- [ ] If no exact 61-second MP4 was supplied, stop and request only its full path and intended use confirmation.
- [ ] Validate video and render creator/account/caption/privacy review.
- [ ] At the explicit Publish action, require user action and then verify initialization, upload, and status under Sandbox restrictions.

### Task 9: Full QA, review, commit, and push

**Files:**
- Review all intended implementation and documentation files.

**Interfaces:**
- Produces: fresh test evidence, secret-free exact diff, and synchronized `origin/main` only if live Sandbox proof and every acceptance condition pass.

- [ ] Run `python -m unittest discover -s oauth-test/tests -v`.
- [ ] Run `node --test oauth-test/tests/cdp.test.mjs`.
- [ ] Run `powershell -NoProfile -ExecutionPolicy Bypass -File tests/validate-site.ps1`.
- [ ] Scan tracked and untracked candidates for secrets, tokens, authorization codes, `.env`, runtime state, browser profiles, media, screenshots, and unrelated assets.
- [ ] Run `git status`, inspect the complete `git diff`, and run `git diff --check`.
- [ ] Commit only after tests, Portal Sandbox proof, live OAuth proof, and posting proof meet the specification.
- [ ] Reconfirm GitHub account `lpg575757-lang` and exact remote before pushing `main`.
- [ ] Never push on partial live proof, test failure, secret detection, unexpected diff, or specification deviation.
