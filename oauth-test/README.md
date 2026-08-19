# TikTok Sandbox OAuth Test

This directory contains the local-only Desktop OAuth and Sandbox posting test harness.

## Local secret setup

1. Copy `.env.example` to `.env` inside this directory.
2. Enter the Sandbox Client Key and Client Secret only in the local `.env` file.
3. Never paste secret values into terminal commands, logs, screenshots, commits, or reports.

The local service reads the two values at runtime without printing them. Runtime state, the dedicated Chrome profile, test media, screenshots, and logs are excluded from Git.

The callback URL is `http://127.0.0.1:3455/callback/`. Production settings and Production Review are outside this tool's scope.

## Run locally

Start the server from the repository root:

```powershell
python oauth-test/server.py
```

Open `http://127.0.0.1:3455/` in the dedicated Sandbox browser. The server binds only to loopback. After OAuth validates the one-time state and exchanges the authorization code internally, it immediately redirects to the query-free `/authorized` page.

For a Direct Post test, provide an explicitly approved local MP4 path and caption. Review calls `creator_info/query`, shows the TikTok-returned account, interaction settings, privacy options, and maximum duration, and enforces `SELF_ONLY`. Initialization and upload occur only after the separate Publish button is pressed.

## Tests

```powershell
python -m unittest discover -s oauth-test/tests -p "test_*.py" -v
node --test oauth-test/tests/cdp.test.mjs
powershell -NoProfile -ExecutionPolicy Bypass -File tests/validate-site.ps1
```

The dedicated Chrome launcher is `oauth-test/start-sandbox-browser.ps1`. It creates a new ignored profile and never reuses the normal Chrome profile. Do not use the CDP helper for Production, reveal credentials, or submit a Production Review.
